"""Motif de lignes déformées par des points d'attraction."""

import math

from shapely.geometry import LineString

from trame.outils import centre, lignes_paralleles, rayon
from trame.parametres import Parametre


NOM = "Point d'attraction"

PARAMETRES = {
    "espacement": Parametre(80, mini=40, maxi=150, unite="mm",
                            aide="Distance minimale entre deux lignes d'une même série"),
    "nombre_points": Parametre(2, mini=1, maxi=3, unite="",
                               aide="Nombre de points d'attraction visibles"),
    "force": Parametre(35, mini=0, maxi=80, unite="mm",
                       aide="Force avec laquelle les lignes sont attirées"),
    "rayon_attraction": Parametre(180, mini=80, maxi=400, unite="mm",
                                  aide="Distance d'influence autour de chaque point"),
    "x1": Parametre(400, mini=0, maxi=1200, unite="mm", aide="Position horizontale du point 1"),
    "y1": Parametre(400, mini=0, maxi=800, unite="mm", aide="Position verticale du point 1"),
    "x2": Parametre(800, mini=0, maxi=1200, unite="mm", aide="Position horizontale du point 2"),
    "y2": Parametre(400, mini=0, maxi=800, unite="mm", aide="Position verticale du point 2"),
    "x3": Parametre(600, mini=0, maxi=1200, unite="mm", aide="Position horizontale du point 3"),
    "y3": Parametre(600, mini=0, maxi=800, unite="mm", aide="Position verticale du point 3"),
}


def _points_attraction(p):
    """Renvoie seulement les points demandés dans l'aperçu."""
    points = [(p["x1"], p["y1"]), (p["x2"], p["y2"]), (p["x3"], p["y3"])]
    return points[:p["nombre_points"]]


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
    attractions = _points_attraction(p)
    lignes = [
        lignes_paralleles(contour, angle, p["espacement"])
        for angle in (160, 29, 135)
    ]
    return [_deformer(serie, attractions, p["force"], p["rayon_attraction"])
            for serie in lignes]
