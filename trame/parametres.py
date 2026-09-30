"""Paramètres réglables des motifs : chacun devient un réglage dans l'aperçu.

Dans un motif :
    PARAMETRES = {
        "espacement": Parametre(50, mini=20, maxi=150, unite="mm", aide="Écart entre deux lignes"),
        "forme": Choix("vagues", ["vagues", "zigzag", "arcs"], aide="Forme des lignes de B"),
        "inverser": Case(False, aide="Inverser le sens des vagues"),
        "centre": Point(600, 400, aide="Centre des cercles"),
        "attractions": Points([(400, 400), (800, 400)], mini=0, maxi=8, aide="Points qui attirent"),
        "angles": Liste([160, 29, 135], mini=2, maxi=5, bornes=(0, 180), unite="°",
                        element="Série", aide="Direction des lignes de chaque série"),
    }

| Type      | Dans l'aperçu                                   | Valeur reçue dans p[...]         |
|-----------|-------------------------------------------------|----------------------------------|
| Parametre | un curseur                                      | un nombre                        |
| Choix     | une liste déroulante                            | le texte choisi                  |
| Case      | une case oui / non                              | True ou False                    |
| Point     | une poignée orange sur la palette, à déplacer   | (x, y) en mm                     |
| Points    | des poignées que l'on ajoute (double-clic sur   | liste de (x, y) en mm            |
|           | la palette), déplace et supprime (double-clic   | (éventuellement vide si mini=0)  |
|           | sur le point)                                   |                                  |
| Liste     | un curseur par élément, « + Ajouter » et « × »  | liste de nombres                 |
|           | pour en retirer (ex. une direction par série)   |                                  |

Les points sont dans le repère de la palette : origine au coin, x le long du grand côté.
"""

LONGUEUR_PALETTE = 1200.0
LARGEUR_PALETTE = 800.0


def sur_la_palette(xy):
    """Ramène un point (x, y) sur la palette."""
    return (min(max(float(xy[0]), 0.0), LONGUEUR_PALETTE), min(max(float(xy[1]), 0.0), LARGEUR_PALETTE))


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


class Choix:
    """Une liste déroulante : une valeur parmi 'options' (des textes)."""

    def __init__(self, valeur, options, aide=""):
        self.valeur = valeur
        self.options = list(options)
        self.aide = aide

    def borner(self, v):
        return v if v in self.options else self.valeur

    def vers_dict(self):
        return {"type": "choix", "valeur": self.valeur, "options": self.options, "aide": self.aide}


class Case:
    """Un réglage oui / non."""

    def __init__(self, valeur, aide=""):
        self.valeur = bool(valeur)
        self.aide = aide

    def borner(self, v):
        return bool(v)

    def vers_dict(self):
        return {"type": "case", "valeur": self.valeur, "aide": self.aide}


class Point:
    """Un point de la palette que l'on place à la souris : x, y en mm (origine au coin)."""

    def __init__(self, x, y, aide=""):
        self.valeur = (float(x), float(y))
        self.aide = aide

    def borner(self, v):
        return sur_la_palette(v)

    def vers_dict(self):
        return {"type": "point", "valeur": list(self.valeur), "aide": self.aide}


class Points:
    """Des points de la palette que l'on ajoute, supprime et déplace à la souris.
    Entre 'mini' et 'maxi' points ; la valeur par défaut est la liste de départ."""

    def __init__(self, valeur, mini=0, maxi=10, aide=""):
        self.valeur = [(float(x), float(y)) for x, y in valeur]
        self.mini = mini
        self.maxi = maxi
        self.aide = aide

    def borner(self, v):
        points = [sur_la_palette(p) for p in v][:self.maxi]
        # s'il en manque, on complète avec ceux de départ
        for p in self.valeur:
            if len(points) >= self.mini:
                break
            points.append(p)
        return points

    def vers_dict(self):
        return {"type": "points", "valeur": [list(p) for p in self.valeur],
                "mini": self.mini, "maxi": self.maxi, "aide": self.aide}


class Liste:
    """Une liste de longueur variable (entre 'mini' et 'maxi' éléments), que l'on complète ou
    réduit dans l'aperçu (« + Ajouter » / « × »). Deux formes :

    - des nombres : Liste([160, 29, 135], mini=2, maxi=5, bornes=(0, 180), unite="°")
      -> un curseur par élément ; p["nom"] = [160, 29, 135]
    - des éléments à plusieurs réglages, décrits par 'champs' (des Parametre) :
      Liste([{"angle": 160, "espacement": 50}, …], mini=2, maxi=5, element="Série",
            champs={"angle": Parametre(…), "espacement": Parametre(…)})
      -> une ligne par élément, ses curseurs côte à côte ; p["nom"] = [{"angle": 160, …}, …]

    element : nom affiché de chaque élément (« Série » -> Série A, Série B… ; sinon numérotés)."""

    def __init__(self, valeur, mini, maxi, bornes=(0, 100), unite="", aide="", element="", pas=None,
                 champs=None):
        self.valeur = list(valeur)
        self.mini = mini
        self.maxi = maxi
        self.bornes = bornes
        self.unite = unite
        self.aide = aide
        self.element = element
        self.champs = champs
        entiers = all(isinstance(v, int) for v in bornes) and all(isinstance(v, int) for v in self.valeur)
        self.pas = pas if pas is not None else (1 if entiers else (bornes[1] - bornes[0]) / 100)

    def borner_element(self, x):
        if self.champs:
            x = x if isinstance(x, dict) else {}
            return {nom: champ.borner(x.get(nom, champ.valeur)) for nom, champ in self.champs.items()}
        bas, haut = self.bornes
        return min(max(type(self.valeur[0])(x), bas), haut)

    def borner(self, v):
        elements = [self.borner_element(x) for x in v][:self.maxi]
        for x in self.valeur:                 # s'il en manque, on complète avec ceux de départ
            if len(elements) >= self.mini:
                break
            elements.append(self.borner_element(x))
        return elements

    def vers_dict(self):
        d = {"type": "liste", "valeur": self.valeur, "mini": self.mini, "maxi": self.maxi,
             "aide": self.aide, "element": self.element}
        if self.champs:
            d["champs"] = {nom: champ.vers_dict() for nom, champ in self.champs.items()}
        else:
            d.update(bornes=list(self.bornes), pas=self.pas, unite=self.unite)
        return d


TYPES = (Parametre, Choix, Case, Point, Points, Liste)


def valeurs(parametres, reglages=None):
    """Dictionnaire nom -> valeur : valeurs par défaut, remplacées par 'reglages' s'il y en a.
    Les valeurs impossibles sont ramenées dans les bornes ; les noms inconnus sont ignorés."""
    reglages = reglages or {}
    return {nom: parametre.borner(reglages.get(nom, parametre.valeur))
            for nom, parametre in parametres.items()}
