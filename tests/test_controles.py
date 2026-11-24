"""Contrôles d'imprimabilité : chaque contrôle détecte son problème, et seulement lui."""

import math

import pytest
from shapely.geometry import LineString, Point, box

from trame import controles
from trame.moteur.chemin import calculer_chemin

FORME = box(0, 0, 400, 300)


def ligne(x0, y0, x1, y1):
    return LineString([(x0, y0), (x1, y1)])


def test_lignes_trop_proches():
    serie = [ligne(0, 100, 400, 100), ligne(0, 115, 400, 115), ligne(0, 200, 400, 200)]
    c = controles.lignes_trop_proches([serie], ecart_min=20)
    assert c["statut"] == "alerte"
    assert "15 mm" in c["message"]
    assert c["segments"]
    assert controles.lignes_trop_proches([serie], ecart_min=10)["statut"] == "ok"


def test_croisements_rasants():
    a = [ligne(0, 150, 400, 150)]
    rasante = [ligne(0, 130, 400, 170)]            # environ 6°
    ouverte = [ligne(100, 0, 300, 300)]            # environ 56°
    c = controles.croisements_rasants([a, rasante])
    assert c["statut"] == "alerte" and len(c["points"]) == 1
    assert c["points"][0] == pytest.approx([200, 150])
    assert controles.croisements_rasants([a, ouverte])["statut"] == "ok"


def test_virages_serres():
    from trame.outils import arc, cercle
    assert controles.virages_serres([cercle((0, 0), 10)], 20, "motif")["statut"] == "alerte"
    assert controles.virages_serres([cercle((0, 0), 50)], 20, "motif")["statut"] == "ok"
    # angle vif : une ligne brisée à 90°
    coude = LineString([(0, 0), (100, 0), (100, 100)])
    c = controles.virages_serres([coude], 20, "motif")
    assert c["statut"] == "alerte" and c["points"] == [[100, 0]]
    # arc doux de grand rayon
    assert controles.virages_serres([arc((0, 0), 200, 0, 90)], 20, "motif")["statut"] == "ok"


def test_decouper_garde_l_interieur():
    lignes = controles.decouper([[ligne(-100, 100, 500, 100)]], FORME)
    assert lignes[0][0].length == pytest.approx(400)


def test_sur_la_palette():
    r = {"path": [(10, 10, 0), (1195, 10, 0)]}
    assert controles.sur_la_palette(r, (1200, 800), 0)["statut"] == "ok"
    c = controles.sur_la_palette(r, (1200, 800), 20)
    assert c["statut"] == "erreur" and len(c["points"]) == 2


def test_controler_sur_un_vrai_chemin():
    S = [[ligne(-10, y, 410, y) for y in range(40, 300, 40)],
         [ligne(x, -10, x, 310) for x in range(40, 400, 40)]]
    r = calculer_chemin([[list(c.coords) for c in s] for s in S], FORME, lane=5)
    reglages = {"largeur_cordon": 10, "rayon_courbure_min": 20, "lane": 5,
                "palette": (1200, 800), "marge": 0}
    resultats = {c["titre"]: c for c in controles.controler(r, FORME, S, reglages)}
    assert resultats["Chemin continu"]["statut"] == "ok"
    assert resultats["Tout est dans la forme"]["statut"] == "ok"
    assert resultats["Lignes assez espacées"]["statut"] == "ok"
    assert resultats["Croisements assez ouverts"]["statut"] == "ok"
    # les 4 coins du rectangle sont des angles vifs
    assert len(resultats["Virages assez doux (contour)"]["points"]) == 4


def test_passages_en_double_classes_sur_le_bord():
    # un passage en double sur un couloir (5 mm hors du contour) est bien « le long du bord »
    double = [[(0, -5, 0), (100, -5, 0)]]
    c = controles.passages_en_double({"superposes": double}, FORME, lane=5, nb_series=2)
    assert "tous le long du bord" in c["message"]
    dedans = [[(100, 100, 0), (200, 100, 0)]]
    c = controles.passages_en_double({"superposes": dedans}, FORME, lane=5, nb_series=2)
    assert "1 dans la forme" in c["message"]


def test_quantites():
    r = {"path": [(0, 0, 0), (1000, 0, 0)]}
    q = controles.quantites(r, largeur_cordon=10, hauteur_couche=5, vitesse=50)
    assert q == {"longueur": 1000, "duree": 20, "volume": 0.1}


def test_ligne_qui_se_recoupe():
    boucle = LineString([(0, 0), (100, 0), (50, 50), (50, -50)])      # croise son premier segment
    c = controles.lignes_qui_se_recoupent([[boucle]])
    assert c["statut"] == "alerte" and c["points"] == [[50, 0]]
    assert controles.lignes_qui_se_recoupent([[ligne(0, 0, 100, 0)]])["statut"] == "ok"


def test_decoupe_ne_coupe_qu_au_bord():
    # une ligne qui se recoupe à l'intérieur de la forme reste en un seul morceau
    from trame.moteur.chemin import calculer_chemin
    boucle = [(-50, 150), (250, 150), (200, 250), (150, 100), (450, 100)]
    r = calculer_chemin([[boucle], [[(200, -50), (200, 350)]]], FORME, lane=0)
    assert r["raccords_droits"] == 0 and r["controle"]["sauts"] == 0


# --- dessin importé, en calques -----------------------------------------------------

from trame.controles import croisements_rasants_trace, lignes_trop_proches_trace


def spirale(pas, tours=3):
    return LineString([((20 + pas * t / (2 * math.pi)) * math.cos(t), (20 + pas * t / (2 * math.pi)) * math.sin(t))
                       for t in [k * 0.05 for k in range(int(tours * 2 * math.pi / 0.05))]])


def test_deux_tours_de_spirale_trop_proches():
    assert lignes_trop_proches_trace([[spirale(15)]], 20)["statut"] == "alerte"
    assert lignes_trop_proches_trace([[spirale(60)]], 20)["statut"] == "ok"


def test_epingle_trop_etroite():
    # une seule ligne qui fait demi-tour : ses deux jambes à 14 mm l'une de l'autre
    epingle = LineString([(0, 0), (300, 0)] + [(300 + 7 * math.sin(math.pi * k / 12), 7 - 7 * math.cos(math.pi * k / 12))
                                                for k in range(13)] + [(0, 14)])
    c = lignes_trop_proches_trace([[epingle]], 20)
    assert c["statut"] == "alerte" and "14 mm" in c["message"]


def test_une_boucle_qui_se_croise_n_est_pas_trop_proche():
    # deux passages qui se croisent franchement ne sont pas « trop proches »
    boucle = LineString([(0, 0), (200, 0), (200, 100), (100, 100), (100, -100)])
    assert lignes_trop_proches_trace([[boucle]], 20)["statut"] == "ok"


def test_croisement_rasant_dans_une_meme_ligne():
    rasant = LineString([(0, 0), (200, 0), (200, 30), (-100, -30)])
    c = croisements_rasants_trace([[rasant]])
    assert c["statut"] == "alerte" and "11°" in c["message"]
    # entre deux calques, comme avant
    assert croisements_rasants_trace([[LineString([(0, 0), (100, 0)])], [LineString([(50, -50), (50, 50)])]])["statut"] == "ok"
    # une courbe fermée ne se « croise » pas à son point de départ
    cercle = LineString([(100 * math.cos(2 * math.pi * k / 72), 100 * math.sin(2 * math.pi * k / 72)) for k in range(73)])
    assert croisements_rasants_trace([[cercle]])["statut"] == "ok"
