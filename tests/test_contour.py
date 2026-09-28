"""Import des contours SVG/DXF et placement sur la palette."""

import pathlib

import pytest
from shapely.geometry import Polygon, box

from trame.contour import charger_contour, placer

DOSSIER = pathlib.Path(__file__).resolve().parent / "contours"
PALETTE_UTILE = box(20, 20, 1180, 780)  # palette 1200 × 800 avec 20 mm de marge


def charger(nom, **reglages):
    return charger_contour((DOSSIER / nom).read_text(encoding="utf-8"), nom, **reglages)


def dimensions(forme):
    xmin, ymin, xmax, ymax = forme.bounds
    return xmax - xmin, ymax - ymin


def test_rectangle_svg_garde_sa_taille():
    # le petit cercle à l'intérieur est ignoré : on garde le plus grand contour
    r = charger("rectangle.svg")
    assert r["rotation"] == 0 and r["echelle"] == 1
    assert dimensions(r["contour"]) == pytest.approx((280, 180), abs=0.01)
    assert r["contour"].centroid.x == pytest.approx(600)
    assert r["contour"].centroid.y == pytest.approx(400)


def test_haricot_dxf_est_tourne():
    # 735 × 885 mm ne tient pas droit (885 > 760) mais tient tourné de 90°
    r = charger("haricot.dxf")
    assert r["rotation"] == 90 and r["echelle"] == 1
    assert dimensions(r["contour"]) == pytest.approx((885, 735), abs=1)
    assert PALETTE_UTILE.covers(r["contour"])


def test_grand_svg_est_reduit():
    # ellipse 1400 × 900 : trop grande dans les deux sens, réduite sans tourner
    r = charger("grand.svg")
    assert r["rotation"] == 0
    assert r["echelle"] == pytest.approx(1160 / 1400)
    assert PALETTE_UTILE.covers(r["contour"].buffer(-0.01))
    assert "réduite" in r["message"]


def test_lignes_separees_en_centimetres():
    # 4 lignes séparées forment un carré de 50 cm
    r = charger("lignes.dxf")
    assert dimensions(r["contour"]) == pytest.approx((500, 500), abs=0.01)


def test_remplir_agrandit():
    r = charger("rectangle.svg", remplir=True)
    assert r["echelle"] == pytest.approx(1160 / 280)
    assert "agrandie" in r["message"]


def test_reduction_choisit_le_meilleur_sens():
    # 3000 × 1000 : droit -> 1160/3000 = 0,39 ; tourné -> 760/3000 = 0,25
    r = placer(box(0, 0, 3000, 1000))
    assert r["rotation"] == 0
    # 1000 × 3000 : c'est en tournant qu'elle reste la plus grande
    r = placer(box(0, 0, 1000, 3000))
    assert r["rotation"] == 90
    assert r["echelle"] == pytest.approx(1160 / 3000)


def test_sans_contour_ferme():
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0 L 100 0"/></svg>'
    with pytest.raises(ValueError, match="Aucun contour fermé"):
        charger_contour(svg, "trait.svg")


def test_format_inconnu():
    with pytest.raises(ValueError, match="Format non reconnu"):
        charger_contour("", "forme.pdf")


def test_contour_est_un_polygone():
    assert isinstance(charger("grand.svg")["contour"], Polygon)
