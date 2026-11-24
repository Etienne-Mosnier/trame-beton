"""Point d'entrée de la page web (trame/app.py)."""

import json

import pytest
import pathlib

from trame import app

RACINE = pathlib.Path(__file__).resolve().parent.parent
CONTOURS = RACINE / "contours"
DESSINS = RACINE / "dessins"


def test_liste_motifs():
    motifs = json.loads(app.liste_motifs())
    exemple = next(m for m in motifs if m["id"] == "exemple")
    assert exemple["nom"].startswith("Exemple")
    assert exemple["parametres"]["series"]["valeur"][0] == {"angle": 160, "espacement": 50}
    assert set(exemple["parametres"]["series"]["champs"]) == {"angle", "espacement"}
    assert "série" in exemple["aide"]
    assert motifs[-1]["id"] == "exemple"       # les motifs des groupes d'abord
    assert exemple["groupe"] == ""                  # l'exemple n'appartient à aucun groupe


def test_reglages_moteur_en_francais():
    reglages = json.loads(app.reglages_moteur())
    assert set(reglages) == {"largeur_cordon", "hauteur_couche", "couches"}
    assert all(r["aide"] for r in reglages.values())


def test_calculer():
    texte = (CONTOURS / "haricot.dxf").read_text()
    reglages = {"motif": {"series": [{"angle": 160, "espacement": 80}, {"angle": 29, "espacement": 80},
                                     {"angle": 135, "espacement": 80}]}, "moteur": {"hauteur_couche": 4}}
    r = json.loads(app.calculer_motif("exemple", json.dumps(reglages), texte, "haricot.dxf"))
    assert "erreur" not in r
    assert r["palette"] == [1200.0, 800.0]
    assert len(r["waves"]) == 3
    assert r["controle"]["sauts"] == 0
    assert r["amp"] == 4
    assert max(p[2] for p in r["path"]) == 8   # deux couches de 4 mm
    assert r["longueur"] > 0 and r["duree"] > 0


def test_calculer_erreur_en_francais():
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0 L 10 0"/></svg>'
    r = json.loads(app.calculer_motif("exemple", "{}", svg, "trait.svg"))
    assert r["erreur"].startswith("Aucun contour fermé")


def test_bilan_texte():
    from trame.bilan import bilan
    texte = bilan(DESSINS / "vagues.svg")
    assert "Calques imprimés, dans l'ordre : A vagues, B lignes" in texte
    assert "OK        Sur la palette" in texte


def test_moteur_deduit_du_cordon():
    assert app.reglages_du_moteur({"largeur_cordon": 12, "hauteur_couche": 6, "couches": 2}) == \
        {"amp": 6, "d": 12, "lane": 12, "couches": 2}
    texte = (CONTOURS / "rectangle.svg").read_text()
    r = json.loads(app.calculer_motif("exemple", json.dumps({"moteur": {"largeur_cordon": 12, "hauteur_couche": 6}}),
                                      texte, "rectangle.svg"))
    assert r["beton"]["largeur_cordon"] == 12 and r["amp"] == 6
    assert max(p[2] for p in r["path"]) == 12                  # deux cordons de 6 mm
    assert "hauteur de couche (6 mm)" in json.loads(app.exporter("script"))["texte"]


@pytest.mark.parametrize("largeur", [10, 25, 40])
def test_couloirs_toujours_sur_la_palette(largeur):
    # plus le cordon est large, plus les couloirs s'écartent : la forme est réduite pour que
    # le bord du cordon reste à la marge de la palette (20 mm) ou plus
    texte = (CONTOURS / "grand.svg").read_text()
    r = json.loads(app.calculer_motif("exemple", json.dumps({"moteur": {"largeur_cordon": largeur}}), texte, "grand.svg"))
    xs = [p[0] for p in r["path"]]
    ys = [p[1] for p in r["path"]]
    demi = largeur / 2
    assert min(xs) - demi >= 20 - 0.5 and max(xs) + demi <= 1180 + 0.5
    assert min(ys) - demi >= 20 - 0.5 and max(ys) + demi <= 780 + 0.5


# --- dessin importé, en calques ------------------------------------------------------


def test_lire_calques():
    r = json.loads(app.lire_calques((DESSINS / "spirales.dxf").read_text(), "spirales.dxf"))
    assert [c["nom"] for c in r["calques"]] == ["1 spirale", "2 boucles", "3 vagues"]
    assert all(c["imprime"] and c["lignes"] == 1 and c["longueur"] > 1000 for c in r["calques"])
    assert r["message"] == "3 calques"


def test_lire_calques_erreur_en_francais():
    r = json.loads(app.lire_calques("<svg", "casse.svg"))
    assert "illisible" in r["erreur"]


def test_calculer_dessin():
    texte = (DESSINS / "vagues.svg").read_text()
    r = json.loads(app.calculer(json.dumps({"moteur": {"hauteur_couche": 4}}), texte, "vagues.svg"))
    assert "erreur" not in r
    assert r["calques"] == ["A vagues", "B lignes"]           # ordre alphabétique au départ
    assert len(r["waves"]) == 2 and r["jumps"] == []
    assert max(p[2] for p in r["path"]) == 4                   # B passe par-dessus A
    assert "taille réelle" in r["message_dessin"]
    assert {c["statut"] for c in r["controles"]} == {"ok"}
    # le chemin reste sur la palette, à la marge près
    xs, ys = [p[0] for p in r["path"]], [p[1] for p in r["path"]]
    assert min(xs) >= 20 and max(xs) <= 1180 and min(ys) >= 20 and max(ys) <= 780
    for format_fichier in ("dxf", "svg", "script"):
        e = json.loads(app.exporter(format_fichier))
        assert "erreur" not in e and e["nom"] == "trame_vagues." + format_fichier
    assert "Dessin : vagues.svg" in json.loads(app.exporter("script"))["texte"]


def test_calculer_ordre_choisi():
    texte = (DESSINS / "vagues.svg").read_text()
    r = json.loads(app.calculer(json.dumps({"calques": ["B lignes", "A vagues"]}), texte, "vagues.svg"))
    assert r["calques"] == ["B lignes", "A vagues"]
    assert max(p[2] for w in r["waves"][0] for p in w) == 0    # B d'abord : à plat
    assert max(p[2] for w in r["waves"][1] for p in w) > 0     # A par-dessus


def test_calculer_dessin_erreurs():
    texte = (DESSINS / "vagues.svg").read_text()
    r = json.loads(app.calculer(json.dumps({"calques": []}), texte, "vagues.svg"))
    assert r["erreur"].startswith("Aucun calque à imprimer")
    six = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>%s</svg>" % "".join(
        "<g id='c%d'><path d='M0 %d L 100 %d' stroke='#000'/></g>" % (k, 10 * k, 10 * k) for k in range(6))
    r = json.loads(app.calculer("{}", six, "six.svg"))
    assert r["erreur"].startswith("6 calques à imprimer : 5 au plus")


def test_calculer_avec_pause():
    import io
    import ezdxf
    texte = (DESSINS / "vagues.svg").read_text()
    r = json.loads(app.calculer(json.dumps({"pauses": ["A vagues"]}), texte, "vagues.svg"))
    assert "erreur" not in r
    assert r["pauses"][0]["calque"] == "A vagues" and r["pauses"][0]["libre"]
    assert len(r["deplacements"]) == 1
    # la buse attend sur la palette, levée de la hauteur d'approche au-dessus du béton
    x, y, z = r["pauses"][0]["point"]
    assert 0 <= x <= 1200 and 0 <= y <= 800 and z >= app.CONFIG["impression"]["hauteur_approche"]
    titres = [c["titre"] for c in r["controles"]]
    assert "Pauses : 1, sans passer au-dessus du béton" in titres
    doc = ezdxf.read(io.StringIO(json.loads(app.exporter("dxf"))["texte"]))
    assert {"DEPLACEMENTS", "PAUSES"} <= {c.dxf.name for c in doc.layers}
    # le programme du robot s'arrête au point d'attente et attend « Continuer »
    script = json.loads(app.exporter("script"))["texte"]
    assert script.count("blocking=True") == 2              # la pause, et l'avertissement de simulation
    assert "Pause 1, apres le calque 'A vagues' (couche 1)" in script
    # le G-code de la maquette ne sait pas encore : il le dit
    assert "Pauses" in json.loads(app.exporter("gcode"))["erreur"]
    # le robot ne dépose pas de cordon pendant le trajet à vide
    bras = json.loads(app.robot())
    assert -1 in bras["series"] and bras["hors_portee"] == []
