"""Ce qui sert aux deux exports (DXF et SVG) : calques, liaisons, sommets des bosses."""

from shapely.geometry import LineString, Point

from trame.moteur.chemin import decaler_vers_exterieur

LETTRES = "ABCDE"
# Distance au couloir sous laquelle un segment est une liaison le long du bord (mm).
TOLERANCE_LIAISON = 0.2


def couloirs(contour, lane, nb_series):
    """Le contour et ses décalages vers l'extérieur : un par série (liaisons)."""
    anneau = list(contour.exterior.coords)
    if lane <= 0:
        return [contour.exterior]
    return [LineString(decaler_vers_exterieur(anneau, lane * i)) for i in range(max(nb_series, 1))]


def lignes_et_liaisons(resultat, contour, lane):
    """(lignes, liaisons) : lignes[i] = polylignes 3D de la série i hors liaisons,
    liaisons = polylignes 3D ajoutées par le moteur pour relier les lignes.
    Dessin importé : le moteur les donne déjà ; motif + contour : on les retrouve le long du bord."""
    if "lignes" in resultat:
        return resultat["lignes"], [l["points"] for l in resultat["liaisons"]]
    return separer_liaisons(resultat["waves"], contour, lane)


def separer_liaisons(waves, contour, lane):
    """Coupe chaque série en morceaux « lignes du motif » et morceaux « liaisons ».

    Renvoie (lignes, liaisons) : lignes[i] = polylignes 3D de la série i hors liaisons,
    liaisons = polylignes 3D qui longent un couloir du bord.
    """
    anneaux = couloirs(contour, lane, len(waves))

    def sur_le_bord(a, b):
        milieu = Point((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        return min(c.distance(milieu) for c in anneaux) < TOLERANCE_LIAISON

    lignes, liaisons = [], []
    for serie in waves:
        morceaux = []
        for poly in serie:
            courant, type_courant = [], None
            for a, b in zip(poly, poly[1:]):
                t = "liaison" if sur_le_bord(a, b) else "ligne"
                if t != type_courant:
                    if len(courant) > 1:
                        (liaisons if type_courant == "liaison" else morceaux).append(courant)
                    courant, type_courant = [a], t
                courant.append(b)
            if len(courant) > 1:
                (liaisons if type_courant == "liaison" else morceaux).append(courant)
        lignes.append(morceaux)
    return lignes, liaisons


def sommets_des_bosses(waves):
    """Sommets des bosses : (x, y, z) là où la hauteur monte puis ne monte plus (un sommet pointu,
    ou le début d'un sommet plat)."""
    sommets = []
    for serie in waves:
        for poly in serie:
            for k in range(1, len(poly) - 1):
                if poly[k][2] > 0 and poly[k][2] > poly[k - 1][2] and poly[k][2] >= poly[k + 1][2]:
                    sommets.append(tuple(poly[k]))
    return sommets


def noms_des_calques(nb, noms=None):
    """Nom de chaque calque exporté, dans l'ordre d'impression : « 1. A vagues », « 2. B lignes »…
    (le rang en tête : réimporté, le fichier garde le même ordre). Sans noms : SERIE_A, SERIE_B…
    Les caractères refusés dans un nom de calque DXF sont remplacés par « _ »."""
    if not noms:
        return ["SERIE_%s" % LETTRES[i] for i in range(nb)]
    propre = lambda nom: "".join("_" if c in '<>/\\":;?*|=`' else c for c in nom)
    return ["%d. %s" % (i + 1, propre(nom)) for i, nom in enumerate(noms[:nb])]


def attentes(resultat):
    """Parcours levé de la buse et point d'attente : départ, chaque pause, fin.
    Renvoie [(nom, trajet 3D, point d'attente), …]."""
    sortie = []
    if resultat.get("depart"):
        sortie.append(("DEPART", resultat["depart"]["trajet"], resultat["depart"]["point"]))
    for numero, (dep, pause) in enumerate(zip(resultat.get("deplacements", []), resultat.get("pauses", [])), 1):
        sortie.append(("PAUSE %d" % numero, dep, pause["point"]))
    if resultat.get("fin"):
        sortie.append(("FIN", resultat["fin"]["trajet"], resultat["fin"]["point"]))
    return sortie


def reperes_palette(palette):
    """Repères de calibration (CDC §7) : origine, un point sur le grand côté, un sur le petit."""
    lx, ly = palette
    return [("P1 origine", (0.0, 0.0)), ("P2 grand cote", (lx, 0.0)), ("P3 petit cote", (0.0, ly))]
