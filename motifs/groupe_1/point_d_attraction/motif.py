"""Motif de lignes déformées par des points d'attraction."""

import math

from shapely.geometry import LineString

from trame.outils import centre, lignes_paralleles, rayon
from trame.parametres import Parametre, Points


NOM = "Point d'attraction"

PARAMETRES = {
    "espacement": Parametre(80, mini=40, maxi=150, unite="mm",
                            aide="Distance minimale entre deux lignes d'une même série"),
    "force": Parametre(35, mini=0, maxi=80, unite="mm",
                       aide="Force avec laquelle les lignes sont attirées"),
    "rayon_attraction": Parametre(180, mini=80, maxi=400, unite="mm",
                                  aide="Distance d'influence autour de chaque point"),
    "attractions": Points([(400, 400), (800, 400)], mini=0, maxi=8,
                          aide="Points qui attirent les lignes."),
}


def _attirer(point, attractions, force, influence):
    """Déplace un point vers les points d'attraction proches."""
    x, y = point
    dx_total = 0.0
    dy_total = 0.0
    for ax, ay in attractions:
        dx = ax - x
        dy = ay - y
        distance = math.hypot(dx, dy)
        if distance == 0:
            continue
        poids = math.exp(-((distance / influence) ** 2))
        dx_total += force * poids * dx / distance
        dy_total += force * poids * dy / distance
    return x + dx_total, y + dy_total


def _deformer(courbes, attractions, force, influence):
    """Ajoute des points intermédiaires pour dessiner des lignes souples."""
    deformees = []
    for courbe in courbes:
        debut, fin = courbe.coords[0], courbe.coords[-1]
        points = []
        for index in range(41):
            t = index / 40
            point = (debut[0] + t * (fin[0] - debut[0]),
                     debut[1] + t * (fin[1] - debut[1]))
            points.append(_attirer(point, attractions, force, influence))
        deformees.append(LineString(points))
    return deformees


def series(contour, p):
    """Trois séries de lignes dont la trajectoire se courbe vers les points."""
    attractions = p["attractions"]      # liste de (x, y), éventuellement vide
    lignes = [
        lignes_paralleles(contour, angle, p["espacement"])
        for angle in (160, 29, 135)
    ]
    return [_deformer(serie, attractions, p["force"], p["rayon_attraction"])
            for serie in lignes]
