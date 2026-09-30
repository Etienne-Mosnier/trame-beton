"""Machine cartésienne 700 × 700 × 700 mm : placement sur le plateau et G-code Klipper."""

import json
import math
import pathlib
import re

import pytest

from trame import app
from trame.export import gcode

CONTOURS = pathlib.Path(__file__).resolve().parent.parent / "contours"
MACHINE = app.CONFIG["cartesienne"]


def calculer_cartesienne(motif="exemple", contour="haricot.dxf", **moteur):
    texte = (CONTOURS / contour).read_text()
    return json.loads(app.calculer(motif, json.dumps({"machine": "cartesienne", "moteur": moteur}), texte, contour))


def test_trame_sur_le_plateau():
    r = calculer_cartesienne()
    assert r["palette"] == [700.0, 700.0]
    assert "plateau" in r["message_contour"]
    xs = [p[0] for p in r["path"]]
    ys = [p[1] for p in r["path"]]
    assert min(xs) - 5 >= 19.5 and max(xs) + 5 <= 680.5
    assert min(ys) - 5 >= 19.5 and max(ys) + 5 <= 680.5


def test_gcode():
    r = calculer_cartesienne(couches=2)
    g = json.loads(app.exporter("gcode"))
    assert g["nom"].endswith(".gcode")
    lignes = g["texte"].splitlines()
    assert all(ord(c) < 128 for c in g["texte"])
    for commande in ("G21", "G90", "M83", "G28"):
        assert any(l.startswith(commande) for l in lignes)
    mouvements = [l for l in lignes if re.match(r"G1 X", l)]
    assert len(mouvements) == pytest.approx(len(r["path"]) - 1, rel=0.01)   # points confondus retirés
    # extrusion : somme des E = longueur × largeur × hauteur / section du filament
    e_total = sum(float(re.search(r"E([\d.]+)", l).group(1)) for l in mouvements)
    section = math.pi * MACHINE["diametre_filament"] ** 2 / 4
    assert e_total == pytest.approx(r["longueur"] * 10 * 5 / section, rel=0.01)
    # hauteurs : 1re couche à la hauteur de couche, 2e couche au-dessus
    zs = [float(re.search(r"Z([\d.]+)", l).group(1)) for l in mouvements]
    assert min(zs) == pytest.approx(5) and max(zs) > 15


def test_export_selon_la_machine():
    calculer_cartesienne()
    assert "erreur" in json.loads(app.exporter("script"))
    texte = (CONTOURS / "haricot.dxf").read_text()
    app.calculer("exemple", "{}", texte, "haricot.dxf")
    assert "erreur" in json.loads(app.exporter("gcode"))
    assert "erreur" not in json.loads(app.exporter("script"))


def test_hors_machine():
    with pytest.raises(ValueError, match="sort de la machine"):
        gcode.generer([(0, 0, 0), (800, 0, 0)], MACHINE, 10, 5)


def test_points_du_motif_ramenes_sur_le_plateau():
    r = calculer_cartesienne("groupe_1/point_d_attraction")
    for x, y in r["points_motif"]["attractions"]:
        assert 0 <= x <= 700 and 0 <= y <= 700
