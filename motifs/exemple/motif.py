"""Motif exemple : des séries de lignes droites qui se croisent en losanges.

C'est le motif de la définition Grasshopper d'origine (betonrobot.ghx), avec des séries que l'on
ajoute ou retire dans l'aperçu (de 2 à 5), chacune avec son angle et son espacement.
Il montre la forme d'un fichier de motif.
"""

from trame.outils import lignes_paralleles
from trame.parametres import Liste, Parametre

NOM = "Exemple : séries de lignes"

PARAMETRES = {
    "series": Liste(
        [{"angle": 160, "espacement": 50}, {"angle": 29, "espacement": 50}, {"angle": 135, "espacement": 50}],
        mini=2, maxi=5, element="Série",
        champs={
            "angle": Parametre(90, mini=0, maxi=180, unite="°", aide="Direction des lignes"),
            "espacement": Parametre(50, mini=20, maxi=150, unite="mm", aide="Écart entre deux lignes"),
        },
        aide="Une ligne par série, dans l'ordre d'impression : chaque série passe par-dessus "
             "les précédentes. Pour chacune : la direction de ses lignes et leur écartement."),
}


def series(contour, p):
    """Une série de lignes parallèles par ligne du réglage, dans l'ordre d'impression A, B, C…"""
    return [lignes_paralleles(contour, s["angle"], s["espacement"]) for s in p["series"]]
