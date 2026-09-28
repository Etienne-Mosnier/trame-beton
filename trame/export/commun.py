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
    """Sommets des bosses : (x, y, z) là où la hauteur est plus grande qu'aux deux voisins."""
    sommets = []
    for serie in waves:
        for poly in serie:
            for k in range(1, len(poly) - 1):
                if poly[k][2] > 0 and poly[k][2] > poly[k - 1][2] and poly[k][2] > poly[k + 1][2]:
                    sommets.append(tuple(poly[k]))
    return sommets


def reperes_palette(palette):
    """Repères de calibration (CDC §7) : origine, un point sur le grand côté, un sur le petit."""
    lx, ly = palette
    return [("P1 origine", (0.0, 0.0)), ("P2 grand cote", (lx, 0.0)), ("P3 petit cote", (0.0, ly))]
