"""Export G-code pour la machine cartésienne (Klipper), plateau 700 × 700 × 700 mm.

La machine cartésienne sert de MAQUETTE : la trame conçue en vraie grandeur (palette, cordon
final) est imprimée réduite dans le rapport  cordon d'essai / cordon final, en X, Y ET Z
(bosses, couches et proportions du cordon comprises). La maquette est centrée sur le plateau.

Origine au coin avant gauche, Z = 0 au plateau. Extrusion céramique : piston + tube PTFE Ø 10 mm
+ tête malaxeuse. Axe E en mode relatif (M83), en millimètres de matière dans le tube : pour chaque
segment, E = longueur × largeur × hauteur du cordon d'essai / section du tube.
Réglage de Klipper : docs/MAQUETTE.md. Valeurs de la machine : config/cellule.toml, [cartesienne].
À ESSAYER D'ABORD À VIDE (sans béton) ET À VITESSE RÉDUITE.
"""

import math
import unicodedata


def ascii(texte):
    return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode("ascii")


def echelle(largeur_finale, largeur_essai):
    """Rapport de réduction de la maquette : cordon d'essai / cordon final."""
    if largeur_essai <= 0 or largeur_finale <= 0:
        raise ValueError("La largeur du cordon d'essai doit être positive.")
    return largeur_essai / largeur_finale


def vitesse_impression(machine, largeur_essai, hauteur_essai):
    """Vitesse d'impression (mm/s), comme Orca : débit volumique maximal / section du cordon,
    plafonnée à la vitesse maximale de la machine."""
    section = largeur_essai * hauteur_essai
    return min(machine["vitesse_max"], machine["debit_volumique_max"] / section)


def generer(path, machine, largeur, hauteur, largeur_essai, palette, entete=()):
    """Texte G-code de la maquette.

    path     : chemin en vraie grandeur, points (x, y, z) en mm dans le repère de la palette ;
               z = hauteur au-dessus de la première couche (0 pour la première couche)
    machine  : section [cartesienne] de config/cellule.toml
    largeur, hauteur : cordon final (largeur, hauteur de couche), en mm
    largeur_essai    : largeur du cordon de la maquette (mm)
    palette  : (longueur, largeur) de la palette en vraie grandeur, pour centrer la maquette
    """
    k = echelle(largeur, largeur_essai)
    largeur_m, hauteur_m = largeur * k, hauteur * k            # cordon d'essai
    # la palette réduite, centrée sur le plateau
    dx = (machine["longueur"] - palette[0] * k) / 2
    dy = (machine["largeur"] - palette[1] * k) / 2
    hb = machine["hauteur_buse"] or hauteur_m
    points = []
    for p in path:
        q = (p[0] * k + dx, p[1] * k + dy, (p[2] if len(p) > 2 else 0.0) * k + hb)
        if not points or math.dist(points[-1], q) >= 0.02:
            points.append(q)
    if len(points) < 2:
        raise ValueError("Le chemin est vide : rien à imprimer.")

    # le chemin doit tenir dans la machine
    lx, ly, lz = machine["longueur"], machine["largeur"], machine["hauteur"]
    h = machine["hauteur_approche"]
    for x, y, z in points:
        if not (0 <= x <= lx and 0 <= y <= ly and 0 <= z + h <= lz):
            raise ValueError("La maquette au 1:%g ne tient pas dans la machine (%g × %g × %g mm) : "
                             "prends un cordon d'essai plus fin." % (round(1 / k, 2), lx, ly, lz))

    section = math.pi * machine["diametre_filament"] ** 2 / 4
    e_par_mm = largeur_m * hauteur_m / section * machine["multiplicateur_extrusion"]
    vitesse = vitesse_impression(machine, largeur_m, hauteur_m)
    f_imp = vitesse * 60                       # G-code : mm/min
    f_dep = machine["vitesse_deplacement"] * 60
    longueur = sum(math.dist(a, b) for a, b in zip(points, points[1:]))

    lignes = ["; G-code genere par trame-beton : NE PAS MODIFIER A LA MAIN",
              "; Machine cartesienne (Klipper), %g x %g x %g mm, origine coin avant gauche" % (lx, ly, lz),
              "; ESSAYER D'ABORD A VIDE (sans ceramique) ET A VITESSE REDUITE"]
    lignes += ["; " + ascii(t) for t in entete]
    lignes += ["; MAQUETTE a l'echelle 1:%g (cordon final %g x %g mm -> essai %g x %g mm)"
               % (round(1 / k, 2), largeur, hauteur, largeur_m, hauteur_m),
               "; palette %g x %g mm -> %g x %g mm, centree sur le plateau"
               % (palette[0], palette[1], palette[0] * k, palette[1] * k),
               "; vitesse %.1f mm/s = debit %g mm3/s / section %.2f mm2 (plafond %g mm/s)"
               % (vitesse, machine["debit_volumique_max"], largeur_m * hauteur_m, machine["vitesse_max"]),
               "; %d points, %.1f m de cordon, environ %d min"
               % (len(points), longueur / 1000, round(longueur / vitesse / 60)),
               "; E = %.4f mm de matiere dans le tube (diametre %g mm) par mm de cordon"
               % (e_par_mm, machine["diametre_filament"]),
               "; Klipper [extruder] : max_extrude_cross_section doit valoir au moins %.1f (mm2)"
               % (largeur_m * hauteur_m * machine["multiplicateur_extrusion"] * 1.1),
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
