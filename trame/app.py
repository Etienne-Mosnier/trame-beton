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
import math
import pathlib
import sys
import tomllib
import traceback

from trame.contour import charger_contour
from trame.controles import controler, quantites
from trame.export.dxf import exporter_dxf
from trame.export.svg import exporter_svg
import numpy as np

from trame.robot import alertes, cinematique, urscript
from trame.robot.calibration import repere_palette, vers_robot
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
        _dernier.update(resultat=r, contour=forme, motif=motif_id, nom_contour=contour_nom,
                        lane=moteur["lane"],
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


_placement = {}   # placement de la palette choisi dans le mode enseignant (remplace la simulation)


def points_placement(x, y, z, rotation):
    """Les 3 points de calibration d'une palette posée à plat : coin (x, y, z) dans le repère du
    robot (mm), grand côté tourné de 'rotation' degrés par rapport à l'axe X du robot."""
    lx, ly = CONFIG["palette"]["longueur"], CONFIG["palette"]["largeur"]
    c, s = math.cos(math.radians(rotation)), math.sin(math.radians(rotation))
    return {"origine": [x, y, z], "grand_cote": [x + lx * c, y + lx * s, z],
            "petit_cote": [x - ly * s, y + ly * c, z]}


def calibration():
    """Repère de la palette : la calibration relevée si elle est complète, sinon le placement
    du mode enseignant, sinon la calibration de simulation. Renvoie (repere, simulation)."""
    c = CONFIG["calibration"]
    simulation = not (c["origine"] and c["grand_cote"] and c["petit_cote"])
    if simulation:
        c = _placement or CONFIG["calibration_simulation"]
    return repere_palette(c["origine"], c["grand_cote"], c["petit_cote"]), simulation


PORTEE_MAX = 1300.0   # mm, portée annoncée de l'UR10e
PIED = 200.0          # mm autour de l'axe du robot : la buse y toucherait le pied du robot


def lisser(geometrie, tours=3):
    """Arrondit les bords d'un polygone (coupe les coins, méthode de Chaikin)."""
    from shapely.geometry import Polygon

    def anneau(points):
        points = list(points)[:-1]
        for _ in range(tours):
            nouveaux = []
            for a, b in zip(points, points[1:] + points[:1]):
                nouveaux += [(0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]),
                             (0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1])]
            points = nouveaux
        return points

    polygones = [Polygon(anneau(p.exterior.coords), [anneau(t.coords) for t in p.interiors])
                 for p in getattr(geometrie, "geoms", [geometrie]) if not p.is_empty]
    from shapely.ops import unary_union
    return unary_union([p.buffer(0) for p in polygones])


def formes(geometrie):
    """Polygone(s) shapely -> [[contour extérieur, trou, trou…], …] en listes de points (mm)."""
    polygones = getattr(geometrie, "geoms", [geometrie])
    return [[[[round(x, 1), round(y, 1)] for x, y in anneau.coords]
             for anneau in [p.exterior, *p.interiors]]
            for p in polygones if not p.is_empty and p.area > 0]


def cercle_ajuste(points):
    """Cercle (cx, cy, rayon) le plus proche d'une suite de points (moindres carrés)."""
    P = np.array([p[:2] for p in points], dtype=float)
    A = np.column_stack([P[:, 0], P[:, 1], np.ones(len(P))])
    b = -(P[:, 0] ** 2 + P[:, 1] ** 2)
    D, E, F = np.linalg.lstsq(A, b, rcond=None)[0]
    cx, cy = -D / 2, -E / 2
    return cx, cy, math.sqrt(cx * cx + cy * cy - F)


def portee(repere):
    """Limites et orientation du robot, dans le repère du ROBOT (mm), au niveau de la palette :
    zone où il amène la buse verticale (hauteurs d'impression et d'approche), partie de la
    palette hors de portée, cercle de portée maximale, directions du nord."""
    from shapely.geometry import Point, Polygon, box
    from shapely.ops import unary_union

    imp = reglages_impression()
    outil = CONFIG["outil"]
    tcp = cinematique.matrice_pose([v / 1000 for v in outil["tcp"][:3]] + list(outil["tcp"][3:]))
    z_plan = repere["origine"][2]            # hauteur du dessus de la palette (repère robot)
    pas = 50.0
    r = PORTEE_MAX + 100
    cases = alertes.zone_atteignable(
        lambda p: (p[0], p[1], z_plan + p[2]),
        (-r, r, -r, r),
        [imp["hauteur_buse"], imp["hauteur_buse"] + imp["hauteur_approche"]],
        np.array(urscript.buse_dans_base(outil.get("rotation_z", 0.0))).T,
        np.linalg.inv(tcp), pas=pas)
    # cases atteignables réunies en une forme, bords en escalier lissés, pied du robot retiré
    zone = unary_union([box(x - pas / 2, y - pas / 2, x + pas / 2, y + pas / 2)
                        for x, y, ok in cases if ok])
    zone = zone.buffer(pas).buffer(-2 * pas).buffer(pas)
    # La buse est décalée de la bride et garde la même orientation : la zone est un vrai cercle,
    # dont le centre est décalé par rapport à l'axe du robot. On ajuste ce cercle sur le bord
    # extérieur, un autre sur le bord intérieur, et on garde un anneau prudent (un peu plus petit).
    principale = max(getattr(zone, "geoms", [zone]), key=lambda g: g.area)
    cx, cy, rayon_ext = cercle_ajuste(principale.exterior.coords)
    rayon_ext -= pas / 2
    trous = [c for t in principale.interiors for c in t.coords]
    rayon_int = PIED
    if trous:
        ix, iy, ri = cercle_ajuste(trous)
        # le trou intérieur, ramené au même centre, sans le rogner
        rayon_int = max(PIED, max(math.dist((cx, cy), c) for c in trous) + pas / 2)
    # un seul cercle intérieur, de même centre, qui englobe aussi le pied du robot
    rayon_int = max(rayon_int, math.hypot(cx, cy) + PIED)
    centre = Point(cx, cy)
    zone = centre.buffer(rayon_ext, quad_segs=64).difference(centre.buffer(rayon_int, quad_segs=64))

    # la palette dans le repère du robot, et sa partie hors de portée
    lx, ly = CONFIG["palette"]["longueur"], CONFIG["palette"]["largeur"]
    coins = [vers_robot(repere, (x, y, 0))[:2] for x, y in ((0, 0), (lx, 0), (lx, ly), (0, ly))]
    palette = Polygon(coins)
    hors = palette.difference(zone)

    nord = math.radians(CONFIG["robot"].get("nord", 90.0))
    return {
        "zone": formes(zone),
        "centre": [round(cx, 1), round(cy, 1)],
        "rayon_ext": round(rayon_ext),
        "rayon_int": round(rayon_int),
        "hors_palette": formes(hors),
        "atteignable": round(100 * (1 - hors.area / palette.area)),
        "z": round(z_plan, 1),
        "portee_max": PORTEE_MAX,
        "nord": [round(math.cos(nord), 6), round(math.sin(nord), 6)],
    }


def portee_robot():
    """Limites et orientation du robot pour la calibration en cours (texte JSON)."""
    return json.dumps(portee(calibration()[0]))


def placement(reglages_json):
    """Mode enseignant : place la palette (x, y, z en mm, rotation en degrés, repère du robot),
    ou revient à la calibration de simulation si reglages_json est vide.
    Renvoie la zone atteignable et les 3 points à recopier dans config/cellule.toml."""
    reglages = json.loads(reglages_json or "{}")
    _placement.clear()
    if reglages:
        _placement.update(points_placement(reglages["x"], reglages["y"], reglages["z"], reglages["rotation"]))
    repere, simulation = calibration()
    p = portee(repere)
    c = _placement or CONFIG["calibration_simulation"]
    return json.dumps({
        "portee": p,
        "atteignable": p["atteignable"],
        "calibration": {k: [round(v, 1) for v in c[k]] for k in ("origine", "grand_cote", "petit_cote")},
        "simulation": simulation,
    })


def reglages_impression():
    """Réglages d'impression, avec la hauteur de buse provisoire si elle n'est pas fixée."""
    imp = dict(CONFIG["impression"])
    if not imp["hauteur_buse"]:
        imp["hauteur_buse"] = BETON["hauteur_couche"]
    return imp


def programme_robot(d):
    """Texte URScript du dernier calcul."""
    repere, simulation = calibration()
    imp = reglages_impression()
    entete = ["Motif : %s, contour : %s" % (d["motif"], d["nom_contour"])]
    if not CONFIG["impression"]["hauteur_buse"]:
        entete.append("PROVISOIRE : hauteur de la buse = hauteur de couche (%g mm)" % imp["hauteur_buse"])
    for nom in PROVISOIRES:
        entete.append("PROVISOIRE : %s = %g mm" % (nom, BETON[nom]))
    entete.append("A MESURER : masse de la buse (%g kg declares)" % CONFIG["outil"]["masse_kg"])
    if simulation:
        entete.append("SIMULATION : calibration de simulation (config/cellule.toml, calibration vide)")
    if repere["defaut_angle"] > 2:
        entete.append("ATTENTION : les cotes releves font %.1f degres d'ecart avec l'equerre"
                      % repere["defaut_angle"])
    if not CONFIG["extrusion"]["active"]:
        entete.append("Extrusion desactivee : la buse suit le chemin sans pomper")
    reglages = {"outil": CONFIG["outil"], "impression": imp, "extrusion": CONFIG["extrusion"]}
    return urscript.generer(d["resultat"]["path"] or [], repere, reglages, entete, simulation)


def exporter(format_fichier):
    """Fichier du dernier calcul : DXF, SVG ou programme du robot (script).
    Renvoie {"nom": ..., "texte": ...} ou {"erreur": ...}."""
    if not _dernier:
        return json.dumps({"erreur": "Rien à exporter : lance d'abord un calcul."})
    d = _dernier
    if format_fichier == "script":
        try:
            texte = programme_robot(d)
        except ValueError as e:
            return json.dumps({"erreur": str(e)})
    elif format_fichier == "dxf":
        texte = exporter_dxf(d["resultat"], d["contour"], d["palette"], d["lane"])
    elif format_fichier == "svg":
        texte = exporter_svg(d["resultat"], d["contour"], d["palette"], d["lane"], d["amp"])
    else:
        return json.dumps({"erreur": "Format inconnu : %s" % format_fichier})
    return json.dumps({"nom": "trame_%s.%s" % (d["motif"], format_fichier), "texte": texte})


def robot():
    """Mouvement du bras pour le dernier calcul : angles des articulations à chaque point du
    programme (approche et dégagement compris), temps, et position du robot vue de la palette."""
    if not _dernier:
        return json.dumps({"erreur": "Lance d'abord un calcul."})
    d = _dernier
    repere, simulation = calibration()
    imp = reglages_impression()
    outil = CONFIG["outil"]
    hb, h = imp["hauteur_buse"], imp["hauteur_approche"]
    points = urscript.preparer_points(d["resultat"]["path"] or [], hb, imp["longueur_max_segment"])
    if len(points) < 2:
        return json.dumps({"erreur": "Rien à imprimer."})
    premier, dernier = points[0], points[-1]
    tous = [(premier[0], premier[1], premier[2] + h)] + points + [(dernier[0], dernier[1], dernier[2] + h)]

    # pose de la bride pour chaque point : buse verticale, dans le repère du robot (m)
    R = np.array(urscript.buse_dans_base(outil.get("rotation_z", 0.0))).T
    tcp = cinematique.matrice_pose([v / 1000 for v in outil["tcp"][:3]] + list(outil["tcp"][3:]))
    tcp_inverse = np.linalg.inv(tcp)
    poses = []
    for p in tous:
        T = np.eye(4)
        T[:3, :3] = R
        T[:3, 3] = [v / 1000 for v in vers_robot(repere, p)]
        poses.append(T @ tcp_inverse)
    angles, hors_portee = cinematique.trajectoire(poses)

    # alertes : repère du robot (mm) -> repère palette
    Rp = np.array([repere["x"], repere["y"], repere["z"]])      # lignes = axes de la palette
    vers_palette = np.eye(4)
    vers_palette[:3, :3] = Rp
    vers_palette[:3, 3] = -Rp @ np.array(repere["origine"])
    liste_alertes = alertes.analyser(angles, hors_portee, tous, tcp, vers_palette,
                                     (CONFIG["palette"]["longueur"], CONFIG["palette"]["largeur"]))

    # temps de passage (s) : approche et dégagement à la vitesse d'approche
    temps = [0.0]
    for k in range(1, len(tous)):
        v = imp["vitesse_approche"] if k in (1, len(tous) - 1) else imp["vitesse"]
        temps.append(temps[-1] + math.dist(tous[k - 1], tous[k]) / v)

    # série de chaque point (pour déposer le cordon avec la bonne couleur)
    serie_de = {}
    for i, serie in enumerate(d["resultat"]["waves"]):
        for poly in serie:
            for p in poly:
                serie_de.setdefault((round(p[0], 2), round(p[1], 2)), i)
    series, courant = [], 0
    for p in tous:
        courant = serie_de.get((round(p[0], 2), round(p[1], 2)), courant)
        series.append(courant)

    # position du robot vue depuis la palette (inverse du repère de la palette)
    base = vers_palette[:3, 3]
    return json.dumps({
        "base": {"position": [round(v, 2) for v in base], "rotation": np.round(Rp, 6).tolist()},
        # repère de la palette dans celui du robot (mm) : l'aperçu y place la palette
        "repere": {k: [round(float(v), 6) for v in repere[k]] for k in ("origine", "x", "y", "z")},
        "tcp": outil["tcp"],
        "points": [[round(p[0], 2), round(p[1], 2), round(p[2] - hb, 2)] for p in tous],
        "series": series,
        "angles": [[round(v, 5) for v in q] for q in angles],
        "temps": [round(t, 3) for t in temps],
        "hors_portee": hors_portee,
        "alertes": [dict(a, points=[[round(v, 1) for v in p] for p in a["points"]]) for a in liste_alertes],
        "simulation": simulation,
    })


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
