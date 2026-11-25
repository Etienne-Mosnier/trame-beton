"""Contrôles d'imprimabilité d'un dessin : chaque contrôle détecte son problème, et seulement lui."""

import math

import pytest
from shapely.geometry import LineString

from trame import controles
from trame.moteur.enchainement import calculer_trace


def ligne(x0, y0, x1, y1):
    return LineString([(x0, y0), (x1, y1)])


def arc(centre, rayon, debut, fin, n=90):
    """Arc de cercle (angles en degrés)."""
    return LineString([(centre[0] + rayon * math.cos(math.radians(debut + (fin - debut) * k / n)),
                        centre[1] + rayon * math.sin(math.radians(debut + (fin - debut) * k / n))) for k in range(n + 1)])


def test_lignes_trop_proches():
    calque = [ligne(0, 100, 400, 100), ligne(0, 115, 400, 115), ligne(0, 200, 400, 200)]
    c = controles.lignes_trop_proches([calque], ecart_min=20)
    assert c["statut"] == "alerte"
    assert "15 mm" in c["message"]
    assert c["segments"]
    assert controles.lignes_trop_proches([calque], ecart_min=10)["statut"] == "ok"
    # deux calques différents peuvent être proches : ils se croisent par principe
    assert controles.lignes_trop_proches([[calque[0]], [calque[1]]], ecart_min=20)["statut"] == "ok"


def test_croisements_rasants():
    a = [ligne(0, 150, 400, 150)]
    rasante = [ligne(0, 130, 400, 170)]            # environ 6°
    ouverte = [ligne(100, 0, 300, 300)]            # environ 56°
    c = controles.croisements_rasants([a, rasante])
    assert c["statut"] == "alerte" and len(c["points"]) == 1
    assert c["points"][0] == pytest.approx([200, 150])
    assert controles.croisements_rasants([a, ouverte])["statut"] == "ok"


def test_virages_serres():
    assert controles.virages_serres([arc((0, 0), 10, 0, 360)], 20, "dessin")["statut"] == "alerte"
    assert controles.virages_serres([arc((0, 0), 50, 0, 360)], 20, "dessin")["statut"] == "ok"
    # angle vif : une ligne brisée à 90°
    coude = LineString([(0, 0), (100, 0), (100, 100)])
    c = controles.virages_serres([coude], 20, "dessin")
    assert c["statut"] == "alerte" and c["points"] == [[100, 0]]
    # arc doux de grand rayon
    assert controles.virages_serres([arc((0, 0), 200, 0, 90)], 20, "dessin")["statut"] == "ok"


def test_sur_la_palette():
    r = {"path": [(10, 10, 0), (1195, 10, 0)]}
    assert controles.sur_la_palette(r, (1200, 800), 0)["statut"] == "ok"
    c = controles.sur_la_palette(r, (1200, 800), 20)
    assert c["statut"] == "erreur" and len(c["points"]) == 2


def test_quantites():
    r = {"path": [(0, 0, 0), (1000, 0, 0)]}
    q = controles.quantites(r, largeur_cordon=10, hauteur_couche=5, vitesse=50)
    assert q == {"longueur": 1000, "duree": 20, "volume": 0.1}


def test_liaisons_dans_un_calque_en_plusieurs_morceaux():
    A = [[(0, 0), (100, 0)], [(0, 40), (100, 40)]]
    B = [[(50, -50), (50, 100)]]
    r = calculer_trace([A, B], largeur_cordon=10, amp=5)
    c = controles.liaisons_ajoutees(r, ["A", "B"])
    assert c["statut"] == "alerte" and "« A »" in c["message"] and c["segments"]
    seul = calculer_trace([[A[0]], B], largeur_cordon=10, amp=5)
    assert controles.liaisons_ajoutees(seul, ["A", "B"])["statut"] == "ok"


def test_liaison_par_dessus_le_beton_signalee():
    # B est enfermé dans un carré imprimé avant lui, C est dehors : la liaison de B à C passe
    # par-dessus le carré, et se voit
    carre = [(0, 0), (300, 0), (300, 300), (0, 300), (0, 0)]
    r = calculer_trace([[carre], [[(140, 150), (160, 150)]], [[(400, 0), (400, 300)]]], largeur_cordon=10, amp=5)
    c = controles.liaisons_ajoutees(r, ["A", "B", "C"])
    assert c["statut"] == "alerte" and "par-dessus des cordons déjà imprimés" in c["message"] and c["segments"]
    # sans rien franchir : rien à signaler
    a_cote = calculer_trace([[[(0, 0), (300, 0)]], [[(310, 10), (310, 300)]]], largeur_cordon=10, amp=5)
    assert controles.liaisons_ajoutees(a_cote, ["A", "B"])["statut"] == "ok"


def test_depart_au_dessus_des_cordons_a_venir_signale():
    # le premier calque est enfermé dans un carré imprimé ensuite : pour l'atteindre, la buse
    # (le béton coule déjà) passe au-dessus de l'endroit où sera le carré
    carre = [(0, 0), (300, 0), (300, 300), (0, 300), (0, 0)]
    r = calculer_trace([[[(140, 150), (160, 150)]], [carre]], largeur_cordon=10, amp=5)
    c = controles.depart_et_fin(r)
    assert c["statut"] == "alerte" and "début du premier calque" in c["message"] and c["segments"]
    # dans l'autre ordre, le départ est au bord du dessin (c'est alors la fin qui est enfermée)
    r = calculer_trace([[carre], [[(140, 150), (160, 150)]]], largeur_cordon=10, amp=5)
    assert r["depart"]["evite_suite"] and not r["fin"]["libre"]
    assert controles.depart_et_fin(r)["statut"] == "erreur"


def test_controler_un_dessin():
    A = [[(0, 100), (400, 100)]]
    B = [[(200, 0), (200, 300)]]
    r = calculer_trace([A, B], largeur_cordon=10, amp=5, pauses=[True, False], cadre=(-200, -200, 600, 500))
    calques = [[LineString(c) for c in A], [LineString(c) for c in B]]
    resultats = {c["titre"]: c["statut"] for c in controles.controler(
        r, calques, ["A", "B"], {"largeur_cordon": 10, "rayon_courbure_min": 20, "palette": (1200, 800)})}
    assert resultats["Pauses : 1, sans passer au-dessus du béton"] == "ok"
    assert resultats["Départ et fin à côté du dessin"] == "ok"
    assert resultats["Croisements assez ouverts"] == "ok"


def spirale(pas, tours=3):
    return LineString([((20 + pas * t / (2 * math.pi)) * math.cos(t), (20 + pas * t / (2 * math.pi)) * math.sin(t))
                       for t in [k * 0.05 for k in range(int(tours * 2 * math.pi / 0.05))]])


def test_deux_tours_de_spirale_trop_proches():
    assert controles.lignes_trop_proches([[spirale(15)]], 20)["statut"] == "alerte"
    assert controles.lignes_trop_proches([[spirale(60)]], 20)["statut"] == "ok"


def test_epingle_trop_etroite():
    # une seule ligne qui fait demi-tour : ses deux jambes à 14 mm l'une de l'autre
    epingle = LineString([(0, 0), (300, 0)] + [(300 + 7 * math.sin(math.pi * k / 12), 7 - 7 * math.cos(math.pi * k / 12))
                                                for k in range(13)] + [(0, 14)])
    c = controles.lignes_trop_proches([[epingle]], 20)
    assert c["statut"] == "alerte" and "14 mm" in c["message"]


def test_une_boucle_qui_se_croise_n_est_pas_trop_proche():
    # deux passages qui se croisent franchement ne sont pas « trop proches »
    boucle = LineString([(0, 0), (200, 0), (200, 100), (100, 100), (100, -100)])
    assert controles.lignes_trop_proches([[boucle]], 20)["statut"] == "ok"


def test_croisement_rasant_dans_une_meme_ligne():
    rasant = LineString([(0, 0), (200, 0), (200, 30), (-100, -30)])
    c = controles.croisements_rasants([[rasant]])
    assert c["statut"] == "alerte" and "11°" in c["message"]
    # entre deux calques, comme avant
    assert controles.croisements_rasants([[LineString([(0, 0), (100, 0)])], [LineString([(50, -50), (50, 50)])]])["statut"] == "ok"
    # une courbe fermée ne se « croise » pas à son point de départ
    cercle = LineString([(100 * math.cos(2 * math.pi * k / 72), 100 * math.sin(2 * math.pi * k / 72)) for k in range(73)])
    assert controles.croisements_rasants([[cercle]])["statut"] == "ok"
