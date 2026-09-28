"""Alertes robot et placement de la palette."""

import json
import math
import pathlib

import numpy as np
import pytest

from trame import app
from trame.robot import alertes
from trame.robot.calibration import repere_palette, vers_robot
from trame.robot.cinematique import DEPART, matrice_pose

RACINE = pathlib.Path(__file__).resolve().parent.parent
TCP = matrice_pose([0.1744, 0, 0.02886, 1.2092, 1.2092, 1.2092])
SIMU = ([-197.0, -437.0, 8.7], [-197.0, 763.0, 8.7], [-997.0, -437.0, 8.7])


def vers_palette(repere):
    Rp = np.array([repere["x"], repere["y"], repere["z"]])
    M = np.eye(4)
    M[:3, :3] = Rp
    M[:3, 3] = -Rp @ np.array(repere["origine"])
    return M


def statuts(liste):
    return {a["titre"]: a["statut"] for a in liste}


def test_pose_du_script_sans_collision():
    M = vers_palette(repere_palette(*SIMU))
    assert alertes.collisions(DEPART, TCP, M, (1200, 800)) == set()


def test_bras_dans_la_palette():
    # palette remontée de 30 cm : le bras et la buse passent dedans
    M = vers_palette(repere_palette(*[[p[0], p[1], p[2] + 300] for p in SIMU]))
    touches = alertes.collisions(DEPART, TCP, M, (1200, 800))
    assert "buse / palette" in touches


def test_singularites():
    M = vers_palette(repere_palette(*SIMU))
    q_poignet = list(DEPART)
    q_poignet[4] = 0.01                        # poignet aligné
    q_coude = list(DEPART)
    q_coude[2] = 0.02                          # coude tendu
    liste = alertes.analyser([DEPART, q_poignet, q_coude], [], [(0, 0, 0)] * 3, TCP, M, (1200, 800))
    s = statuts(liste)
    assert s["Poignet jamais aligné"] == "alerte"
    assert s["Coude jamais tendu"] == "alerte"
    poignet = next(a for a in liste if a["titre"] == "Poignet jamais aligné")
    assert poignet["indices"] == [1]


def test_saut_et_limites():
    M = vers_palette(repere_palette(*SIMU))
    q_saut = list(DEPART)
    q_saut[0] += math.radians(45)
    q_limite = list(DEPART)
    q_limite[2] = math.radians(175)            # coude à 5° de sa limite (180°)
    s = statuts(alertes.analyser([DEPART, q_saut, q_limite], [], [(0, 0, 0)] * 3, TCP, M, (1200, 800)))
    assert s["Mouvement régulier du bras"] == "alerte"
    assert s["Articulations loin de leurs limites"] == "alerte"


def test_hors_portee_est_une_erreur():
    M = vers_palette(repere_palette(*SIMU))
    liste = alertes.analyser([DEPART, DEPART], [1], [(0, 0, 0), (5, 5, 0)], TCP, M, (1200, 800))
    a = next(a for a in liste if a["titre"] == "Tout est à portée du robot")
    assert a["statut"] == "erreur" and a["points"] == [(5, 5)]


def test_points_de_placement():
    c = app.points_placement(-197, -437, 8.7, 90)
    for cle, attendu in zip(("origine", "grand_cote", "petit_cote"), SIMU):
        assert c[cle] == pytest.approx(attendu)


def test_placement_et_zone_atteignable():
    app.calculer("exemple", "{}", (RACINE / "contours" / "haricot.dxf").read_text(), "haricot.dxf")
    proche = json.loads(app.placement(""))
    assert proche["atteignable"] > 90
    loin = json.loads(app.placement(json.dumps({"x": -2500, "y": -437, "z": 8.7, "rotation": 90})))
    assert loin["atteignable"] == 0
    assert loin["calibration"]["origine"] == [-2500, -437, 8.7]
    # le placement choisi sert au robot et au programme, puis on revient à la simulation
    r = json.loads(app.robot())
    assert len(r["hors_portee"]) == len(r["points"])
    assert "-2.50000" in json.loads(app.exporter("script"))["texte"]
    json.loads(app.placement(""))
    assert json.loads(app.robot())["hors_portee"] == []


def test_robot_renvoie_les_alertes():
    app.calculer("exemple", "{}", (RACINE / "contours" / "haricot.dxf").read_text(), "haricot.dxf")
    r = json.loads(app.robot())
    s = statuts(r["alertes"])
    assert s["Tout est à portée du robot"] == "ok"
    assert s["Pas de collision"] == "ok"
    # buse orientée comme le .ghx : poignet proche de l'alignement par endroits
    assert s["Poignet jamais aligné"] == "alerte"
