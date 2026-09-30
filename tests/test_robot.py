"""Calibration de la palette et programme URScript."""

import json
import math
import pathlib
import random

import pytest

from trame import app
from trame.robot import urscript
from trame.robot.calibration import matrice, pose_ur, repere_palette, vecteur_rotation, vers_robot

SIMU = ([-197.0, -437.0, 8.7], [-197.0, 763.0, 8.7], [-997.0, -437.0, 8.7])
CONTOURS = pathlib.Path(__file__).resolve().parent.parent / "contours"


def pose_trans(pose, point_mm):
    """Ce que fait pose_trans(palette, p[...]) sur le robot, pour une position (mm)."""
    colonnes = matrice(pose[3:])
    return [pose[i] * 1000 + sum(colonnes[j][i] * point_mm[j] for j in range(3)) for i in range(3)]


def test_calibration_simulation():
    r = repere_palette(*SIMU)
    assert r["x"] == pytest.approx([0, 1, 0])
    assert r["y"] == pytest.approx([-1, 0, 0])
    assert r["z"] == pytest.approx([0, 0, 1])
    assert vers_robot(r, (0, 0, 0)) == pytest.approx(SIMU[0])
    assert vers_robot(r, (1200, 0, 0)) == pytest.approx(SIMU[1])
    assert vers_robot(r, (0, 800, 0)) == pytest.approx(SIMU[2])


def test_calibration_palette_penchee():
    # palette qui penche de 1 mm sur le grand côté, relevé pas tout à fait d'équerre
    r = repere_palette([0, 0, 0], [1200, 0, 1], [5, 800, 0])
    assert r["z"][2] > 0.999
    assert 0.3 < r["defaut_angle"] < 0.4
    assert vers_robot(r, (1200, 0, 0)) == pytest.approx([1200, 0, 1], abs=1e-3)


def test_calibration_a_l_envers():
    with pytest.raises(ValueError, match="à l'envers"):
        repere_palette([0, 0, 0], [0, 800, 0], [1200, 0, 0])


@pytest.mark.parametrize("graine", range(20))
def test_rotation_aller_retour(graine):
    rnd = random.Random(graine)
    axe = [rnd.uniform(-1, 1) for _ in range(3)]
    n = math.sqrt(sum(a * a for a in axe))
    angle = math.pi if graine == 0 else rnd.uniform(0, math.pi)
    rv = [a / n * angle for a in axe]
    retour = matrice(vecteur_rotation(matrice(rv)))
    for c1, c2 in zip(matrice(rv), retour):
        assert c1 == pytest.approx(c2, abs=1e-9)


def test_pose_ur_comme_pose_trans():
    r = repere_palette([100, 200, 10], [1000, 800, 12], [-300, 800, 9])
    pose = pose_ur(r)
    for point in [(0, 0, 0), (1200, 0, 0), (300, 500, 25)]:
        assert pose_trans(pose, point) == pytest.approx(vers_robot(r, point), abs=1e-6)


def test_buse_verticale_vers_le_bas():
    repere = repere_palette(*SIMU)
    for angle in (0, 37, 90, 180):
        colonnes = matrice(urscript.orientation_buse(angle, repere))
        assert colonnes[2] == pytest.approx([0, 0, -1], abs=1e-9)    # axe z de la buse vers le bas


def test_buse_orientee_comme_le_ghx():
    # rotation_z = 0 : axe x de la buse le long de +X du robot, comme dans betonrobot.script
    repere = repere_palette(*SIMU)
    x_palette = matrice(urscript.orientation_buse(0, repere))[0]
    assert vers_robot(repere, x_palette) == pytest.approx(
        [SIMU[0][i] + [1, 0, 0][i] for i in range(3)], abs=1e-9)


def test_points_prepares():
    path = [(0, 0, 0), (0.01, 0, 0), (250, 0, 0), (250, 10, 5)]
    points = urscript.preparer_points(path, hauteur_buse=5, longueur_max=100)
    assert points[0] == (0, 0, 5)                      # remonté de la hauteur de buse
    assert len(points) == 1 + 3 + 1                    # doublon retiré, 250 mm coupés en 3
    assert points[-1] == (250, 10, 10)                 # le sommet de la bosse est gardé


def test_arrondis_sans_chevauchement():
    points = [(0, 0, 0), (2, 0, 0), (2, 2, 0), (100, 2, 0), (100, 50, 0)]
    r = urscript.rayons_arrondi(points, rayon=1.5)
    assert r[0] == 0 and r[-1] == 0
    assert r[1] == pytest.approx(0.9) and r[3] == 1.5


REGLAGES = {
    "outil": {"tcp": [174.4, 0, 28.86, 1.2092, 1.2092, 1.2092], "masse_kg": 0.1,
              "centre_gravite": [174.4, 0, 28.86], "rotation_z": 0},
    "impression": {"vitesse": 72, "rayon_raccord": 1.5, "acceleration": 500, "hauteur_buse": 5,
                   "hauteur_approche": 50, "vitesse_approche": 20, "longueur_max_segment": 100},
    "extrusion": {"active": True, "type": "digitale", "sortie": 3, "delai_depart": 0.5,
                  "delai_arret": 0.2, "valeur_analogique": 0},
}


def test_programme():
    path = [(100, 100, 0), (200, 100, 0), (210, 100, 5), (220, 100, 0), (300, 100, 0)]
    texte = urscript.generer(path, repere_palette(*SIMU), REGLAGES, ["Motif : essai é"])
    lignes = texte.splitlines()
    assert all(ord(c) < 128 for c in texte)
    assert "# Motif : essai e" in lignes
    assert "  set_tcp(p[0.17440, 0.0, 0.02886, 1.20920, 1.20920, 1.20920])" in lignes
    assert "    set_standard_digital_out(3, True)" in lignes
    assert sum(l.strip().startswith("movep(") for l in lignes) == 3
    assert "  movel(pt(210.00, 100.00, 10.00), a=A, v=V)" not in lignes   # bosse = movep
    assert "  movep(pt(210.00, 100.00, 10.00), a=A, v=V, r=0.00150)" in lignes
    assert "  movej(pt(100.00, 100.00, 55.00), a=1.0, v=0.3)" in lignes     # approche
    assert lignes[-1] == "trame_beton()"
    # autant de « def » que de « end »
    assert sum(l.strip().startswith("def ") for l in lignes) == sum(l.strip() == "end" for l in lignes)
    assert "popup(" not in texte


def test_extrusion_sans_sortie():
    reglages = dict(REGLAGES, extrusion=dict(REGLAGES["extrusion"], sortie=-1))
    with pytest.raises(ValueError, match="sans numéro de sortie"):
        urscript.generer([(0, 0, 0), (10, 0, 0)], repere_palette(*SIMU), reglages)


def test_export_depuis_l_apercu():
    app.calculer("exemple", "{}", (CONTOURS / "rectangle.svg").read_text(), "rectangle.svg")
    r = json.loads(app.exporter("script"))
    assert r["nom"] == "trame_exemple.script"
    assert "SIMULATION" in r["texte"] and "popup(" in r["texte"]
    assert "PROVISOIRE : hauteur de la buse" in r["texte"]
    assert "Extrusion desactivee" in r["texte"]


def test_vitesse_du_robot_reglable():
    texte = (CONTOURS / "rectangle.svg").read_text()
    lent = json.loads(app.calculer("exemple", json.dumps({"vitesse": 36}), texte, "rectangle.svg"))
    assert lent["vitesse"] == 36
    script = json.loads(app.exporter("script"))["texte"]
    assert "  V = 0.0360  # vitesse d'impression (m/s)" in script.splitlines()
    rapide = json.loads(app.calculer("exemple", json.dumps({"vitesse": 72}), texte, "rectangle.svg"))
    assert lent["duree"] == pytest.approx(2 * rapide["duree"], abs=1)
    # l'animation du robot suit la vitesse choisie
    temps = json.loads(app.robot())["temps"]
    assert temps[-2] - temps[1] == pytest.approx(rapide["longueur"] / 72, rel=0.05)
