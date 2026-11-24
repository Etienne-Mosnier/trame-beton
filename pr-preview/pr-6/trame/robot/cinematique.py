"""Cinématique de l'UR10e : directe (angles -> position de la buse) et inverse analytique
(position -> jusqu'à 8 jeux d'angles), avec un choix de configuration continu d'un point à l'autre.

Paramètres : ceux de Universal_Robots_ROS2_Description (config/ur10e, licence BSD-3),
convention DH d'Universal Robots. Unités internes : mètres et radians.
Ce calcul sert à l'aperçu et aux alertes ; sur le robot, c'est le contrôleur qui calcule
lui-même les angles (le programme URScript donne des poses cartésiennes).
"""

import math

import numpy as np

# Paramètres DH de l'UR10e (m, rad)
D = [0.1807, 0.0, 0.0, 0.17415, 0.11985, 0.11655]
A = [0.0, -0.6127, -0.57155, 0.0, 0.0, 0.0]
ALPHA = [math.pi / 2, 0.0, 0.0, math.pi / 2, -math.pi / 2, 0.0]

# Limites des articulations (rad) : ±360°, sauf le coude ±180°
LIMITES = [2 * math.pi, 2 * math.pi, math.pi, 2 * math.pi, 2 * math.pi, 2 * math.pi]

# Position de départ : première pose du programme d'origine (reference/betonrobot.script)
DEPART = [-0.1235, -1.3916, 2.3905, -0.9989, -0.1235, -1.5708]


def dh(i, theta):
    """Matrice 4×4 de l'articulation i pour l'angle theta."""
    ct, st = math.cos(theta), math.sin(theta)
    ca, sa = math.cos(ALPHA[i]), math.sin(ALPHA[i])
    return np.array([[ct, -st * ca, st * sa, A[i] * ct],
                     [st, ct * ca, -ct * sa, A[i] * st],
                     [0.0, sa, ca, D[i]],
                     [0.0, 0.0, 0.0, 1.0]])


def directe(q):
    """Angles (rad) -> matrice 4×4 de la bride (tool0) dans le repère base du robot (m)."""
    T = np.eye(4)
    for i in range(6):
        T = T @ dh(i, q[i])
    return T


def rotation(rv):
    """Vecteur rotation (rx, ry, rz) -> matrice 3×3."""
    angle = math.sqrt(sum(v * v for v in rv))
    if angle < 1e-12:
        return np.eye(3)
    k = np.array(rv) / angle
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(angle) * K + (1 - math.cos(angle)) * K @ K


def matrice_pose(pose):
    """Pose UR [x, y, z (m), rx, ry, rz] -> matrice 4×4."""
    T = np.eye(4)
    T[:3, :3] = rotation(pose[3:])
    T[:3, 3] = pose[:3]
    return T


def inverse(T, eps=1e-9):
    """Matrice 4×4 de la bride -> liste des solutions (6 angles dans ]-π, π]).
    Méthode analytique classique pour les UR (K. Hawkins, 2013)."""
    d1, a2, a3, d4, d5, d6 = D[0], A[1], A[2], D[3], D[4], D[5]
    solutions = []

    # épaule (θ1) : le poignet (point P05) doit être à distance d4 de l'axe de la base
    p05 = T @ np.array([0.0, 0.0, -d6, 1.0])
    rayon = math.hypot(p05[0], p05[1])
    if rayon < abs(d4):
        return []
    psi = math.atan2(p05[1], p05[0])
    phi = math.acos(max(-1.0, min(1.0, d4 / rayon)))
    for s1 in (1, -1):
        t1 = psi + s1 * phi + math.pi / 2
        # poignet 2 (θ5)
        c5 = (T[0, 3] * math.sin(t1) - T[1, 3] * math.cos(t1) - d4) / d6
        if abs(c5) > 1 + 1e-9:
            continue
        for s5 in (1, -1):
            t5 = s5 * math.acos(max(-1.0, min(1.0, c5)))
            # poignet 3 (θ6) ; indéterminé si le poignet est aligné (sin θ5 = 0)
            s5v = math.sin(t5)
            if abs(s5v) < eps:
                t6 = 0.0
            else:
                Ti = np.linalg.inv(T)
                t6 = math.atan2((-Ti[1, 0] * math.sin(t1) + Ti[1, 1] * math.cos(t1)) / s5v,
                                (Ti[0, 0] * math.sin(t1) - Ti[0, 1] * math.cos(t1)) / s5v)
            # épaule (θ2), coude (θ3), poignet 1 (θ4)
            T14 = np.linalg.inv(dh(0, t1)) @ T @ np.linalg.inv(dh(4, t5) @ dh(5, t6))
            p13 = T14 @ np.array([0.0, -d4, 0.0, 1.0])
            p13 = p13[:3]
            n13 = math.hypot(p13[0], p13[1])
            c3 = (n13 * n13 - a2 * a2 - a3 * a3) / (2 * a2 * a3)
            if abs(c3) > 1 + 1e-9:
                continue
            for s3 in (1, -1):
                t3 = s3 * math.acos(max(-1.0, min(1.0, c3)))
                t2 = -math.atan2(p13[1], -p13[0]) + math.asin(max(-1.0, min(1.0, a3 * math.sin(t3) / n13)))
                T34 = np.linalg.inv(dh(1, t2) @ dh(2, t3)) @ T14
                t4 = math.atan2(T34[1, 0], T34[0, 0])
                solutions.append([ramener(v) for v in (t1, t2, t3, t4, t5, t6)])
    return solutions


def ramener(angle):
    """Angle ramené dans ]-π, π]."""
    return math.atan2(math.sin(angle), math.cos(angle))


def plus_proche(solutions, q_prec):
    """La solution la plus proche de q_prec, chaque angle déplacé de ±2π pour rester continu
    (dans les limites). Renvoie None s'il n'y a pas de solution."""
    meilleure = None
    for sol in solutions:
        q = []
        for i, v in enumerate(sol):
            # le tour (±2π) le plus proche de l'angle précédent, sans sortir des limites
            candidats = [v + k * 2 * math.pi for k in (-1, 0, 1)]
            candidats = [c for c in candidats if abs(c) <= LIMITES[i] + 1e-9] or [v]
            q.append(min(candidats, key=lambda c: abs(c - q_prec[i])))
        ecart = max(abs(q[i] - q_prec[i]) for i in range(6))
        if meilleure is None or ecart < meilleure[0]:
            meilleure = (ecart, q)
    return meilleure[1] if meilleure else None


def trajectoire(poses_bride, q_depart=DEPART):
    """Angles le long d'une suite de poses de la bride (matrices 4×4).
    Renvoie (liste d'angles, indices des poses sans solution : hors de portée)."""
    angles, hors_portee = [], []
    q = list(q_depart)
    for k, T in enumerate(poses_bride):
        suivant = plus_proche(inverse(T), q)
        if suivant is None:
            hors_portee.append(k)
        else:
            q = suivant
        angles.append(list(q))
    return angles, hors_portee
