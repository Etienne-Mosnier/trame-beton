"""Contrôles d'imprimabilité : chaque contrôle détecte son problème, et seulement lui."""

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
