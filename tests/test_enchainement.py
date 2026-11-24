"""Moteur des dessins en calques (trame/moteur/enchainement.py) : enchaînement et bosses."""

import math

import pytest

from trame.moteur.enchainement import calculer_trace, enchainer

AMP = 5.0


def hauteur_a(points, x, y, rayon=1.5):
    """Hauteur la plus grande du chemin près du point (x, y), vu de dessus (le long des
    segments : le moteur ne garde pas les points alignés). None si le chemin n'y passe pas."""
    hauteurs = []
    for a, b in zip(points, points[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        long2 = dx * dx + dy * dy
        t = 0.0 if long2 == 0 else max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / long2))
        if math.hypot(a[0] + t * dx - x, a[1] + t * dy - y) <= rayon:
            hauteurs.append(a[2] + t * (b[2] - a[2]))
    return max(hauteurs, default=None)


def test_une_ligne_par_calque_gardee_telle_quelle():
    A = [[(0, 0), (100, 0), (100, 100)]]
    r = calculer_trace([A], largeur_cordon=10, amp=AMP)
    assert r["liaisons"] == []
    assert [p[:2] for p in r["path"]] in ([(0, 0), (100, 0), (100, 100)], [(100, 100), (100, 0), (0, 0)])
    assert all(p[2] == 0 for p in r["path"])


def test_le_calque_suivant_passe_par_dessus():
    A = [[(0, 100), (400, 100)]]
    B = [[(200, 0), (200, 300)]]
    r = calculer_trace([A, B], largeur_cordon=10, amp=AMP)
    assert all(p[2] == 0 for p in r["lignes"][0][0])               # A, imprimé en premier : à plat
    assert hauteur_a(r["lignes"][1][0], 200, 100) == AMP           # B monte d'une couche sur A
    assert hauteur_a(r["lignes"][1][0], 200, 250) == 0             # et redescend ensuite
    # une seule liaison, de la fin de A au début de B (départ et sens choisis au plus court)
    assert len(r["liaisons"]) == 1 and not r["liaisons"][0]["dans_calque"]
    assert r["jumps"] == [] and r["controle"]["sauts"] == 0


def test_ordre_inverse_inverse_les_bosses():
    A = [[(0, 100), (400, 100)]]
    B = [[(200, 0), (200, 300)]]
    r = calculer_trace([B, A], largeur_cordon=10, amp=AMP)
    assert all(p[2] == 0 for p in r["lignes"][0][0])               # B d'abord : à plat
    assert hauteur_a(r["lignes"][1][0], 200, 100) == AMP           # A passe par-dessus


def test_une_boucle_passe_par_dessus_son_propre_debut():
    # une seule ligne qui se recroise (boucle) : le second passage monte
    boucle = [(0, 0), (200, 0), (200, 100), (100, 100), (100, -100)]
    r = calculer_trace([[boucle]], largeur_cordon=10, amp=AMP)
    z = [p[2] for p in r["path"]]
    assert max(z) == AMP
    # au croisement (100, 0) : le premier passage reste à plat, le second est à AMP
    premiers = [p for p in r["path"][:3] if p[2] == 0]
    assert premiers and hauteur_a(r["path"], 100, 0) == AMP


def test_courbe_fermee_arretee_avant_son_depart():
    cercle = [(100 * math.cos(2 * math.pi * k / 72), 100 * math.sin(2 * math.pi * k / 72)) for k in range(73)]
    r = calculer_trace([[cercle]], largeur_cordon=10, amp=AMP)
    debut, fin = r["path"][0], r["path"][-1]
    # la buse s'arrête une largeur de cordon avant de revenir à son départ
    assert math.dist(debut[:2], fin[:2]) == pytest.approx(10, abs=1)
    assert max(p[2] for p in r["path"]) == 0                       # elle ne repasse pas dessus


def test_calque_en_plusieurs_morceaux_relie_au_plus_court():
    A = [[(0, 0), (100, 0)], [(0, 40), (100, 40)], [(0, 80), (100, 80)]]
    r = calculer_trace([A], largeur_cordon=10, amp=AMP)
    assert r["controle"]["liaisons_dans_calque"] == 2
    # zigzag : chaque liaison va au bout le plus proche (40 mm), jamais en travers
    assert all(math.dist(*[p[:2] for p in l["points"]]) == pytest.approx(40) for l in r["liaisons"])


def test_depart_au_plus_court():
    # A finit tout près du début de B, si on le prend dans le bon sens
    A = [[(500, 0), (0, 0)]]
    B = [[(510, 10), (510, 300)]]
    morceaux = enchainer([A, B], ecart=10)
    liaison = next(m for m in morceaux if m["nature"] == "liaison")
    assert math.dist(*liaison["points"]) == pytest.approx(math.hypot(10, 10))


def test_couches_empilees():
    A = [[(0, 100), (400, 100)]]
    B = [[(200, 0), (200, 300)]]
    r = calculer_trace([A, B], largeur_cordon=10, amp=AMP, couches=3)
    # au croisement : A1 0, B1 5, A2 10, B2 15, A3 20, B3 25
    assert max(p[2] for p in r["path"]) == pytest.approx(5 * AMP)
    # loin du croisement, chaque couche repose sur la précédente
    hauteurs = [hauteur_a(w, 50, 100) for w in r["waves"][0]]
    assert sorted(round(h, 3) for h in hauteurs if h is not None) == [0, AMP, 2 * AMP]
    assert r["jumps"] == []
