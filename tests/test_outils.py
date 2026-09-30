"""Outils pour les motifs et paramètres."""

import math

import pytest
from shapely.geometry import box

from trame import outils
from trame.parametres import Case, Choix, Liste, Parametre, Point, Points, valeurs

FORME = box(0, 0, 400, 200)


def test_lignes_paralleles_couvrent_la_forme():
    lignes = outils.lignes_paralleles(FORME, angle=0, espacement=50)
    ys = sorted(round(l.coords[0][1]) for l in lignes if l.intersects(FORME))
    assert ys == [0, 50, 100, 150, 200]
    assert all(l.length > 400 for l in lignes)


def test_lignes_paralleles_angle():
    ligne = outils.lignes_paralleles(FORME, angle=90, espacement=50)[0]
    (x0, y0), (x1, y1) = ligne.coords
    assert x0 == pytest.approx(x1)            # 90° = lignes verticales


def test_ondes():
    onde = outils.ondes(FORME, angle=0, espacement=50, amplitude=10, longueur_onde=100)[5]
    ys = [p[1] for p in onde.coords]
    assert max(ys) - min(ys) == pytest.approx(20, abs=0.1)


def test_cercles_et_rayons():
    cercles = outils.cercles_concentriques(FORME, espacement=50)
    assert cercles[0].is_closed
    assert cercles[1].length == pytest.approx(2 * math.pi * 100, rel=1e-3)
    assert len(outils.lignes_rayonnantes(FORME, nombre=12)) == 12


def test_valeurs_bornees():
    P = {"espacement": Parametre(50, mini=20, maxi=150, unite="mm", aide="écart")}
    assert valeurs(P) == {"espacement": 50}
    assert valeurs(P, {"espacement": 500, "inconnu": 3}) == {"espacement": 150}
    assert P["espacement"].pas == 1
    assert Parametre(0.5, mini=0.0, maxi=1.0).pas == pytest.approx(0.01)


def test_point():
    P = {"attraction": Point(400, 300, aide="point"), "force": Parametre(30, mini=0, maxi=80)}
    assert valeurs(P) == {"attraction": (400.0, 300.0), "force": 30}
    # valeur venue de l'aperçu (liste JSON), ramenée sur la palette
    assert valeurs(P, {"attraction": [1500, -20]})["attraction"] == (1200.0, 0.0)
    assert P["attraction"].vers_dict() == {"type": "point", "valeur": [400.0, 300.0], "aide": "point"}


def test_choix_case_points():
    P = {
        "forme": Choix("vagues", ["vagues", "zigzag"], aide="forme"),
        "inverser": Case(False, aide="sens"),
        "attractions": Points([(400, 400), (800, 400)], mini=1, maxi=3, aide="points"),
    }
    assert valeurs(P) == {"forme": "vagues", "inverser": False, "attractions": [(400.0, 400.0), (800.0, 400.0)]}
    v = valeurs(P, {"forme": "spirale", "inverser": True,
                    "attractions": [[100, 100], [2000, 50], [300, 300], [500, 500]]})
    assert v["forme"] == "vagues"                                   # option inconnue : défaut
    assert v["inverser"] is True
    assert v["attractions"] == [(100.0, 100.0), (1200.0, 50.0), (300.0, 300.0)]   # 3 au plus, sur la palette
    assert valeurs(P, {"attractions": []})["attractions"] == [(400.0, 400.0)]    # 1 au moins
    assert P["attractions"].vers_dict()["type"] == "points"


def test_liste():
    P = {"directions": Liste([160, 29, 135], mini=2, maxi=5, bornes=(0, 180), unite="°", element="Série")}
    assert valeurs(P) == {"directions": [160, 29, 135]}
    assert valeurs(P, {"directions": [10, 200, 30, 40, 50, 60]})["directions"] == [10, 180, 30, 40, 50]
    assert valeurs(P, {"directions": [45]})["directions"] == [45, 160]            # 2 au moins
    assert P["directions"].vers_dict()["type"] == "liste"


def test_liste_a_plusieurs_champs():
    P = {"series": Liste([{"angle": 160, "espacement": 50}, {"angle": 29, "espacement": 50}], mini=2, maxi=3,
                         champs={"angle": Parametre(90, mini=0, maxi=180), "espacement": Parametre(50, mini=20, maxi=150)})}
    v = valeurs(P, {"series": [{"angle": 200, "espacement": 10}, {"angle": 45}, {}, {"angle": 1}]})["series"]
    assert v == [{"angle": 180, "espacement": 20}, {"angle": 45, "espacement": 50}, {"angle": 90, "espacement": 50}]
    d = P["series"].vers_dict()
    assert set(d["champs"]) == {"angle", "espacement"} and d["champs"]["angle"]["maxi"] == 180
