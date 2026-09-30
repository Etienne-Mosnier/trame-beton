"""Point d'entrée de la page web (trame/app.py)."""

import json

import pytest
import pathlib

from trame import app

CONTOURS = pathlib.Path(__file__).resolve().parent.parent / "contours"


def test_liste_motifs():
    motifs = json.loads(app.liste_motifs())
    exemple = next(m for m in motifs if m["id"] == "exemple")
    assert exemple["nom"].startswith("Exemple")
    assert exemple["parametres"]["series"]["valeur"][0] == {"angle": 160, "espacement": 50}
    assert set(exemple["parametres"]["series"]["champs"]) == {"angle", "espacement"}
    assert "série" in exemple["aide"]
    assert motifs[-1]["id"] == "exemple"       # les motifs des groupes d'abord
    groupe = next(m for m in motifs if m["id"] == "groupe_1/point_d_attraction")
    assert groupe["groupe"] == "groupe_1"


def test_reglages_moteur_en_francais():
    reglages = json.loads(app.reglages_moteur())
    assert set(reglages) == {"largeur_cordon", "hauteur_couche", "couches"}
    assert all(r["aide"] for r in reglages.values())


def test_calculer():
    texte = (CONTOURS / "haricot.dxf").read_text()
    reglages = {"motif": {"series": [{"angle": 160, "espacement": 80}, {"angle": 29, "espacement": 80},
                                     {"angle": 135, "espacement": 80}]}, "moteur": {"hauteur_couche": 4}}
    r = json.loads(app.calculer("exemple", json.dumps(reglages), texte, "haricot.dxf"))
    assert "erreur" not in r
    assert r["palette"] == [1200.0, 800.0]
    assert len(r["waves"]) == 3
    assert r["controle"]["sauts"] == 0
    assert r["amp"] == 4
    assert max(p[2] for p in r["path"]) == 8   # deux couches de 4 mm
    assert r["longueur"] > 0 and r["duree"] > 0


def test_calculer_erreur_en_francais():
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0 L 10 0"/></svg>'
    r = json.loads(app.calculer("exemple", "{}", svg, "trait.svg"))
    assert r["erreur"].startswith("Aucun contour fermé")


def test_bilan_texte():
    from trame.bilan import bilan
    texte = bilan("exemple", "rectangle.svg")
    assert "OK        Chemin continu" in texte
    assert "ATTENTION Virages assez doux (contour)" in texte


def test_moteur_deduit_du_cordon():
    assert app.reglages_du_moteur({"largeur_cordon": 12, "hauteur_couche": 6, "couches": 2}) == \
        {"amp": 6, "d": 12, "lane": 12, "couches": 2}
    texte = (CONTOURS / "rectangle.svg").read_text()
    r = json.loads(app.calculer("exemple", json.dumps({"moteur": {"largeur_cordon": 12, "hauteur_couche": 6}}),
                                texte, "rectangle.svg"))
    assert r["beton"]["largeur_cordon"] == 12 and r["amp"] == 6
    assert max(p[2] for p in r["path"]) == 12                  # deux cordons de 6 mm
    assert "hauteur de couche (6 mm)" in json.loads(app.exporter("script"))["texte"]


@pytest.mark.parametrize("largeur", [10, 25, 40])
def test_couloirs_toujours_sur_la_palette(largeur):
    # plus le cordon est large, plus les couloirs s'écartent : la forme est réduite pour que
    # le bord du cordon reste à la marge de la palette (20 mm) ou plus
    texte = (CONTOURS / "grand.svg").read_text()
    r = json.loads(app.calculer("exemple", json.dumps({"moteur": {"largeur_cordon": largeur}}), texte, "grand.svg"))
    xs = [p[0] for p in r["path"]]
    ys = [p[1] for p in r["path"]]
    demi = largeur / 2
    assert min(xs) - demi >= 20 - 0.5 and max(xs) + demi <= 1180 + 0.5
    assert min(ys) - demi >= 20 - 0.5 and max(ys) + demi <= 780 + 0.5
