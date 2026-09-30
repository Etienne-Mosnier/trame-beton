"""Motif exemple : des séries de lignes droites qui se croisent en losanges.

C'est le motif de la définition Grasshopper d'origine (betonrobot.ghx), avec des séries que l'on
ajoute ou retire dans l'aperçu (de 2 à 5). Il montre la forme d'un fichier de motif.
"""

from trame.outils import lignes_paralleles
from trame.parametres import Liste, Parametre

NOM = "Exemple : séries de lignes"

PARAMETRES = {
    "espacement": Parametre(50, mini=20, maxi=150, unite="mm",
                            aide="Écart entre deux lignes d'une même série"),
    "directions": Liste([160, 29, 135], mini=2, maxi=5, bornes=(0, 180), unite="°", element="Série",
                        aide="Direction des lignes de chaque série, dans l'ordre d'impression : "
                             "chaque série passe par-dessus les précédentes"),
}


def series(contour, p):
    """Une série de lignes parallèles par direction, dans l'ordre d'impression A, B, C…"""
    return [lignes_paralleles(contour, angle, p["espacement"]) for angle in p["directions"]]
