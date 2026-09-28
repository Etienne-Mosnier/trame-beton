"""Génération du programme URScript (PolyScope 5).

Principes (CDC §9) :
- poses cartésiennes dans le repère de la palette : pose_trans(palette, p[...]), buse verticale ;
  le contrôleur calcule lui-même les angles des articulations ;
- mouvements linéaires raccordés (movep) à vitesse constante ; on ne redécoupe PAS le chemin
  à pas constant (les sommets des bosses sont gardés), on ajoute seulement des points dans
  les segments trop longs ;
- approche au-dessus du premier point, descente, extrusion, impression, arrêt, dégagement.

Le texte généré est en ASCII (sans accents) par prudence pour le contrôleur.
VALIDER DANS URSIM AVANT TOUT PASSAGE SUR LE ROBOT.
"""

import math
import unicodedata

from trame.robot.calibration import pose_ur, vecteur_rotation

# Écart en dessous duquel deux points consécutifs n'en font qu'un (mm).
ECART_MIN = 0.05
# Un arrondi ne prend jamais plus que cette part du segment voisin le plus court.
PART_ARRONDI = 0.45


def ascii(texte):
    """Retire les accents : « répété » -> « repete »."""
    return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode("ascii")


def nombre(v, chiffres=5):
    """Nombre URScript, toujours avec un point décimal (jamais une division entière)."""
    texte = "%.*f" % (chiffres, v)
    return "0.0" if texte.lstrip("-").strip("0.") == "" else texte


def pose(valeurs):
    return "p[%s]" % ", ".join(nombre(v) for v in valeurs)


def preparer_points(path, hauteur_buse, longueur_max):
    """Points du chemin en mm, remontés de hauteur_buse, sans doublons, segments trop longs coupés."""
    points = []
    for p in path:
        q = (p[0], p[1], (p[2] if len(p) > 2 else 0.0) + hauteur_buse)
        if points and math.dist(points[-1], q) < ECART_MIN:
            continue
        if points and longueur_max > 0:
            d = math.dist(points[-1], q)
            n = math.ceil(d / longueur_max)
            a = points[-1]
            for k in range(1, n):
                points.append(tuple(a[m] + (q[m] - a[m]) * k / n for m in range(3)))
        points.append(q)
    return points


def rayons_arrondi(points, rayon):
    """Rayon de raccord de chaque point (mm) : jamais plus que PART_ARRONDI du segment voisin
    le plus court, pour que deux arrondis ne se chevauchent pas ; 0 au premier et au dernier."""
    rayons = [0.0] * len(points)
    for k in range(1, len(points) - 1):
        voisin = min(math.dist(points[k - 1], points[k]), math.dist(points[k], points[k + 1]))
        rayons[k] = min(rayon, PART_ARRONDI * voisin)
    return rayons


def orientation_buse(rotation_z):
    """Vecteur rotation de la buse verticale, pointe en bas, tournée de rotation_z degrés."""
    t = math.radians(rotation_z)
    c, s = math.cos(t), math.sin(t)
    # Rz(t) · Rx(180°) : colonnes de la matrice
    return vecteur_rotation([[c, s, 0.0], [s, -c, 0.0], [0.0, 0.0, -1.0]])


def fonctions_extrusion(extrusion):
    """Fonctions extrusion_on() / extrusion_off() selon config/cellule.toml."""
    if not extrusion["active"]:
        return [
            "  def extrusion_on():",
            "    # extrusion desactivee (config/cellule.toml : extrusion.active = false)",
            '    textmsg("extrusion_on (desactivee)")',
            "  end",
            "  def extrusion_off():",
            '    textmsg("extrusion_off (desactivee)")',
            "  end",
        ]
    sortie = int(extrusion["sortie"])
    if sortie < 0:
        raise ValueError("Extrusion activée mais sans numéro de sortie (config/cellule.toml).")
    if extrusion["type"] == "digitale":
        marche, arret = ("set_standard_digital_out(%d, True)" % sortie,
                         "set_standard_digital_out(%d, False)" % sortie)
    elif extrusion["type"] == "analogique":
        marche = "set_standard_analog_out(%d, %s)" % (sortie, nombre(extrusion["valeur_analogique"], 3))
        arret = "set_standard_analog_out(%d, 0.0)" % sortie
    else:
        raise ValueError("Type d'extrusion inconnu : « %s » (digitale ou analogique)." % extrusion["type"])
    return [
        "  def extrusion_on():",
        "    " + marche,
        "    sleep(%s)" % nombre(extrusion["delai_depart"], 2),
        "  end",
        "  def extrusion_off():",
        "    " + arret,
        "    sleep(%s)" % nombre(extrusion["delai_arret"], 2),
        "  end",
    ]


def generer(path, repere, reglages, entete=(), simulation=False):
    """Texte du programme URScript.

    path     : chemin d'impression, points (x, y, z) en mm dans le repère de la palette
    repere   : repère de la palette (calibration.repere_palette)
    reglages : {"outil": …, "impression": …, "extrusion": …} de config/cellule.toml
               (impression.hauteur_buse déjà remplacée si elle était provisoire)
    entete   : lignes de commentaire à mettre en tête (motif, contour, valeurs provisoires…)
    simulation : True = calibration de simulation ; le programme prévient au démarrage
    """
    outil, imp, extrusion = reglages["outil"], reglages["impression"], reglages["extrusion"]
    points = preparer_points(path, imp["hauteur_buse"], imp["longueur_max_segment"])
    if len(points) < 2:
        raise ValueError("Le chemin est vide : rien à imprimer.")
    rayons = rayons_arrondi(points, imp["rayon_raccord"])
    rx, ry, rz = orientation_buse(outil.get("rotation_z", 0.0))
    tcp = [v / 1000 for v in outil["tcp"][:3]] + list(outil["tcp"][3:])
    cog = [v / 1000 for v in outil["centre_gravite"]]
    a = imp["acceleration"] / 1000
    v = imp["vitesse"] / 1000
    v_app = imp["vitesse_approche"] / 1000
    h = imp["hauteur_approche"]
    longueur = sum(math.dist(p, q) for p, q in zip(points, points[1:]))

    lignes = ["# Programme genere par trame-beton : NE PAS MODIFIER A LA MAIN",
              "# VALIDER DANS URSIM AVANT TOUT PASSAGE SUR LE ROBOT"]
    lignes += ["# " + ascii(t) for t in entete]
    lignes += ["# %d points, %.1f m de cordon, environ %d min a %g mm/s"
               % (len(points), longueur / 1000, round(longueur / imp["vitesse"] / 60), imp["vitesse"]),
               "def trame_beton():",
               "  set_tcp(%s)" % pose(tcp),
               "  set_payload(%s, [%s])" % (nombre(outil["masse_kg"], 3), ", ".join(nombre(c) for c in cog)),
               "  # repere de la palette : origine au coin (0, 0), x le long du grand cote",
               "  palette = %s" % pose(pose_ur(repere)),
               "  A = %s  # acceleration (m/s2)" % nombre(a, 4),
               "  V = %s  # vitesse d'impression (m/s)" % nombre(v, 4),
               "  VA = %s  # vitesse d'approche et de degagement (m/s)" % nombre(v_app, 4),
               "  # point de la palette en mm -> pose du robot, buse verticale vers le bas",
               "  def pt(x, y, z):",
               "    return pose_trans(palette, p[x / 1000.0, y / 1000.0, z / 1000.0, %s, %s, %s])"
               % (nombre(rx), nombre(ry), nombre(rz)),
               "  end"]
    lignes += fonctions_extrusion(extrusion)
    if simulation:
        lignes.append('  popup("Calibration de SIMULATION : ne pas lancer sur le vrai robot.", '
                      'title="trame-beton", warning=True, blocking=True)')

    def p_txt(p, dz=0.0):
        return "pt(%.2f, %.2f, %.2f)" % (p[0], p[1], p[2] + dz)

    premier, dernier = points[0], points[-1]
    lignes += ['  textmsg("trame-beton : approche")',
               "  movej(%s, a=1.0, v=0.3)" % p_txt(premier, h),
               "  movel(%s, a=A, v=VA)" % p_txt(premier),
               "  extrusion_on()",
               '  textmsg("trame-beton : impression")']
    for p, r in zip(points[1:-1], rayons[1:-1]):
        lignes.append("  movep(%s, a=A, v=V, r=%s)" % (p_txt(p), nombre(r / 1000, 5)))
    lignes += ["  movel(%s, a=A, v=V)" % p_txt(dernier),
               "  extrusion_off()",
               "  movel(%s, a=A, v=VA)" % p_txt(dernier, h),
               '  textmsg("trame-beton : fini")',
               "end",
               "trame_beton()",
               ""]
    return "\n".join(lignes)
