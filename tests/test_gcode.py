"""Maquette G-code (WASP 2040, delta, Marlin, plateau rond de 200 mm) : la trame en vraie grandeur
réduite dans le rapport cordon d'essai / cordon final, en X, Y et Z ; extrusion continue par le
boîtier externe (pas d'axe E) ; arrêts M0 au départ, aux pauses et à la fin."""

import json
import math
import pathlib
import re

import pytest

from trame import app
from trame.export import gcode

DESSINS = pathlib.Path(__file__).resolve().parent.parent / "dessins"
MACHINE = app.CONFIG["wasp"]


def calculer(largeur=10, hauteur=5, couches=1, pauses=()):
    texte = (DESSINS / "spirales.dxf").read_text()
    moteur = {"largeur_cordon": largeur, "hauteur_couche": hauteur, "couches": couches}
    return json.loads(app.calculer(json.dumps({"moteur": moteur, "pauses": list(pauses)}), texte, "spirales.dxf"))


def mouvements(texte):
    return [l for l in texte.splitlines() if re.match(r"G1 X", l)]


def valeur(ligne, axe):
    return float(re.search(axe + r"(-?[\d.]+)", ligne).group(1))


def test_maquette_a_l_echelle_du_cordon():
    # cordon final 10 × 5 mm, essai 1,5 mm : échelle 1:6,67 en X, Y et Z, centre de la palette au centre
    r = calculer(largeur=10, hauteur=5, couches=2)
    g = json.loads(app.exporter("gcode", json.dumps({"largeur_essai": 1.5})))
    lignes = mouvements(g["texte"])
    k = 1.5 / 10
    attendus = [((p[0] - 600) * k, (p[1] - 400) * k, p[2] * k + 5 * k) for p in r["path"]]
    for ligne in lignes[::50]:
        x, y, z = valeur(ligne, "X"), valeur(ligne, "Y"), valeur(ligne, "Z")
        assert min(math.dist((x, y, z), a) for a in attendus) < 0.02
    # tout tient sur le plateau rond, marge comprise
    assert all(math.hypot(valeur(l, "X"), valeur(l, "Y")) <= 95 for l in lignes)
    # la première couche est à la hauteur du cordon d'essai (0,75 mm)
    assert min(valeur(l, "Z") for l in lignes) == pytest.approx(0.75)
    assert "1:6.67" in g["texte"]


def test_deplacements_seulement():
    calculer()
    texte = json.loads(app.exporter("gcode", json.dumps({"largeur_essai": 1.5})))["texte"]
    lignes = texte.splitlines()
    # extrusion par le boîtier externe : aucun axe E
    assert not any(re.search(r"\bE-?[\d.]", l.split(";")[0]) for l in lignes)
    for commande in ("G21", "G90", "M84 S0", "G28"):
        assert any(l.startswith(commande) for l in lignes)
    assert "G1 F%d" % (MACHINE["vitesse"] * 60) in texte


def test_arrets_au_depart_aux_pauses_et_a_la_fin():
    r = calculer(pauses=["1 spirale"])
    texte = json.loads(app.exporter("gcode", json.dumps({"largeur_essai": 1.5})))["texte"]
    lignes = texte.splitlines()
    arrets = [l for l in lignes if l.startswith("M0 ")]
    assert arrets == ["M0 Lancer extrusion", "M0 Pause 1 : cliquer", "M0 Couper extrusion"]
    # chaque arrêt attend la fin des mouvements, au point d'attente (à côté du dessin)
    k = 1.5 / 10
    for arret, attente in zip(arrets, [r["depart"], r["pauses"][0], r["fin"]]):
        i = lignes.index(arret)
        assert lignes[i - 3].startswith("M400")
        position = next(l for l in reversed(lignes[:i]) if re.match(r"G[01] X", l))
        x, y = (attente["point"][0] - 600) * k, (attente["point"][1] - 400) * k
        assert math.dist((valeur(position, "X"), valeur(position, "Y")), (x, y)) < 0.05


def test_rapport_affiche_dans_l_apercu():
    calculer(largeur=10)
    m = json.loads(app.maquette(1.5))
    assert m["rapport"] == pytest.approx(6.67) and m["tient"] and m["plateau"] == 200
    assert m["vitesse"] == MACHINE["vitesse"]
    trop = json.loads(app.maquette(5))
    assert not trop["tient"] and 1.5 < trop["essai_max"] < 5
    assert json.loads(app.maquette(trop["essai_max"] - 0.01))["tient"]


def test_maquette_trop_grande():
    calculer(largeur=10)
    erreur = json.loads(app.exporter("gcode", json.dumps({"largeur_essai": 5})))["erreur"]
    assert "ne tient pas sur le plateau rond" in erreur and "au plus" in erreur
    with pytest.raises(ValueError):
        gcode.echelle(20, 0)
