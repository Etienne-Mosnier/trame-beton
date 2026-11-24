"""Réglages de l'aperçu : chacun devient un curseur (réglages du béton, dans trame/app.py).

    MOTEUR = {"largeur_cordon": Parametre(10, mini=4, maxi=40, unite="mm", aide="Largeur du cordon")}
    valeurs(MOTEUR, {"largeur_cordon": 12})  ->  {"largeur_cordon": 12}
"""


class Parametre:
    """Un curseur : valeur par défaut, bornes, unité et phrase d'aide."""

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
        """Ramène v entre mini et maxi, avec le même type que la valeur par défaut."""
        return min(max(type(self.valeur)(v), self.mini), self.maxi)

    def vers_dict(self):
        """Description envoyée à la page web pour construire le curseur."""
        return {"type": "curseur", "valeur": self.valeur, "mini": self.mini, "maxi": self.maxi,
                "pas": self.pas, "unite": self.unite, "aide": self.aide}


def valeurs(parametres, reglages=None):
    """Dictionnaire nom -> valeur : valeurs par défaut, remplacées par 'reglages' s'il y en a.
    Les valeurs impossibles sont ramenées dans les bornes ; les noms inconnus sont ignorés."""
    reglages = reglages or {}
    return {nom: parametre.borner(reglages.get(nom, parametre.valeur))
            for nom, parametre in parametres.items()}
