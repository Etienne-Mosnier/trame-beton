"""Motif du groupe 3 : pour l'instant une copie du motif exemple.

C'est le motif de la définition Grasshopper d'origine (betonrobot.ghx).
Décrivez vos idées dans une issue « Idée de motif » : Copilot transforme ce fichier.
"""

from trame.outils import lignes_paralleles
from trame.parametres import Parametre

NOM = "Départ : trois séries de lignes (à transformer)"

PARAMETRES = {
    "espacement": Parametre(50, mini=20, maxi=150, unite="mm",
                            aide="Écart entre deux lignes d'une même série"),
    "angle_a": Parametre(160, mini=0, maxi=180, unite="°",
                         aide="Direction des lignes de la série A (imprimée en premier, à plat)"),
    "angle_b": Parametre(29, mini=0, maxi=180, unite="°",
                         aide="Direction des lignes de la série B (passe par-dessus A)"),
    "angle_c": Parametre(135, mini=0, maxi=180, unite="°",
                         aide="Direction des lignes de la série C (passe par-dessus A et B)"),
}


def series(contour, p):
    """Trois séries de lignes parallèles, dans l'ordre d'impression A, B, C."""
    serie_a = lignes_paralleles(contour, p["angle_a"], p["espacement"])
    serie_b = lignes_paralleles(contour, p["angle_b"], p["espacement"])
    serie_c = lignes_paralleles(contour, p["angle_c"], p["espacement"])
    return [serie_a, serie_b, serie_c]
