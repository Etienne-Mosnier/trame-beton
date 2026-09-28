"""La page web : liste des fichiers copiés dans Pyodide."""

import importlib.util
import pathlib

RACINE = pathlib.Path(__file__).resolve().parent.parent


def charger_construire():
    spec = importlib.util.spec_from_file_location("construire", RACINE / "web" / "construire.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_liste_complete():
    # tous les modules de trame/, tous les motifs, les contours exemples et la config
    fichiers = charger_construire().lister()
    for p in (RACINE / "trame").rglob("*.py"):
        assert p.relative_to(RACINE).as_posix() in fichiers
    for p in (RACINE / "motifs").rglob("motif.py"):
        assert p.relative_to(RACINE).as_posix() in fichiers
    assert "config/cellule.toml" in fichiers
    assert "contours/haricot.dxf" in fichiers
    assert not any("__pycache__" in f for f in fichiers)
