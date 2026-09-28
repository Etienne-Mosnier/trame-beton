"""Vérifie chaque motif de motifs/ : forme du fichier, réglages, imports et calcul complet.

Ce test tourne sur tous les dossiers de motifs, y compris ceux des groupes :
un motif qui ne respecte pas les règles d'AGENTS.md le fait échouer.
"""

import ast
import importlib
import pathlib

import pytest
from shapely.geometry import LineString, box

from trame.moteur.chemin import calculer_chemin
from trame.parametres import Parametre, valeurs

RACINE = pathlib.Path(__file__).resolve().parent.parent
MOTIFS = sorted(p.parent.name for p in (RACINE / "motifs").glob("*/motif.py"))
IMPORTS_AUTORISES = {"math", "shapely", "trame.outils", "trame.parametres"}

# palette avec une marge de 20 mm, et une forme plus petite pour varier
FORMES = [box(20, 20, 1180, 780), box(300, 200, 700, 500)]


def charger(nom):
    return importlib.import_module("motifs.%s.motif" % nom)


def test_il_y_a_au_moins_l_exemple():
    assert "exemple" in MOTIFS


@pytest.mark.parametrize("nom", MOTIFS)
def test_forme_du_fichier(nom):
    motif = charger(nom)
    assert isinstance(motif.NOM, str) and motif.NOM
    assert isinstance(motif.PARAMETRES, dict)
    assert callable(motif.series)


@pytest.mark.parametrize("nom", MOTIFS)
def test_parametres_complets(nom):
    for cle, parametre in charger(nom).PARAMETRES.items():
        assert isinstance(parametre, Parametre), cle
        assert parametre.aide, "le paramètre « %s » n'a pas d'aide" % cle
        assert parametre.mini <= parametre.valeur <= parametre.maxi, cle


@pytest.mark.parametrize("nom", MOTIFS)
def test_imports_autorises(nom):
    # seulement math, shapely, trame.outils et trame.parametres (règle d'AGENTS.md)
    arbre = ast.parse((RACINE / "motifs" / nom / "motif.py").read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            modules = [a.name for a in noeud.names]
        elif isinstance(noeud, ast.ImportFrom):
            modules = [noeud.module or ""]
        else:
            continue
        for module in modules:
            racine = module.split(".")[0]
            assert module in IMPORTS_AUTORISES or racine in ("math", "shapely"), \
                "import interdit dans un motif : %s" % module


@pytest.mark.parametrize("nom", MOTIFS)
@pytest.mark.parametrize("reglage", ["defaut", "mini", "maxi"])
def test_series_valides(nom, reglage):
    motif = charger(nom)
    choix = {cle: getattr(p, "valeur" if reglage == "defaut" else reglage)
             for cle, p in motif.PARAMETRES.items()}
    for forme in FORMES:
        S = motif.series(forme, valeurs(motif.PARAMETRES, choix))
        assert 2 <= len(S) <= 5, "il faut de 2 à 5 séries"
        for serie in S:
            assert serie, "une série est vide"
            assert all(isinstance(c, LineString) for c in serie)


@pytest.mark.parametrize("nom", MOTIFS)
def test_calcul_complet(nom):
    motif = charger(nom)
    forme = FORMES[0]
    S = motif.series(forme, valeurs(motif.PARAMETRES))
    r = calculer_chemin([[list(c.coords) for c in serie] for serie in S], forme)
    assert r["path"] is not None
    assert r["controle"]["hors_forme"] == 0
