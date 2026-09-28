"""Repère palette -> repère robot, à partir de trois points relevés sur le pendant (CDC §7).

On amène la buse sur trois points de la palette et on relève leurs positions (repère base
du robot, en mm) :
    origine    : le coin (0, 0) de la palette
    grand_cote : un point sur le grand côté (l'axe x de la palette)
    petit_cote : un point sur le petit côté (l'axe y de la palette)
Le repère obtenu suit le plan de ces trois points : il corrige aussi un léger défaut de niveau.
"""

import math


def moins(a, b):
    return [a[i] - b[i] for i in range(3)]


def produit_vectoriel(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def scalaire(a, b):
    return sum(a[i] * b[i] for i in range(3))


def unitaire(a):
    n = math.sqrt(scalaire(a, a))
    if n == 0:
        raise ValueError("Deux points de calibration sont confondus.")
    return [v / n for v in a]


def repere_palette(origine, grand_cote, petit_cote):
    """Repère de la palette : {"origine", "x", "y", "z", "defaut_angle"} (mm, vecteurs unitaires).

    defaut_angle : écart à 90° entre les deux côtés relevés (degrés), pour repérer une erreur.
    """
    x = unitaire(moins(grand_cote, origine))
    vers_y = moins(petit_cote, origine)
    z = unitaire(produit_vectoriel(x, vers_y))
    if z[2] <= 0:
        raise ValueError("Les points de calibration donnent une palette à l'envers : "
                         "vérifie que le point du petit côté est bien à gauche du grand côté "
                         "(vu de dessus, origine en bas à gauche).")
    y = produit_vectoriel(z, x)
    angle = math.degrees(math.acos(max(-1.0, min(1.0, scalaire(x, unitaire(vers_y))))))
    return {"origine": list(origine), "x": x, "y": y, "z": z, "defaut_angle": abs(angle - 90)}


def vers_robot(repere, point):
    """Point (x, y, z) du repère palette (mm) -> repère base du robot (mm)."""
    o, x, y, z = repere["origine"], repere["x"], repere["y"], repere["z"]
    return [o[i] + point[0] * x[i] + point[1] * y[i] + point[2] * z[i] for i in range(3)]


def vecteur_rotation(colonnes):
    """Matrice de rotation (donnée par ses 3 colonnes) -> vecteur rotation (rx, ry, rz) en radians,
    comme les poses URScript."""
    (r00, r10, r20), (r01, r11, r21), (r02, r12, r22) = colonnes
    cos_angle = max(-1.0, min(1.0, (r00 + r11 + r22 - 1) / 2))
    angle = math.acos(cos_angle)
    if angle < 1e-9:
        return [0.0, 0.0, 0.0]
    if math.pi - angle < 1e-6:
        # demi-tour : l'axe se lit sur la diagonale
        axe = [math.sqrt(max((r00 + 1) / 2, 0)), math.sqrt(max((r11 + 1) / 2, 0)),
               math.sqrt(max((r22 + 1) / 2, 0))]
        # signes relatifs à partir des termes hors diagonale
        if axe[0] > 1e-6:
            axe[1] = math.copysign(axe[1], r01 + r10)
            axe[2] = math.copysign(axe[2], r02 + r20)
        elif axe[1] > 1e-6:
            axe[2] = math.copysign(axe[2], r12 + r21)
        return [a * angle for a in axe]
    s = 2 * math.sin(angle)
    axe = [(r21 - r12) / s, (r02 - r20) / s, (r10 - r01) / s]
    return [a * angle for a in axe]


def pose_ur(repere):
    """Pose URScript du repère palette : [x, y, z en m, rx, ry, rz en rad]."""
    position = [v / 1000 for v in repere["origine"]]
    return position + vecteur_rotation([repere["x"], repere["y"], repere["z"]])


def matrice(rotation):
    """Vecteur rotation (rx, ry, rz) -> colonnes de la matrice (pour les tests et l'aperçu)."""
    angle = math.sqrt(scalaire(rotation, rotation))
    if angle < 1e-12:
        return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    k = [v / angle for v in rotation]
    c, s, t = math.cos(angle), math.sin(angle), 1 - math.cos(angle)
    lignes = [
        [t * k[0] * k[0] + c, t * k[0] * k[1] - s * k[2], t * k[0] * k[2] + s * k[1]],
        [t * k[0] * k[1] + s * k[2], t * k[1] * k[1] + c, t * k[1] * k[2] - s * k[0]],
        [t * k[0] * k[2] - s * k[1], t * k[1] * k[2] + s * k[0], t * k[2] * k[2] + c],
    ]
    return [[lignes[0][j], lignes[1][j], lignes[2][j]] for j in range(3)]
