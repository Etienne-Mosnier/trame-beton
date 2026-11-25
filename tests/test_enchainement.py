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
    ligne = r["lignes"][0][0]
    # le dessin, intact, entre un prolongement d'entrée et un de sortie (17 mm, à hauteur de
    # cordon : la buse arrive de côté et repart sans s'arrêter sur le cordon)
    assert [p[:2] for p in ligne[1:-1]] in ([(0, 0), (100, 0), (100, 100)], [(100, 100), (100, 0), (0, 0)])
    assert math.dist(ligne[0][:2], ligne[1][:2]) == pytest.approx(17) and math.dist(ligne[-2][:2], ligne[-1][:2]) == pytest.approx(17)
    assert all(p[2] == 0 for p in ligne)
    # extrusion continue : le parcours commence et finit à côté du dessin, buse levée
    assert r["path"][0] == r["depart"]["point"] and r["path"][-1] == r["fin"]["point"]
    assert r["depart"]["point"][2] == 50 and r["depart"]["libre"] and r["fin"]["libre"]


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
    ligne = r["lignes"][0][0]
    assert max(p[2] for p in ligne) == AMP
    # au croisement (100, 0) : le second passage est à AMP
    assert hauteur_a(ligne, 100, 0) == AMP


def test_courbe_fermee_arretee_avant_son_depart():
    cercle = [(100 * math.cos(2 * math.pi * k / 72), 100 * math.sin(2 * math.pi * k / 72)) for k in range(73)]
    r = calculer_trace([[cercle]], largeur_cordon=10, amp=AMP)
    ligne = r["lignes"][0][0]
    # la buse s'arrête une largeur de cordon avant de revenir à son départ (entre les
    # prolongements d'entrée et de sortie)
    assert math.dist(ligne[1][:2], ligne[-2][:2]) == pytest.approx(10, abs=1)
    assert max(p[2] for p in ligne) == 0                           # elle ne repasse pas dessus


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


def test_une_boucle_fermee_commence_pres_du_calque_suivant():
    # A : un cercle (il peut commencer n'importe où) ; B part de sa droite. A doit commencer et
    # finir à droite : une liaison courte, qui ne passe pas par-dessus le cercle
    cercle = [(100 * math.cos(2 * math.pi * k / 72), 100 * math.sin(2 * math.pi * k / 72)) for k in range(73)]
    r = calculer_trace([[cercle], [[(130, 0), (300, 0)]]], largeur_cordon=10, amp=AMP)
    assert len(r["liaisons"]) == 1
    liaison = [p[:2] for p in r["liaisons"][0]["points"]]
    assert math.dist(liaison[0], liaison[-1]) < 40
    assert r["liaisons"][0]["survols"] == 0


def test_la_fin_est_au_bord_du_dessin():
    # spirale tracée du bord vers le centre : le moteur l'imprime du centre vers le bord, pour que
    # la buse sorte du dessin sans passer au-dessus du béton (il coule encore à la fin)
    spirale = [((30 + 60 * t / (2 * math.pi)) * math.cos(t), (30 + 60 * t / (2 * math.pi)) * math.sin(t))
               for t in [k * 2 * math.pi / 72 for k in range(72 * 3 + 1)]]
    spirale.reverse()
    r = calculer_trace([[spirale]], largeur_cordon=10, amp=AMP)
    ligne = r["lignes"][0][0]
    fin_du_dessin = ligne[-2][:2]                 # avant le prolongement de sortie
    assert math.hypot(*fin_du_dessin) > 200
    assert r["fin"]["libre"]


def test_liaison_par_dessus_le_beton_comptee():
    # B est enfermé dans un carré imprimé avant lui ; C est dehors : la liaison de B à C passe
    # forcément par-dessus le carré
    carre = [(0, 0), (300, 0), (300, 300), (0, 300), (0, 0)]
    r = calculer_trace([[carre], [[(140, 150), (160, 150)]], [[(400, 0), (400, 300)]]], largeur_cordon=10, amp=AMP)
    assert [l["survols"] for l in r["liaisons"]] == [0, 1]
    assert r["fin"]["libre"]


def test_couches_empilees():
    A = [[(0, 100), (400, 100)]]
    B = [[(200, 0), (200, 300)]]
    r = calculer_trace([A, B], largeur_cordon=10, amp=AMP, couches=3)
    # au croisement : A1 0, B1 5, A2 10, B2 15, A3 20, B3 25
    assert max(p[2] for serie in r["waves"] for w in serie for p in w) == pytest.approx(5 * AMP)
    # loin du croisement, chaque couche repose sur la précédente
    hauteurs = [hauteur_a(w, 50, 100) for w in r["waves"][0]]
    assert sorted(round(h, 3) for h in hauteurs if h is not None) == [0, AMP, 2 * AMP]
    assert r["jumps"] == []


# --- pauses ---------------------------------------------------------------------------

from shapely.geometry import LineString as Ligne, MultiLineString, Point as Pt

from trame.moteur.deplacements import chemin_libre, obstacles


def survole(trajet, imprime, rayon):
    """Le trajet à vide (sans ses deux bouts, au-dessus des cordons qu'il quitte et rejoint)
    passe-t-il au-dessus d'un cordon imprimé ?"""
    zone = MultiLineString([Ligne([p[:2] for p in poly]) for poly in imprime]).buffer(rayon - 0.5)
    milieu = [p[:2] for p in trajet[2:-2]]
    return len(milieu) > 1 and Ligne(milieu).intersects(zone)


def test_pause_entre_deux_calques():
    A = [[(0, 100), (400, 100)]]
    B = [[(200, 0), (200, 300)]]
    r = calculer_trace([A, B], largeur_cordon=10, amp=AMP, pauses=[True, False], levee=50)
    assert len(r["pauses"]) == 1 and len(r["deplacements"]) == 1 and r["liaisons"] == []
    pause = r["pauses"][0]
    assert pause["libre"] and pause["calque"] == 0 and pause["couche"] == 1
    # le parcours reste d'un seul tenant (extrusion continue) et passe par le point d'attente
    assert r["path"][pause["indice"]] == pause["point"]
    trajet = r["deplacements"][0]
    # la buse sort du béton à hauteur de cordon, puis monte de 50 mm et va attendre
    assert trajet[0][2] == 0 and trajet[1][:2] == trajet[0][:2] and trajet[1][2] == pytest.approx(50)
    assert math.dist(trajet[0][:2], (0, 100)) > 15 and math.dist(trajet[0][:2], (400, 100)) > 15
    # partie levée : jamais au-dessus du calque A (un cordon d'écart pour le béton qui tombe)
    assert not survole(trajet, r["lignes"][0], 15)
    # le point d'attente est loin du dessin : le tas de béton ne touche pas la pièce
    assert Ligne([(0, 100), (400, 100)]).distance(Pt(pause["point"][:2])) > 60
    assert hauteur_a(r["lignes"][1][0], 200, 100) == AMP          # B passe toujours par-dessus A


def test_sortie_d_une_spirale_par_le_couloir():
    # spirale imprimée du bord vers le centre : la sortie suit le couloir entre les tours
    spirale = [((30 + 60 * t / (2 * math.pi)) * math.cos(t), (30 + 60 * t / (2 * math.pi)) * math.sin(t))
               for t in [k * 2 * math.pi / 72 for k in range(72 * 3 + 1)]]
    spirale.reverse()
    zone = obstacles([spirale], 10)
    trajet = chemin_libre(spirale[-1], (400, 0), zone, (-400, -400, 400, 400), 5)
    assert trajet is not None and len(trajet) > 3                 # pas en ligne droite
    assert not Ligne(trajet[1:]).intersects(zone.buffer(-0.5))


def test_pause_sans_passage_signalee():
    # le calque B est enfermé dans un carré imprimé : impossible d'y entrer sans survoler
    carre = [[(0, 0), (300, 0), (300, 300), (0, 300), (0, 5)]]
    dedans = [[(140, 150), (160, 150)]]
    r = calculer_trace([carre, dedans], largeur_cordon=10, amp=AMP, pauses=[True, False])
    assert r["pauses"][0]["libre"] is False
    assert r["controle"]["pauses_bloquees"] == 1


def test_pause_entre_deux_couches():
    A = [[(0, 100), (400, 100)]]
    B = [[(200, 0), (200, 300)]]
    r = calculer_trace([A, B], largeur_cordon=10, amp=AMP, couches=2, pauses=[False, True])
    assert len(r["pauses"]) == 1 and r["pauses"][0]["couche"] == 1 and r["pauses"][0]["calque"] == 1
    # la couche 2 repose sur la couche 1 malgré la pause
    hauteurs = [hauteur_a(w, 50, 100) for w in r["waves"][0]]
    assert sorted(h for h in hauteurs if h is not None) == [0, AMP]


def test_le_beton_tombe_pendant_une_pause_compte():
    # le béton coule pendant le trajet d'une pause : une ligne qui passe ensuite dessus monte
    from trame.moteur.enchainement import poser
    morceaux = [{"calque": 0, "nature": "ligne", "points": [(0, 0), (100, 0)]},
                {"calque": 0, "nature": "trajet", "points": [(100, 0), (150, 0), (150, 200), (0, 200)]},
                {"calque": 1, "nature": "ligne", "points": [(0, 200), (0, 260), (75, 260), (75, 100)]}]
    poses = poser(morceaux, AMP, 10)
    assert hauteur_a(poses[2]["points"], 75, 200) == AMP


# --- bosses : largeur du cordon, cordons serrés, trajets levés -------------------------


def test_bosse_sur_toute_la_largeur_du_cordon():
    # B reste en haut tant qu'il est au-dessus du cordon A (10 mm de large), pas seulement sur son axe
    r = calculer_trace([[[(0, 100), (400, 100)]], [[(200, 0), (200, 300)]]], largeur_cordon=10, amp=AMP)
    b = r["lignes"][1][0]
    assert hauteur_a(b, 200, 96) == AMP and hauteur_a(b, 200, 104) == AMP
    assert hauteur_a(b, 200, 60) == 0


def test_cordons_serres_franchis_d_un_coup():
    # deux cordons de A à 18 mm l'un de l'autre : B les franchit d'un seul plateau, sans redescendre
    serres = calculer_trace([[[(0, 100), (400, 100)], [(400, 118), (0, 118)]], [[(200, 0), (200, 300)]]],
                            largeur_cordon=10, amp=AMP)
    b = serres["lignes"][1][0]
    assert all(hauteur_a(b, 200, y) == AMP for y in range(96, 123, 2))
    # à 80 mm l'un de l'autre : deux bosses, et B redescend au sol entre les deux
    ecartes = calculer_trace([[[(0, 100), (400, 100)], [(400, 180), (0, 180)]], [[(200, 0), (200, 300)]]],
                             largeur_cordon=10, amp=AMP)
    b = ecartes["lignes"][1][0]
    assert hauteur_a(b, 200, 100) == AMP and hauteur_a(b, 200, 180) == AMP and hauteur_a(b, 200, 140) == 0


def test_le_trajet_leve_ne_pose_pas_de_beton():
    # le trajet buse levée d'une pause passe là où B sera imprimé ensuite : B ne monte pas dessus
    from trame.moteur.enchainement import poser
    morceaux = [{"calque": 0, "couche": 1, "nature": "ligne", "points": [(0, 0), (100, 0)]},
                {"calque": 0, "couche": 1, "nature": "pause", "route": [(100, 0), (150, 100), (0, 100)], "points": []},
                {"calque": 1, "couche": 1, "nature": "ligne", "points": [(50, 150), (50, 50)]}]
    poses = poser(morceaux, AMP, 10)
    assert max(p[2] for p in poses[2]["points"]) == 0
