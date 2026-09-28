"""Chemin continu : enchaînement des courbes le long du contour, couloirs, bilan CONTRÔLE."""

import math
import pathlib

import pytest
from shapely.geometry import LineString, Point, Polygon, box

from trame.contour import charger_contour
from trame.moteur.chemin import calculer_chemin, decaler_vers_exterieur

RECT = box(0, 0, 300, 200)
DOSSIER = pathlib.Path(__file__).resolve().parent.parent / "contours"


def lignes(forme, angle, pas):
    """Lignes parallèles espacées de 'pas', dans la direction 'angle', qui débordent de la forme."""
    cx, cy = forme.centroid.x, forme.centroid.y
    a = math.radians(angle)
    ux, uy = math.cos(a), math.sin(a)
    sortie = []
    for k in range(-30, 31):
        ox, oy = cx - uy * pas * k, cy + ux * pas * k
        sortie.append([(ox - 2000 * ux, oy - 2000 * uy), (ox + 2000 * ux, oy + 2000 * uy)])
    return sortie


def longueur_max_segment(path):
    return max(math.dist(a, b) for a, b in zip(path, path[1:]))


def test_une_serie_un_seul_chemin_continu():
    r = calculer_chemin([lignes(RECT, 0, 40)], RECT)
    assert r["controle"] == {"superpositions": 0, "sur_le_bord": 0, "hors_forme": 0, "sauts": 0}
    # toutes les lignes (y = 20, 60, …, 180) sont dans le chemin
    ys = {round(p[1]) for p in r["path"]}
    assert {20, 60, 100, 140, 180} <= ys
    # un seul morceau : aucune liaison ne traverse la forme
    assert longueur_max_segment(r["path"]) <= 300 + 1e-6


def test_deux_series_dans_l_ordre_avec_bosses():
    r = calculer_chemin([lignes(RECT, 0, 40), lignes(RECT, 90, 40)], RECT, active=[1])
    path = r["path"]
    assert r["controle"]["sauts"] == 0 and r["controle"]["superpositions"] == 0
    # A (horizontale) est imprimée avant B : la première bosse vient après toute la série A
    premiere_bosse = next(k for k, p in enumerate(path) if p[2] > 0)
    assert all(p[2] == 0 for p in path[:premiere_bosse])
    # B monte d'une couche (5 mm) à chacun de ses croisements avec A
    assert max(p[2] for p in path) == pytest.approx(5)
    assert len(r["hits"]) == 7 * 5 - 0     # 7 lignes B × 5 lignes A


def test_couloirs_vers_l_exterieur():
    # avec lane = 5, les liaisons de B longent un contour décalé de 5 mm vers l'extérieur
    r = calculer_chemin([lignes(RECT, 0, 40), lignes(RECT, 90, 40)], RECT, active=[1], lane=5)
    bord = RECT.exterior
    distances = {round(bord.distance(Point(p[0], p[1])), 1) for p in r["path"]
                 if not RECT.buffer(-0.5).contains(Point(p[0], p[1]))}
    assert 5.0 in distances
    assert max(distances) <= 5.0 + 1e-6            # rien au-delà du couloir de B
    assert r["controle"]["hors_forme"] == 0


def test_contour_decale_garde_sens_et_depart():
    anneau = [(0, 0), (300, 0), (300, 200), (0, 200), (0, 0)]
    decale = decaler_vers_exterieur(anneau, 10)
    assert Polygon(decale).exterior.is_ccw == Polygon(anneau).exterior.is_ccw
    assert math.dist(decale[0][:2], (0, 0)) == pytest.approx(10, abs=0.01)
    assert Polygon(decale).area == pytest.approx(320 * 220 - (400 - math.pi * 100), rel=1e-3)


def test_trois_series_sur_le_haricot():
    # cas proche du .ghx : trois séries espacées de 50 mm, B et C ondulent
    forme = charger_contour((DOSSIER / "haricot.dxf").read_text(), "haricot.dxf")["contour"]
    S = [lignes(forme, a, 50) for a in (160, 29, 135)]
    r = calculer_chemin(S, forme, weights=[1, 1, 2, 3], active=[1, 2, 3], lane=5)
    assert r["controle"]["sauts"] == 0
    assert r["controle"]["hors_forme"] == 0
    hauteurs = {round(p[2]) for p in r["path"]}
    assert hauteurs == {0, 5, 10}                  # sol, une couche, deux couches
    assert r["info"].startswith("CONTROLE :")


@pytest.mark.parametrize("route", ["series", "chrono", "zigzag", "contour"])
def test_toutes_les_routes_donnent_un_chemin(route):
    r = calculer_chemin([lignes(RECT, 0, 40), lignes(RECT, 90, 40)], RECT,
                        active=[1], route=route, lane=0)
    assert r["path"] is not None
    assert r["controle"]["hors_forme"] == 0
    assert r["controle"]["sauts"] == 0


def test_sans_contour():
    # sans contour : les lignes ne sont pas découpées, le zigzag relie leurs bouts
    S = [[[(0, 0), (100, 0)], [(0, 20), (100, 20)], [(0, 40), (100, 40)]]]
    r = calculer_chemin(S, None)
    assert "boundary : non branche" in r["info"]
    assert [p[:2] for p in r["path"]] == [
        (0, 0), (100, 0), (100, 20), (0, 20), (0, 40), (100, 40)]


def test_hop_leve_les_sauts():
    # deux morceaux éloignés sans contour : un saut, levé de 'hop'
    S = [[[(0, 0), (10, 0)], [(500, 0), (510, 0)]]]
    r = calculer_chemin(S, None, hop=15)
    assert r["controle"]["sauts"] == 1
    assert max(p[2] for p in r["path"]) == 15


def test_zigzag_false_pas_de_chemin():
    r = calculer_chemin([lignes(RECT, 0, 40)], RECT, zigzag=False)
    assert r["path"] is None
    assert len(r["waves"][0]) == 5
