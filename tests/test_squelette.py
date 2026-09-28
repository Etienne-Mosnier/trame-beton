"""Vérifie que le squelette du projet est en place."""

import importlib
import pathlib
import tomllib

RACINE = pathlib.Path(__file__).resolve().parent.parent

MODULES = [
    "trame",
    "trame.parametres",
    "trame.outils",
    "trame.contour",
    "trame.controles",
    "trame.app",
    "trame.moteur.croisements",
    "trame.moteur.chemin",
    "trame.export.dxf",
    "trame.export.svg",
    "trame.robot.urscript",
    "trame.robot.calibration",
    "trame.robot.atteignabilite",
    "trame.robot.cinematique",
    "trame.robot.alertes",
]


def test_modules_importables():
    for nom in MODULES:
        importlib.import_module(nom)


def test_shapely_disponible():
    from shapely.geometry import LineString

    a = LineString([(0, 0), (10, 10)])
    b = LineString([(0, 10), (10, 0)])
    assert a.intersects(b)


def test_config_cellule_lisible():
    with open(RACINE / "config" / "cellule.toml", "rb") as f:
        config = tomllib.load(f)
    for section in ["robot", "outil", "impression", "extrusion", "palette", "calibration"]:
        assert section in config
    assert config["palette"]["longueur"] == 1200.0
    assert config["palette"]["largeur"] == 800.0
    # l'extrusion reste désactivée tant que la sortie n'est pas connue
    assert config["extrusion"]["active"] is False


def test_fichiers_de_reference_presents():
    for nom in ["betonrobot.ghx", "vagues_ghx.py", "betonrobot.script", "chemin_script_xyz.csv"]:
        assert (RACINE / "reference" / nom).is_file()
