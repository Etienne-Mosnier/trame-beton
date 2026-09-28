"""Bosses aux croisements et empilement : cas simples calculés à la main.

Réglages par défaut (ceux du .ghx) : amp = 5 mm, d = 10 mm, fuse = 0,5 mm.
"""

import pytest

from trame.moteur.croisements import (
    croisements,
    empiler,
    points_vague,
    preparer,
    trier_evenements,
    vagues,
)

# A : horizontale, B : verticale, elles se croisent en (0, 0)
A = [[(-100, 0), (100, 0)]]
B = [[(0, -100), (0, 100)]]


def arrondi(points):
    return [tuple(round(v, 6) for v in p) for p in points]


def test_croisement_simple():
    assert croisements(B[0], A) == pytest.approx([100.0])


def test_superposition_ignoree():
    # deux lignes confondues ne font pas de croisement (comme dans Rhino)
    assert croisements([(0, 0), (100, 0)], [[(50, 0), (150, 0)]]) == []


def test_deux_lignes_B_monte_sur_A():
    # B monte d'une couche (5 mm) sur A, sur 10 mm de part et d'autre
    r = empiler([A, B], active=[1])
    assert arrondi(r["waves"][1][0]) == [
        (0, -100, 0), (0, -10, 0), (0, 0, 5), (0, 10, 0), (0, 100, 0),
    ]
    assert arrondi(r["waves"][0][0]) == [(-100, 0, 0), (100, 0, 0)]   # A reste à plat
    assert r["hits"] == [pytest.approx((0, 0))]


def test_trois_series_empilement_sur_une_bosse():
    # C (y = 5) passe sur la rampe de B : B y est à 2,5 mm -> C monte de 2 couches
    C = [[(-100, 5), (100, 5)]]
    r = empiler([A, B, C], active=[1, 2])
    vague_c = arrondi(r["waves"][2][0])
    assert (0, 5, 10) in vague_c                       # sommet à 2 × 5 mm
    assert (-20, 5, 0) in vague_c and (20, 5, 0) in vague_c   # écart 2 × 10 mm
    assert r["info"][-1] == "serie 2 : 1 bosses, hauteurs [2]"


def test_trois_series_loin_de_la_bosse():
    # C (y = 50) croise B là où B est à plat -> une seule couche
    C = [[(-100, 50), (100, 50)]]
    r = empiler([A, B, C], active=[1, 2])
    assert (0, 50, 5) in arrondi(r["waves"][2][0])


def test_serie_ne_monte_pas_sur_une_serie_suivante():
    # en mode série, A (imprimée en premier) ne monte jamais, même active
    r = empiler([A, B], active=[0, 1])
    assert arrondi(r["waves"][0][0]) == [(-100, 0, 0), (100, 0, 0)]


def test_pas_de_bosse_au_raccord():
    # croisement à moins de fuse (0,5 mm) du début de la courbe : pas de bosse
    court = [[(0, -0.2), (0, 100)]]
    r = empiler([A, court], active=[1])
    assert len(r["waves"][1][0]) == 2


def test_fusion_de_deux_croisements_proches():
    # deux croisements à 0,3 mm : un seul, avec le coef le plus fort
    ev = trier_evenements([(50.0, 50.0, 1.0, True), (50.3, 50.3, 2.0, False)], d=10, fuse=0.5)
    assert ev == [(50.0, 50.3, 2.0)]


def test_bosses_qui_se_chevauchent():
    # coefs différents : on garde la plus haute
    ev = trier_evenements([(50.0, 50.0, 1.0, False), (60.0, 60.0, 2.0, False)], d=10, fuse=0.5)
    assert ev == [(60.0, 60.0, 2.0)]
    # même coef : on garde celle qui touche A
    ev = trier_evenements([(50.0, 50.0, 1.0, False), (60.0, 60.0, 1.0, True)], d=10, fuse=0.5)
    assert ev == [(60.0, 60.0, 1.0)]
    # assez loin (écart >= d × (1 + 1)) : on garde les deux
    ev = trier_evenements([(50.0, 50.0, 1.0, False), (70.0, 70.0, 1.0, True)], d=10, fuse=0.5)
    assert len(ev) == 2


def test_bosses_voisines_partagent_l_ecart():
    # deux bosses à 15 mm (coef 1 et 2) : la limite est au prorata des coefs
    ligne = [(0, 0), (100, 0)]
    vague = arrondi(points_vague(ligne, [(40.0, 40.0, 1.0), (55.0, 55.0, 2.0)], amp=5, d=10))
    assert vague == [
        (0, 0, 0), (30, 0, 0), (40, 0, 5), (45, 0, 0),
        (45, 0, 0), (55, 0, 10), (75, 0, 0), (100, 0, 0),
    ]


def test_sommets_gardes_entre_les_bosses():
    # polyligne coudée : le coude (50, 0) est gardé, car il est loin de la bosse
    coude = [[(0, 0), (50, 0), (50, 100)]]
    r = empiler([[[(-10, 80), (100, 80)]], coude], active=[1])
    assert (50, 0, 0) in arrondi(r["waves"][1][0])


def test_mode_own_hors_serie_exemple_du_script():
    # exemple du script : A=1, B=1, C=2, active = B et C
    # C x B -> C monte x2 ; C x A -> 1 ; B x A -> 1 ; B x C -> 1
    C = [[(-100, 50), (100, 50)]]
    r = vagues([A, B, C], weights=[1, 1, 2], active=[1, 2], d=5)
    assert (0, 50, 10) in arrondi(r["waves"][2][0])    # C sur B
    assert (0, 0, 5) in arrondi(r["waves"][1][0])      # B sur A
    assert (0, 50, 5) in arrondi(r["waves"][1][0])     # B sous C : poids de B = 1


def test_modes_min_max_mul():
    # exemple du script : A=1, B=2, C=2 en "min" -> B x C = 2, B x A = 1
    C = [[(-100, 50), (100, 50)]]
    r = vagues([A, B, C], weights=[1, 2, 2], mode="min", d=5)
    assert (0, 0, 5) in arrondi(r["waves"][1][0])
    assert (0, 50, 10) in arrondi(r["waves"][1][0])
    r = vagues([A, B], weights=[2, 3], mode="mul", d=1)
    assert (0, 0, 30) in arrondi(r["waves"][1][0])


def test_courbe_fermee_recousue_hors_des_bosses():
    # carré fermé traversé par A : le départ est déplacé loin des croisements
    carre = [[(-50, -50), (50, -50), (50, 50), (-50, 50), (-50, -50)]]
    r = vagues([A, carre], active=[1])
    vague = r["waves"][1][0]
    depart = vague[0]
    assert depart == vague[-1] and depart[2] == 0
    assert abs(depart[1]) > 20        # loin des croisements en y = 0
    assert sum(1 for p in vague if p[2] > 0) == 2


def test_reglages_completes_comme_le_script():
    # weights = 1,1,2,3 et active = 1,2,3 pour 3 séries (réglages du .ghx)
    reg = preparer([A, B, A], {"weights": [1, 1, 2, 3], "active": [1, 2, 3]})
    assert reg["weights"] == [1, 1, 2]
    assert reg["active"] == [1, 2]
    reg = preparer([A, B, A], {"weights": [2]})
    assert reg["weights"] == [2, 2, 2] and reg["active"] == [0, 1, 2]
