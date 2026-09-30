"""Couches : la trame est réimprimée par-dessus elle-même (couche 2, 3… jusqu'à 5).

La couche 1 est calculée par le moteur d'origine (croisements.empiler). Pour les couches
suivantes, on applique une règle générale : en chaque point, la buse se pose sur le béton
déjà imprimé à cet endroit (le haut du cordon le plus haut dessous), et les montées gardent la
même pente que les bosses de la couche 1 (hauteur amp sur une longueur d).
Ainsi A2 épouse A1 (et ses bosses), B2 monte au-dessus de A2, etc.
"""

import math

import numpy as np
import shapely
from shapely.geometry import LineString, Point

# Pas de calcul le long du chemin (mm) et distance sous laquelle un cordon est « dessous ».
PAS = 1.0
RAYON = 1.0


def reechantillonner(points, pas=PAS):
    """Points (x, y) tous les 'pas' mm, en gardant les sommets d'origine."""
    sortie = [tuple(points[0][:2])]
    for a, b in zip(points, points[1:]):
        d = math.dist(a[:2], b[:2])
        n = max(1, math.ceil(d / pas))
        for k in range(1, n + 1):
            sortie.append((a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n))
    return sortie


def hauteur_dessous(xy, imprimes, amp):
    """Pour chaque point (x, y) : hauteur du haut du béton déjà imprimé (0 = bâche)."""
    segments = [(p, q) for poly in imprimes for p, q in zip(poly, poly[1:])]
    H = np.zeros(len(xy))
    if not segments:
        return H
    A = np.array([s[0] for s in segments], dtype=float)
    B = np.array([s[1] for s in segments], dtype=float)
    arbre = shapely.STRtree(shapely.linestrings(np.stack([A[:, :2], B[:, :2]], axis=1)))
    P = np.array(xy, dtype=float)
    i_pt, i_seg = arbre.query(shapely.points(P), predicate="dwithin", distance=RAYON)
    if len(i_pt) == 0:
        return H
    a, b, p = A[i_seg], B[i_seg], P[i_pt]
    ab = b[:, :2] - a[:, :2]
    long2 = (ab ** 2).sum(axis=1)
    t = np.where(long2 > 0, ((p - a[:, :2]) * ab).sum(axis=1) / np.where(long2 > 0, long2, 1), 0)
    t = np.clip(t, 0, 1)
    haut = a[:, 2] + (b[:, 2] - a[:, 2]) * t + amp          # haut du cordon dessous
    np.maximum.at(H, i_pt, haut)
    return H


def monter(trace, imprimes, amp, d, tol=0.05):
    """Trace à plat -> polyligne 3D posée sur ce qui est déjà imprimé, montées en pente douce."""
    xy = reechantillonner(trace)
    H = hauteur_dessous(xy, imprimes, amp)
    pente = amp / d if d > 0 else 1e9
    s = np.concatenate([[0.0], np.cumsum([math.dist(p, q) for p, q in zip(xy, xy[1:])])])
    z = H.copy()
    # z = max sur tous les points j de (H_j - pente × distance) : deux passages suffisent
    for k in range(1, len(z)):
        z[k] = max(z[k], z[k - 1] - pente * (s[k] - s[k - 1]))
    for k in range(len(z) - 2, -1, -1):
        z[k] = max(z[k], z[k + 1] - pente * (s[k + 1] - s[k]))
    points = [(x, y, float(h)) for (x, y), h in zip(xy, z)]
    return simplifier(points, tol)


def simplifier(points, tol):
    """Retire les points alignés (en 3D) avec leurs voisins, à tol près."""
    garde = [points[0]]
    for k in range(1, len(points) - 1):
        a, b, c = np.array(garde[-1]), np.array(points[k]), np.array(points[k + 1])
        ac = c - a
        n = np.linalg.norm(ac)
        if n == 0:
            continue
        ecart = np.linalg.norm(np.cross(b - a, ac)) / n
        if ecart > tol:
            garde.append(points[k])
    garde.append(points[-1])
    return garde


def liaison_de_couche(fin, debut, couloir):
    """Passage de la fin d'une couche au début de la suivante, sans quitter la ligne :
    le long du couloir de la dernière série, puis jusqu'au départ de la première."""
    bord = LineString([p[:2] for p in couloir])
    L = bord.length
    l0, l1 = bord.project(Point(fin[:2])), bord.project(Point(debut[:2]))
    avant = (l1 - l0) % L
    sens = 1 if avant <= L - avant else -1
    longueur = avant if sens == 1 else L - avant
    n = max(1, math.ceil(longueur / 2.0))
    points = [tuple(fin[:2])]
    for k in range(n + 1):
        q = bord.interpolate((l0 + sens * longueur * k / n) % L)
        points.append((q.x, q.y))
    points.append(tuple(debut[:2]))
    return points
