"""Point d'entrée appelé par la page web : motif + réglages -> résultat JSON.

La page appelle :
    liste_motifs()                    -> motifs disponibles, leurs réglages et leur aide
    reglages_moteur()                 -> réglages du moteur (curseurs communs à tous les motifs)
    calculer(motif, reglages, texte, nom) -> tout ce qu'il faut pour dessiner l'aperçu
Toutes les fonctions renvoient un texte JSON. En cas d'erreur, calculer() renvoie
{"erreur": "message en français"} au lieu de planter.
"""

import importlib
import json
import pathlib
import sys
import tomllib
import traceback

from trame.contour import charger_contour
from trame.controles import controler, quantites
from trame.export.dxf import exporter_dxf
from trame.export.svg import exporter_svg
from trame.moteur.chemin import calculer_chemin
from trame.parametres import Parametre, valeurs

RACINE = pathlib.Path(__file__).resolve().parent.parent


def lire_config():
    with open(RACINE / "config" / "cellule.toml", "rb") as f:
        return tomllib.load(f)


CONFIG = lire_config()

# Valeurs du béton pas encore mesurées (0 dans config/cellule.toml) : valeurs provisoires,
# signalées dans l'aperçu. hauteur_couche = amp du .ghx.
PROVISOIRE = {"largeur_cordon": 10.0, "hauteur_couche": 5.0, "rayon_courbure_min": 20.0}
BETON = {nom: CONFIG["impression"][nom] or defaut for nom, defaut in PROVISOIRE.items()}
PROVISOIRES = [nom for nom in PROVISOIRE if not CONFIG["impression"][nom]]
HAUTEUR_COUCHE = BETON["hauteur_couche"]

# Réglages du moteur proposés dans l'aperçu (les autres gardent les valeurs du .ghx).
# Les noms affichés sont en français ; NOMS_MOTEUR donne le nom du réglage dans le moteur.
MOTEUR = {
    "hauteur_bosse": Parametre(HAUTEUR_COUCHE, mini=1.0, maxi=20.0, unite="mm", pas=0.5,
                     aide="Hauteur d'une bosse : une couche de cordon"),
    "longueur_montée": Parametre(10.0, mini=2.0, maxi=40.0, unite="mm", pas=0.5,
                   aide="Longueur de la montée de chaque côté d'un croisement"),
    "écart_couloirs": Parametre(5.0, mini=0.0, maxi=20.0, unite="mm", pas=0.5,
                      aide="Écart entre les liaisons de deux séries le long du bord"),
}
NOMS_MOTEUR = {"hauteur_bosse": "amp", "longueur_montée": "d", "écart_couloirs": "lane"}


def liste_motifs():
    """Motifs trouvés dans motifs/ : nom, réglages et texte d'aide."""
    sortie = []
    for dossier in sorted((RACINE / "motifs").iterdir()):
        if not (dossier / "motif.py").is_file():
            continue
        entree = {"id": dossier.name, "nom": dossier.name, "parametres": {}, "aide": ""}
        try:
            motif = importlib.import_module("motifs.%s.motif" % dossier.name)
            entree["nom"] = motif.NOM
            entree["parametres"] = {k: p.vers_dict() for k, p in motif.PARAMETRES.items()}
        except Exception as e:
            entree["erreur"] = "Le motif ne se charge pas : %s" % e
        aide = dossier / "aide.md"
        if aide.is_file():
            entree["aide"] = aide.read_text(encoding="utf-8")
        sortie.append(entree)
    # l'exemple en dernier : les motifs des groupes d'abord
    sortie.sort(key=lambda m: (m["id"] == "exemple", m["id"]))
    return json.dumps(sortie)


def reglages_moteur():
    return json.dumps({k: p.vers_dict() for k, p in MOTEUR.items()})


_contours = {}
_dernier = {}   # dernier calcul, pour les exports


def lire_contour(texte, nom):
    """Contour placé sur la palette ; gardé en mémoire pour ne pas relire le fichier."""
    cle = (nom, len(texte), hash(texte))
    if cle not in _contours:
        palette = CONFIG["palette"]
        _contours[cle] = charger_contour(texte, nom, marge=palette["marge"],
                                         palette=(palette["longueur"], palette["largeur"]))
    return _contours[cle]


def arrondir(points, chiffres=2):
    return [[round(v, chiffres) for v in p] for p in points]


def calculer(motif_id, reglages_json, contour_texte, contour_nom):
    """Calcul complet pour l'aperçu.

    reglages_json : {"motif": {nom: valeur}, "moteur": {nom: valeur}}
    """
    try:
        reglages = json.loads(reglages_json or "{}")
        place = lire_contour(contour_texte, contour_nom)
        forme = place["contour"]

        motif = importlib.import_module("motifs.%s.motif" % motif_id)
        p = valeurs(motif.PARAMETRES, reglages.get("motif"))
        series = motif.series(forme, p)
        moteur = {NOMS_MOTEUR[k]: v for k, v in valeurs(MOTEUR, reglages.get("moteur")).items()}

        r = calculer_chemin([[list(c.coords) for c in serie] for serie in series], forme, **moteur)

        palette = CONFIG["palette"]
        controles = controler(r, forme, series, {
            "largeur_cordon": BETON["largeur_cordon"],
            "rayon_courbure_min": BETON["rayon_courbure_min"],
            "lane": moteur["lane"],
            "palette": (palette["longueur"], palette["largeur"]),
            "marge": 0.0,     # le contour est déjà placé avec sa marge ; ici : rester sur la palette
        })
        q = quantites(r, BETON["largeur_cordon"], moteur["amp"], CONFIG["impression"]["vitesse"])
        path = r["path"] or []
        _dernier.update(resultat=r, contour=forme, motif=motif_id, lane=moteur["lane"],
                        amp=moteur["amp"], palette=(palette["longueur"], palette["largeur"]))
        return json.dumps({
            "palette": [CONFIG["palette"]["longueur"], CONFIG["palette"]["largeur"]],
            "contour": arrondir(forme.exterior.coords),
            "message_contour": place["message"],
            "waves": [[arrondir(v) for v in serie] for serie in r["waves"]],
            "path": arrondir(path),
            "jumps": [arrondir(j) for j in r["jumps"]],
            "controle": r["controle"],
            "controles": [dict(c, points=arrondir(c["points"]), segments=[arrondir(s) for s in c["segments"]])
                          for c in controles],
            "info": r["info"],
            **q,
            "beton": BETON,
            "provisoires": PROVISOIRES,
            "amp": moteur["amp"],
        })
    except ValueError as e:
        # erreurs prévues (contour ouvert, format inconnu…) : le message suffit
        return json.dumps({"erreur": str(e), "details": traceback.format_exc()})
    except Exception as e:
        return json.dumps({"erreur": "%s : %s" % (type(e).__name__, e),
                           "details": traceback.format_exc()})


def exporter(format_fichier):
    """Fichier DXF ou SVG du dernier calcul : {"nom": ..., "texte": ...} ou {"erreur": ...}."""
    if not _dernier:
        return json.dumps({"erreur": "Rien à exporter : lance d'abord un calcul."})
    d = _dernier
    if format_fichier == "dxf":
        texte = exporter_dxf(d["resultat"], d["contour"], d["palette"], d["lane"])
    elif format_fichier == "svg":
        texte = exporter_svg(d["resultat"], d["contour"], d["palette"], d["lane"], d["amp"])
    else:
        return json.dumps({"erreur": "Format inconnu : %s" % format_fichier})
    return json.dumps({"nom": "trame_%s.%s" % (d["motif"], format_fichier), "texte": texte})


def verifier():
    """Vérification de l'étape 2 : versions trouvées et un petit calcul shapely."""
    import ezdxf
    import shapely
    import svgelements
    from shapely.geometry import LineString

    # deux lignes qui se croisent au point (50, 50)
    a = LineString([(0, 0), (100, 100)])
    b = LineString([(0, 100), (100, 0)])
    croisement = a.intersection(b)

    return json.dumps({
        "ok": True,
        "python": sys.version.split()[0],
        "shapely": shapely.__version__,
        "ezdxf": ezdxf.__version__,
        "svgelements": svgelements.SVGELEMENTS_VERSION,
        "croisement": [croisement.x, croisement.y],
    })
