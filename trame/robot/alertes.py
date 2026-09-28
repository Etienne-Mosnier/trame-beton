"""Alertes robot le long du chemin : portée, limites des articulations, singularités et
collisions simplifiées du bras et de la buse avec la palette et le socle.

Chaque alerte suit le format de trame/controles.py (titre, statut, message, points), avec en
plus « indices » : les numéros des points du programme concernés (pour l'animation).
Le modèle est volontairement simple : l'aperçu montre où passe le bras, URSim reste la référence.
"""

import math

import numpy as np

from trame.robot.cinematique import LIMITES, dh

# Seuils (degrés ou mètres)
MARGE_LIMITE = 10.0        # alerte quand une articulation est à moins de 10° de sa limite
SAUT_MAX = 20.0            # changement d'angle entre deux points voisins au-delà duquel on alerte
SINGULARITE = 5.0          # poignet ou coude à moins de 5° de l'alignement
MARGE_EPAULE = 0.05        # poignet à moins de 5 cm de l'axe de l'épaule (au-delà de d4)
RAYON_SOCLE = 0.10         # socle du robot : cylindre de 10 cm de rayon
HAUT_SOCLE = 0.18          # jusqu'à l'épaule (m)
MARGE_PALETTE = 0.002      # m au-dessus de la bâche

# Morceaux du bras : (nom, articulation de départ, d'arrivée, décalage le long de l'axe, rayon)
# Les points sont les origines des repères DH ; le décalage place le tube sur le vrai bras.
TUBES = [
    ("bras", 1, 2, 0.176, 0.075),
    ("avant-bras", 2, 3, 0.04, 0.06),
    ("poignet", 3, 4, 0.0, 0.05),
    ("poignet", 4, 5, 0.0, 0.05),
    ("poignet", 5, 6, 0.0, 0.045),
]
NOMS_ARTICULATIONS = ["base", "épaule", "coude", "poignet 1", "poignet 2", "poignet 3"]


def reperes(q):
    """Repères DH successifs (T0 = base … T6 = bride), matrices 4×4 en mètres."""
    T = [np.eye(4)]
    for i in range(6):
        T.append(T[-1] @ dh(i, q[i]))
    return T


def tubes(q, tcp, T=None):
    """Segments (a, b, rayon, nom) du bras et de la buse, dans le repère du robot (m).
    La pointe de la buse n'en fait pas partie : elle touche le cordon par construction."""
    T = T or reperes(q)
    sortie = []
    for nom, i, j, decalage, rayon in TUBES:
        axe = T[i][:3, 2] if i < 6 else np.zeros(3)
        a = T[i][:3, 3] + axe * decalage
        b = T[j][:3, 3] + axe * decalage
        sortie.append((a, b, rayon, nom))
    # buse : de la bride jusqu'à 9 cm au-dessus de la pointe
    buse = T[6] @ tcp
    haut = buse[:3, 3] - buse[:3, 2] * 0.09
    sortie.append((T[6][:3, 3], haut, 0.02, "buse"))
    return sortie


ETAPES = np.linspace(0, 1, 8)[:, None]   # 8 points le long de chaque tube


def collisions(q, tcp, vers_palette, palette, T=None):
    """Noms des morceaux du bras qui touchent la palette ou le socle.
    vers_palette : matrice 4×4 du repère robot vers le repère palette (mm)."""
    lx, ly = palette
    touches = set()
    for a, b, rayon, nom in tubes(q, tcp, T):
        p = a + (b - a) * ETAPES                      # 8 points (m), repère du robot
        # socle : cylindre vertical autour de l'axe de la base (sauf le bras, attaché à l'épaule)
        if nom != "bras" and np.any((np.hypot(p[:, 0], p[:, 1]) < RAYON_SOCLE + rayon) & (p[:, 2] < HAUT_SOCLE)):
            touches.add("%s / socle" % nom)
        # palette : sous la bâche, au-dessus de la palette
        x, y, z = (vers_palette[:3, :3] @ (p * 1000).T) + vers_palette[:3, 3:4]
        r = rayon * 1000
        if np.any((-r < x) & (x < lx + r) & (-r < y) & (y < ly + r) & (z - r < MARGE_PALETTE * 1000)):
            touches.add("%s / palette" % nom)
    return touches


def alerte(titre, indices, message_ok, message, points_du_chemin, statut="alerte"):
    if not indices:
        return {"titre": titre, "statut": "ok", "message": message_ok, "points": [], "indices": []}
    return {"titre": titre, "statut": statut, "message": message % len(indices),
            "points": [points_du_chemin[k][:2] for k in indices][:300], "indices": indices}


def analyser(angles, hors_portee, points, tcp, vers_palette, palette):
    """Toutes les alertes robot pour une suite de poses.

    angles      : angles (rad) à chaque point du programme
    hors_portee : indices sans solution (calculés par cinematique.trajectoire)
    points      : points du programme dans le repère palette (mm), pour placer les marques
    tcp         : matrice 4×4 de la buse dans le repère de la bride
    """
    limites, sauts, poignet, coude, epaule, touches = [], [], [], [], [], {}
    d4 = 0.17415
    for k, q in enumerate(angles):
        if k in hors_portee:
            continue
        if any(abs(q[i]) > LIMITES[i] - math.radians(MARGE_LIMITE) for i in range(6)):
            limites.append(k)
        if k > 0 and max(abs(q[i] - angles[k - 1][i]) for i in range(6)) > math.radians(SAUT_MAX):
            sauts.append(k)
        if abs(math.sin(q[4])) < math.sin(math.radians(SINGULARITE)):
            poignet.append(k)
        if abs(math.sin(q[2])) < math.sin(math.radians(SINGULARITE)):
            coude.append(k)
        # épaule : le centre du poignet s'approche de l'axe de la base
        T = reperes(q)
        p05 = (T[6] @ np.array([0, 0, -0.11655, 1.0]))[:2]
        if math.hypot(*p05) < d4 + MARGE_EPAULE:
            epaule.append(k)
        for t in collisions(q, tcp, vers_palette, palette, T):
            touches.setdefault(t, []).append(k)

    hors = sorted(hors_portee)
    choc = sorted({k for liste in touches.values() for k in liste})
    return [
        alerte("Tout est à portée du robot", hors, "Le robot atteint tous les points.",
               "%d point(s) hors de portée : le robot ne peut pas y amener la buse verticale.",
               points, "erreur"),
        alerte("Articulations loin de leurs limites", limites,
               "Aucune articulation ne s'approche de sa limite.",
               "%d point(s) où une articulation est à moins de 10° de sa limite.", points),
        alerte("Mouvement régulier du bras", sauts, "Le bras passe d'un point à l'autre sans à-coup.",
               "%d point(s) où une articulation tourne brusquement (plus de 20° d'un coup) : "
               "le bras change de position.", points),
        alerte("Poignet jamais aligné", poignet, "Le poignet ne s'aligne jamais.",
               "%d point(s) où le poignet est presque aligné (singularité) : "
               "le robot peut ralentir ou s'arrêter.", points),
        alerte("Coude jamais tendu", coude, "Le coude n'est jamais tendu.",
               "%d point(s) où le coude est presque tendu (singularité, bord de la zone atteignable).",
               points),
        alerte("Épaule dégagée", epaule, "Le poignet reste loin de l'axe de l'épaule.",
               "%d point(s) où le poignet passe près de l'axe de la base (singularité d'épaule).", points),
        dict(alerte("Pas de collision", choc, "Ni le bras ni la buse ne touchent la palette ou le socle.",
                    "%d point(s) où le bras touche quelque chose : " + ", ".join(sorted(touches)) + ".",
                    points, "erreur")),
    ]


def zone_atteignable(repere_vers_robot, palette, hauteurs, orientation, tcp_inverse, pas=50.0):
    """Grille de la palette : pour chaque case, True si le robot atteint le point avec la buse
    verticale à toutes les hauteurs données. repere_vers_robot(p) : point palette (mm) -> robot (mm)."""
    from trame.robot.cinematique import inverse

    lx, ly = palette
    cases = []
    y = pas / 2
    while y < ly:
        x = pas / 2
        while x < lx:
            ok = True
            for h in hauteurs:
                T = np.eye(4)
                T[:3, :3] = orientation
                T[:3, 3] = np.array(repere_vers_robot((x, y, h))) / 1000
                if not inverse(T @ tcp_inverse):
                    ok = False
                    break
            cases.append([round(x, 1), round(y, 1), ok])
            x += pas
        y += pas
    return cases
