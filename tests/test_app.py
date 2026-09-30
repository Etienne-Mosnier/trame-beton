"""Point d'entrée de la page web (trame/app.py)."""

import json
import pathlib

from trame import app

CONTOURS = pathlib.Path(__file__).resolve().parent.parent / "contours"


def test_liste_motifs():
    motifs = json.loads(app.liste_motifs())
    exemple = next(m for m in motifs if m["id"] == "exemple")
    assert exemple["nom"].startswith("Exemple")
    assert exemple["parametres"]["espacement"]["valeur"] == 50
    assert "série" in exemple["aide"]
    assert motifs[-1]["id"] == "exemple"       # les motifs des groupes d'abord
    groupe = next(m for m in motifs if m["id"] == "groupe_1/point_d_attraction")
    assert groupe["groupe"] == "groupe_1"


def test_reglages_moteur_en_francais():
    reglages = json.loads(app.reglages_moteur())
    assert set(reglages) == {"hauteur_bosse", "longueur_montée", "écart_couloirs", "couches"}
    assert all(r["aide"] for r in reglages.values())


def test_calculer():
    texte = (CONTOURS / "haricot.dxf").read_text()
    reglages = {"motif": {"espacement": 80}, "moteur": {"hauteur_bosse": 4}}
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
