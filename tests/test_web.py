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
    # tous les modules de trame/, les dessins d'exemple et la config
    fichiers = charger_construire().lister()
    for p in (RACINE / "trame").rglob("*.py"):
        assert p.relative_to(RACINE).as_posix() in fichiers
    assert "config/cellule.toml" in fichiers
    assert "dessins/vagues.svg" in fichiers and "dessins/spirales.dxf" in fichiers
    assert "gabarits/gabarit_palette.dxf" in fichiers and "gabarits/gabarit_palette.svg" in fichiers
    assert not any("__pycache__" in f for f in fichiers)
