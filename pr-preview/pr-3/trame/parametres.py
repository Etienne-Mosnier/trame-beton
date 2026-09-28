"""Paramètres réglables des motifs : chacun devient un curseur dans l'aperçu.

Dans un motif :
    PARAMETRES = {
        "espacement": Parametre(50, mini=20, maxi=150, unite="mm", aide="Écart entre deux lignes"),
    }
La fonction series(contour, p) reçoit p, un dictionnaire nom -> valeur : p["espacement"].
"""


class Parametre:
    """Un réglage : valeur par défaut, bornes du curseur, unité et phrase d'aide."""

    def __init__(self, valeur, mini, maxi, unite="", aide="", pas=None):
        self.valeur = valeur
        self.mini = mini
        self.maxi = maxi
        self.unite = unite
        self.aide = aide
        # pas du curseur : 1 si toutes les valeurs sont entières, sinon 1/100 de la plage
        entiers = all(isinstance(v, int) for v in (valeur, mini, maxi))
        self.pas = pas if pas is not None else (1 if entiers else (maxi - mini) / 100)

    def borner(self, v):
        """Ramène v entre mini et maxi."""
        return min(max(v, self.mini), self.maxi)

    def vers_dict(self):
        """Description envoyée à la page web pour construire le curseur."""
        return {"valeur": self.valeur, "mini": self.mini, "maxi": self.maxi,
                "pas": self.pas, "unite": self.unite, "aide": self.aide}


def valeurs(parametres, reglages=None):
    """Dictionnaire nom -> valeur : valeurs par défaut, remplacées par 'reglages' s'il y en a.
    Les valeurs hors bornes sont ramenées entre mini et maxi ; les noms inconnus sont ignorés."""
    reglages = reglages or {}
    sortie = {}
    for nom, parametre in parametres.items():
        v = reglages.get(nom, parametre.valeur)
        sortie[nom] = parametre.borner(type(parametre.valeur)(v))
    return sortie
