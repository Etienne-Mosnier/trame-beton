"""Vérifie que la page web connaît tous les fichiers Python de trame/."""

import json
import pathlib

RACINE = pathlib.Path(__file__).resolve().parent.parent


def test_fichiers_json_a_jour():
    # web/fichiers.json liste les fichiers copiés dans Pyodide :
    # un module oublié dans cette liste manquerait dans le navigateur.
    liste = json.loads((RACINE / "web" / "fichiers.json").read_text(encoding="utf-8"))
    sur_disque = sorted(
        p.relative_to(RACINE).as_posix() for p in (RACINE / "trame").rglob("*.py")
    )
    assert sorted(liste) == sur_disque


def test_verifier_hors_navigateur():
    from trame.app import verifier

    resultat = json.loads(verifier())
    assert resultat["ok"]
    assert resultat["croisement"] == [50.0, 50.0]
