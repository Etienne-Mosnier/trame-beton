"""Export G-code pour la machine cartésienne (Klipper), plateau 700 × 700 × 700 mm.

Origine au coin avant gauche, Z = 0 au plateau. Extrusion par l'axe E en mode relatif (M83) :
pour chaque segment, E = longueur × largeur × hauteur du cordon / section du filament équivalent.
Toutes les valeurs de la machine sont dans config/cellule.toml, section [cartesienne].
À ESSAYER D'ABORD À VIDE (sans béton) ET À VITESSE RÉDUITE.
"""

import math
import unicodedata


def ascii(texte):
    return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode("ascii")


def generer(path, machine, largeur, hauteur, entete=()):
    """Texte G-code du chemin.

    path    : points (x, y, z) en mm dans le repère du plateau ; z = hauteur au-dessus de la
              première couche (0 pour la première couche)
    machine : section [cartesienne] de config/cellule.toml
    largeur, hauteur : largeur du cordon et hauteur de couche (mm)
    """
    hb = machine["hauteur_buse"] or hauteur
    points = []
    for p in path:
        q = (p[0], p[1], (p[2] if len(p) > 2 else 0.0) + hb)
        if not points or math.dist(points[-1], q) >= 0.05:
            points.append(q)
    if len(points) < 2:
        raise ValueError("Le chemin est vide : rien à imprimer.")

    # le chemin doit tenir dans la machine
    lx, ly, lz = machine["longueur"], machine["largeur"], machine["hauteur"]
    h = machine["hauteur_approche"]
    for x, y, z in points:
        if not (0 <= x <= lx and 0 <= y <= ly and 0 <= z + h <= lz):
            raise ValueError("Le chemin sort de la machine (%g × %g × %g mm) au point (%.0f, %.0f, %.0f)."
                             % (lx, ly, lz, x, y, z))

    section = math.pi * machine["diametre_filament"] ** 2 / 4
    e_par_mm = largeur * hauteur / section * machine["multiplicateur_extrusion"]
    f_imp = machine["vitesse"] * 60           # G-code : mm/min
    f_dep = machine["vitesse_deplacement"] * 60
    longueur = sum(math.dist(a, b) for a, b in zip(points, points[1:]))

    lignes = ["; G-code genere par trame-beton : NE PAS MODIFIER A LA MAIN",
              "; Machine cartesienne (Klipper), %g x %g x %g mm, origine coin avant gauche" % (lx, ly, lz),
              "; ESSAYER D'ABORD A VIDE (sans beton) ET A VITESSE REDUITE"]
    lignes += ["; " + ascii(t) for t in entete]
    lignes += ["; %d points, %.1f m de cordon, environ %d min a %g mm/s"
               % (len(points), longueur / 1000, round(longueur / machine["vitesse"] / 60), machine["vitesse"]),
               "; cordon %g x %g mm, E = %.4f mm par mm de cordon" % (largeur, hauteur, e_par_mm),
               "; Klipper [extruder] : max_extrude_cross_section doit valoir au moins %.0f (mm2)"
               % (largeur * hauteur * machine["multiplicateur_extrusion"] * 1.1),
               "G21 ; millimetres",
               "G90 ; positions absolues",
               "M83 ; extrusion relative",
               "G28 ; prise d'origine",
               "G0 Z%.2f F%d" % (points[0][2] + h, f_dep),
               "G0 X%.2f Y%.2f F%d ; au-dessus du depart" % (points[0][0], points[0][1], f_dep),
               "G1 Z%.2f F%d ; descente" % (points[0][2], f_dep)]
    if machine["amorce"]:
        lignes.append("G1 E%.3f F%d ; amorce" % (machine["amorce"], f_imp))
    lignes.append("G1 F%d ; vitesse d'impression" % f_imp)
    for a, b in zip(points, points[1:]):
        e = math.dist(a, b) * e_par_mm
        lignes.append("G1 X%.2f Y%.2f Z%.2f E%.4f" % (b[0], b[1], b[2], e))
    lignes += ["G0 Z%.2f F%d ; degagement" % (points[-1][2] + h, f_dep),
               "M400 ; attendre la fin des mouvements",
               "; fin", ""]
    return "\n".join(lignes)
