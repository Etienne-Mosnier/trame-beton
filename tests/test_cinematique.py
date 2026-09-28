"""Cinématique de l'UR10e, vérifiée sur le programme d'origine (8 838 poses)."""

import csv
import json
import math
import pathlib
import re

import numpy as np
import pytest

from trame import app
from trame.robot.calibration import vers_robot
from trame.robot.cinematique import directe, inverse, matrice_pose, plus_proche, trajectoire

RACINE = pathlib.Path(__file__).resolve().parent.parent
TCP = matrice_pose([0.1744, 0, 0.02886, 1.2092, 1.2092, 1.2092])


@pytest.fixture(scope="module")
def script():
    texte = (RACINE / "reference" / "betonrobot.script").read_text()
    angles = [list(map(float, m.group(1).split(","))) for m in re.finditer(r"movej\(\[([^\]]+)\]", texte)]
    lignes = list(csv.reader(open(RACINE / "reference" / "chemin_script_xyz.csv")))[1:]
    return angles, [tuple(map(float, r)) for r in lignes]


def test_directe_retrouve_le_csv(script):
    angles, positions = script
    assert len(angles) == len(positions) == 8838
    for q, p in zip(angles, positions):
        buse = (directe(q) @ TCP)[:3, 3] * 1000
        assert np.linalg.norm(buse - np.array(p)) < 0.01      # mm


def test_inverse_retrouve_les_angles_du_script(script):
    angles, _ = script
    for q in angles:
        solutions = inverse(directe(q))
        assert len(solutions) == 8
        ecart = min(max(abs(math.atan2(math.sin(s[i] - q[i]), math.cos(s[i] - q[i]))) for i in range(6))
                    for s in solutions)
        assert ecart < 1e-9


def test_trajectoire_continue(script):
    angles, _ = script
    suivis, hors = trajectoire([directe(q) for q in angles], angles[0])
    assert hors == []
    assert max(max(abs(a[i] - q[i]) for i in range(6)) for a, q in zip(suivis, angles)) < 1e-9


def test_toutes_les_solutions_sont_justes():
    T = directe([0.3, -1.2, 1.5, -1.9, -1.4, 0.7])
    for s in inverse(T):
        assert np.abs(directe(s) - T).max() < 1e-9


def test_hors_de_portee():
    T = np.eye(4)
    T[:3, 3] = [2.0, 0.0, 0.2]          # 2 m : l'UR10e atteint 1,3 m
    assert inverse(T) == []
    assert plus_proche([], [0] * 6) is None


def test_continuite_des_tours():
    # un angle de 179° suivi de -179° : on passe à 181° plutôt que de faire un tour
    q = plus_proche([[math.radians(-179), 0, 0, 0, 0, 0]], [math.radians(179), 0, 0, 0, 0, 0])
    assert math.degrees(q[0]) == pytest.approx(181)


def test_robot_de_l_apercu():
    app.calculer("exemple", "{}", (RACINE / "contours" / "haricot.dxf").read_text(), "haricot.dxf")
    r = json.loads(app.robot())
    assert r["hors_portee"] == []
    assert len(r["angles"]) == len(r["points"]) == len(r["temps"]) == len(r["series"])
    assert r["simulation"] is True
    assert r["series"][1] == 0 and r["series"][-2] == 2          # A au début, C à la fin
    # la buse est bien au point voulu (hauteur de buse comprise)
    repere, _ = app.calibration()
    hb = app.reglages_impression()["hauteur_buse"]
    for k in (1, len(r["points"]) // 2, len(r["points"]) - 2):
        p = r["points"][k]
        voulu = vers_robot(repere, (p[0], p[1], p[2] + hb))
        buse = (directe(r["angles"][k]) @ TCP)[:3, 3] * 1000
        assert buse == pytest.approx(voulu, abs=0.05)
