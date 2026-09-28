"""Exports DXF et SVG : calques, hauteurs réelles, liaisons séparées."""

import io
import json
import pathlib
import xml.etree.ElementTree as ET

import ezdxf
import pytest
from shapely.geometry import LineString, Point, box

from trame import app
from trame.export.commun import separer_liaisons, sommets_des_bosses
from trame.moteur.chemin import calculer_chemin

CONTOURS = pathlib.Path(__file__).resolve().parent.parent / "contours"
FORME = box(100, 100, 500, 400)


@pytest.fixture(scope="module")
def calcul():
    r = json.loads(app.calculer("exemple", "{}", (CONTOURS / "haricot.dxf").read_text(), "haricot.dxf"))
    assert "erreur" not in r
    return r


def test_dxf(calcul):
    r = json.loads(app.exporter("dxf"))
    assert r["nom"] == "trame_exemple.dxf"
    doc = ezdxf.read(io.StringIO(r["texte"]))
    calques = {c.dxf.name for c in doc.layers}
    assert {"PALETTE", "CONTOUR", "SERIE_A", "SERIE_B", "SERIE_C", "LIAISONS", "CHEMIN", "BOSSES"} <= calques
    msp = doc.modelspace()
    chemin = msp.query('POLYLINE[layer=="CHEMIN"]')[0]
    points = list(chemin.points())
    assert len(points) == len(calcul["path"])            # le chemin complet, point par point
    assert max(p.z for p in points) == pytest.approx(10)  # deux couches de 5 mm, hauteur réelle
    assert doc.header["$INSUNITS"] == 4                    # millimètres


def test_svg(calcul):
    r = json.loads(app.exporter("svg"))
    racine = ET.fromstring(r["texte"])
    ns = {"svg": "http://www.w3.org/2000/svg"}
    ids = {g.get("id") for g in racine.findall("svg:g", ns)}
    assert {"palette", "contour", "serie_A", "serie_B", "serie_C", "liaisons", "bosses"} <= ids
    assert racine.get("width") == "1320mm"                # palette + 60 mm de marge de chaque côté
    serie_b = racine.find("svg:g[@id='serie_B']", ns)
    assert len(serie_b.findall("svg:polyline", ns)) > 5


def test_liaisons_separees():
    S = [[[(0, y), (600, y)] for y in range(140, 400, 40)]]
    r = calculer_chemin(S, FORME, lane=5)
    lignes, liaisons = separer_liaisons(r["waves"], FORME, lane=5)
    # chaque ligne du motif est un morceau à part, horizontal
    assert len(lignes[0]) == 7
    assert all(abs(m[0][1] - m[-1][1]) < 1e-6 for m in lignes[0])
    # les liaisons longent le contour
    for poly in liaisons:
        for p in poly:
            assert FORME.exterior.distance(Point(p[0], p[1])) < 0.3


def test_sommets_des_bosses():
    waves = [[[(0, 0, 0), (10, 0, 5), (20, 0, 0), (30, 0, 10), (40, 0, 0)]]]
    assert sommets_des_bosses(waves) == [(10, 0, 5), (30, 0, 10)]


def test_exporter_sans_calcul():
    app._dernier.clear()
    assert "erreur" in json.loads(app.exporter("dxf"))
