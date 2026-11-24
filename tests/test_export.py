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

DESSINS = pathlib.Path(__file__).resolve().parent.parent / "dessins"
FORME = box(100, 100, 500, 400)


@pytest.fixture(scope="module")
def calcul():
    r = json.loads(app.calculer(json.dumps({"moteur": {"couches": 2}}), (DESSINS / "spirales.dxf").read_text(), "spirales.dxf"))
    assert "erreur" not in r
    return r


def test_dxf(calcul):
    r = json.loads(app.exporter("dxf"))
    assert r["nom"] == "trame_spirales.dxf"
    doc = ezdxf.read(io.StringIO(r["texte"]))
    calques = {c.dxf.name for c in doc.layers}
    # un calque par calque imprimé : son rang d'impression, puis le nom du dessin
    assert {"PALETTE", "1. 1 spirale", "2. 2 boucles", "3. 3 vagues", "LIAISONS", "CHEMIN", "BOSSES",
            "DEPLACEMENTS", "PAUSES"} <= calques
    assert len(doc.modelspace().query('POINT[layer=="BOSSES"]')) > 0      # sommets des bosses
    assert "CONTOUR" not in calques                        # dessin importé : pas de contour
    msp = doc.modelspace()
    chemin = msp.query('POLYLINE[layer=="CHEMIN"]')[0]
    points = list(chemin.points())
    assert len(points) == len(calcul["path"])            # le chemin complet, point par point
    # hauteurs réelles, sans exagération : deux couches de 5 mm, et les bosses par-dessus
    assert max(p.z for p in points) == pytest.approx(max(p[2] for p in calcul["path"]), abs=0.01)
    assert max(p.z for p in points) > 10
    assert doc.header["$INSUNITS"] == 4                    # millimètres


def test_svg(calcul):
    r = json.loads(app.exporter("svg"))
    racine = ET.fromstring(r["texte"])
    ns = {"svg": "http://www.w3.org/2000/svg"}
    ids = {g.get("id") for g in racine.findall("svg:g", ns)}
    assert {"palette", "serie_A", "serie_B", "serie_C", "liaisons", "bosses"} <= ids
    assert racine.get("width") == "1320mm"                # palette + 60 mm de marge de chaque côté
    serie_b = racine.find("svg:g[@id='serie_B']", ns)
    assert len(serie_b.findall("svg:polyline", ns)) == 2  # une seule ligne, imprimée sur deux couches


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


def test_reimport_d_un_export():
    # un fichier exporté se réimporte : l'ordre d'impression est gardé, les calques techniques éteints
    from trame.dessin import lire_dessin
    texte = (DESSINS / "vagues.svg").read_text()
    app.calculer(json.dumps({"pauses": ["A vagues"], "calques": ["B lignes", "A vagues"]}), texte, "vagues.svg")
    for format_fichier in ("dxf", "svg"):
        d = lire_dessin(json.loads(app.exporter(format_fichier))["texte"], "export." + format_fichier)
        imprimes = [c["nom"] for c in d["calques"] if c["imprime"]]
        assert imprimes == ["1. B lignes", "2. A vagues"], format_fichier
