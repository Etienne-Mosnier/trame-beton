"""Maquette G-code (machine cartésienne 700 × 700 × 700 mm, Klipper) :
la trame en vraie grandeur réduite dans le rapport cordon d'essai / cordon final, en X, Y et Z."""

import json
import math
import pathlib
import re

import pytest

from trame import app
from trame.export import gcode

CONTOURS = pathlib.Path(__file__).resolve().parent.parent / "contours"
MACHINE = app.CONFIG["cartesienne"]


def calculer(largeur=20, hauteur=5, couches=1):
    texte = (CONTOURS / "haricot.dxf").read_text()
    moteur = {"largeur_cordon": largeur, "hauteur_couche": hauteur, "couches": couches}
    return json.loads(app.calculer("exemple", json.dumps({"moteur": moteur}), texte, "haricot.dxf"))


def mouvements(texte):
    return [l for l in texte.splitlines() if re.match(r"G1 X", l)]


def valeur(ligne, axe):
    return float(re.search(axe + r"(-?[\d.]+)", ligne).group(1))


def test_maquette_a_l_echelle_du_cordon():
    # cordon final 20 × 5 mm, essai 5 mm de large : échelle 1:4 en X, Y et Z
    r = calculer(largeur=20, hauteur=5, couches=2)
    g = json.loads(app.exporter("gcode", json.dumps({"largeur_essai": 5})))
    lignes = mouvements(g["texte"])
    xs = [valeur(l, "X") for l in lignes]
    ys = [valeur(l, "Y") for l in lignes]
    zs = [valeur(l, "Z") for l in lignes]
    vrais_x = [p[0] for p in r["path"]]
    vrais_y = [p[1] for p in r["path"]]
    # largeur du dessin divisée par 4, maquette centrée sur le plateau (palette 300 × 200 mm)
    assert max(xs) - min(xs) == pytest.approx((max(vrais_x) - min(vrais_x)) / 4, abs=0.1)
    assert max(ys) - min(ys) == pytest.approx((max(vrais_y) - min(vrais_y)) / 4, abs=0.1)
    assert (min(xs) + max(xs)) / 2 == pytest.approx(350 + ((min(vrais_x) + max(vrais_x)) / 2 - 600) / 4, abs=0.1)
    # hauteurs : couche d'essai 1,25 mm, bosses divisées par 4
    assert min(zs) == pytest.approx(1.25)
    assert max(zs) == pytest.approx(1.25 + max(p[2] for p in r["path"]) / 4, abs=0.05)
    assert "1:4" in g["texte"] and "5 x 1.25 mm" in g["texte"]


def test_extrusion_du_cordon_d_essai():
    r = calculer(largeur=20, hauteur=5)
    g = json.loads(app.exporter("gcode", json.dumps({"largeur_essai": 5})))
    e_total = sum(valeur(l, "E") for l in mouvements(g["texte"]))
    section = math.pi * MACHINE["diametre_filament"] ** 2 / 4
    # volume de la maquette : longueur / 4 × 5 × 1,25 mm
    assert e_total == pytest.approx(r["longueur"] / 4 * 5 * 1.25 / section, rel=0.01)
    lignes = g["texte"].splitlines()
    for commande in ("G21", "G90", "M83", "G28"):
        assert any(l.startswith(commande) for l in lignes)


def test_rapport_affiche_dans_l_apercu():
    calculer(largeur=20)
    m = json.loads(app.maquette(5))
    r = calculer(largeur=20)
    xs = [p[0] for p in r["path"]]
    assert m["rapport"] == 4 and m["tient"]
    assert m["taille"][0] == pytest.approx((max(xs) - min(xs)) / 4, abs=1)
    assert not json.loads(app.maquette(19))["tient"]           # presque 1:1 : trop grand


def test_maquette_trop_grande():
    calculer(largeur=20)
    assert "ne tient pas" in json.loads(app.exporter("gcode", json.dumps({"largeur_essai": 19})))["erreur"]
    with pytest.raises(ValueError):
        gcode.echelle(20, 0)


def test_vitesse_automatique_selon_le_debit():
    # comme Orca : vitesse = débit / section, plafonnée à vitesse_max
    m = dict(MACHINE, debit_volumique_max=100.0, vitesse_max=60.0)
    assert gcode.vitesse_impression(m, 5, 2) == pytest.approx(10)       # 100 / 10 mm²
    assert gcode.vitesse_impression(m, 1, 1) == pytest.approx(60)       # plafond
    calculer(largeur=20, hauteur=5)
    g = json.loads(app.exporter("gcode", json.dumps({"largeur_essai": 5})))
    attendu = gcode.vitesse_impression(MACHINE, 5, 1.25)
    assert "G1 F%d" % (attendu * 60) in g["texte"]
    assert json.loads(app.maquette(5))["vitesse"] == pytest.approx(attendu, abs=0.1)
    # un cordon d'essai plus fin s'imprime plus vite (tant qu'on reste sous le plafond)
    assert json.loads(app.maquette(4))["vitesse"] >= json.loads(app.maquette(5))["vitesse"]
