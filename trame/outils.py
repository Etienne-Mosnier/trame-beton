"""Fonctions simples pour écrire les motifs.

Chaque fonction renvoie une liste de courbes (LineString shapely), en mm, dans le repère de
la palette. Les courbes peuvent dépasser du contour : le moteur les découpe.
Les angles sont en degrés : 0° = vers la droite (grand côté de la palette), 90° = vers le haut.

Exemple dans un motif :
    from trame.outils import lignes_paralleles
    serie_a = lignes_paralleles(contour, angle=30, espacement=50)
"""

import math

from shapely import affinity
from shapely.geometry import LineString

# Écart entre deux points d'une courbe (mm) : assez fin pour que les courbes restent lisses.
PAS = 2.0


def centre(contour):
    """Centre de la forme, (x, y)."""
    c = contour.centroid
    return (c.x, c.y)


def rayon(contour, autour=None):
    """Distance du centre (ou du point 'autour') au point de la forme le plus éloigné."""
    cx, cy = autour or centre(contour)
    return max(math.dist((cx, cy), p) for p in contour.exterior.coords)


def lignes_paralleles(contour, angle, espacement, decalage=0):
    """Lignes droites parallèles qui couvrent toute la forme.

    angle      : direction des lignes (degrés)
    espacement : écart entre deux lignes (mm)
    decalage   : fait glisser toutes les lignes sur le côté (mm)
    """
    return ondes(contour, angle, espacement, amplitude=0, longueur_onde=100, decalage=decalage)


def ondes(contour, angle, espacement, amplitude, longueur_onde, decalage=0, dephasage=0):
    """Lignes ondulées parallèles (sinusoïdes) qui couvrent toute la forme.

    amplitude     : hauteur de l'onde de part et d'autre de la ligne (mm) ; 0 = lignes droites
    longueur_onde : distance entre deux sommets de l'onde (mm)
    dephasage     : décale l'onde d'une ligne à la suivante (degrés)
    """
    cx, cy = centre(contour)
    R = rayon(contour) + espacement + abs(amplitude)
    a = math.radians(angle)
    ux, uy = math.cos(a), math.sin(a)       # le long des lignes
    nx, ny = -uy, ux                        # d'une ligne à l'autre
    n = math.ceil(R / espacement)
    courbes = []
    for k in range(-n, n + 1):
        o = k * espacement + decalage
        if amplitude == 0:
            ts = [-R, R]                    # ligne droite : deux points suffisent
        else:
            nb = math.ceil(2 * R / PAS)
            ts = [-R + 2 * R * i / nb for i in range(nb + 1)]
        points = []
        for t in ts:
            ecart = o + amplitude * math.sin(2 * math.pi * t / longueur_onde
                                             + math.radians(dephasage) * k)
            points.append((cx + ux * t + nx * ecart, cy + uy * t + ny * ecart))
        courbes.append(LineString(points))
    return courbes


def cercle(centre_xy, r):
    """Un cercle fermé de rayon r (mm)."""
    points = list(arc(centre_xy, r, 0, 360).coords)
    points[-1] = points[0]            # fermé exactement, malgré les arrondis
    return LineString(points)


def arc(centre_xy, r, debut, fin):
    """Arc de cercle de rayon r, de l'angle 'debut' à l'angle 'fin' (degrés)."""
    cx, cy = centre_xy
    nb = max(8, math.ceil(abs(math.radians(fin - debut)) * r / PAS))
    points = []
    for i in range(nb + 1):
        a = math.radians(debut + (fin - debut) * i / nb)
        points.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return LineString(points)


def cercles_concentriques(contour, espacement, autour=None):
    """Cercles de même centre, espacés de 'espacement' mm, jusqu'au bord de la forme.

    autour : centre des cercles (x, y) ; par défaut le centre de la forme
    """
    c = autour or centre(contour)
    R = rayon(contour, c)
    return [cercle(c, espacement * k) for k in range(1, math.ceil(R / espacement) + 1)]


def contours_decales(contour, espacement, marge=None):
    """Contours emboîtés qui suivent la forme, vers l'intérieur, tous les 'espacement' mm
    (comme des courbes de niveau). Le moteur les imprime en une seule spirale.

    marge : distance du premier contour au bord (par défaut : espacement / 2)
    """
    marge = espacement / 2 if marge is None else marge
    courbes = []
    d = marge
    while True:
        forme = contour.buffer(-d, quad_segs=16)
        if forme.is_empty or forme.area < espacement * espacement:
            break
        # une forme étroite peut se couper en morceaux : on garde le plus grand
        forme = max(getattr(forme, "geoms", [forme]), key=lambda f: f.area)
        courbes.append(LineString(forme.exterior.coords))
        d += espacement
    return courbes


def lignes_rayonnantes(contour, nombre, autour=None, angle_depart=0):
    """'nombre' lignes droites qui partent d'un même point, comme les rayons d'une roue.

    autour : point de départ (x, y) ; par défaut le centre de la forme
    """
    cx, cy = autour or centre(contour)
    R = rayon(contour, (cx, cy)) + 10
    courbes = []
    for k in range(nombre):
        a = math.radians(angle_depart + 360 * k / nombre)
        courbes.append(LineString([(cx, cy), (cx + R * math.cos(a), cy + R * math.sin(a))]))
    return courbes


def tourner(courbes, angle, autour):
    """Tourne toutes les courbes de 'angle' degrés autour du point 'autour' (x, y)."""
    return [affinity.rotate(c, angle, origin=autour) for c in courbes]


def deplacer(courbes, dx, dy):
    """Déplace toutes les courbes de dx, dy (mm)."""
    return [affinity.translate(c, dx, dy) for c in courbes]
