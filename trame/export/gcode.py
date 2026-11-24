"""Export G-code pour l'imprimante delta WASP 2040 (Marlin) : des MAQUETTES à l'échelle du cordon.

La trame conçue en vraie grandeur (palette, cordon final) est imprimée réduite dans le rapport
cordon d'essai / cordon final, en X, Y ET Z (bosses, couches, pauses et proportions du cordon
comprises). Le centre de la palette va au centre du plateau rond.

Delta : origine au centre du plateau, Z = 0 au plateau. L'extrusion est continue, réglée sur le
boîtier externe : le G-code ne commande que les déplacements (pas d'axe E). Comme le robot, la
machine attend un clic sur son écran (M0) au départ (lancer l'extrusion), à chaque pause, et à la
fin (couper l'extrusion). Valeurs de la machine : config/cellule.toml, [wasp] ; voir docs/MAQUETTE.md.
À ESSAYER D'ABORD À VIDE (sans argile).
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


def rayon_utile(machine):
    """Rayon du plateau où la maquette peut aller (mm), marge comprise."""
    return machine["diametre_plateau"] / 2 - machine["marge"]


def reduire(path, machine, largeur, hauteur, largeur_essai, palette):
    """Points de la maquette : centre de la palette au centre du plateau, tout réduit de k.
    Renvoie (points, k, hauteur de la buse pour la 1re couche)."""
    k = echelle(largeur, largeur_essai)
    hb = machine["hauteur_buse"] or hauteur * k
    cx, cy = palette[0] / 2, palette[1] / 2
    points = [((p[0] - cx) * k, (p[1] - cy) * k, (p[2] if len(p) > 2 else 0.0) * k + hb) for p in path]
    return points, k, hb


def essai_maximal(path, machine, largeur, palette):
    """Le cordon d'essai le plus large pour lequel la maquette tient sur le plateau (mm)."""
    cx, cy = palette[0] / 2, palette[1] / 2
    loin = max((math.hypot(p[0] - cx, p[1] - cy) for p in path), default=0.0)
    return largeur * rayon_utile(machine) / loin if loin > 0 else largeur


def generer(path, machine, largeur, hauteur, largeur_essai, palette, entete=(), arrets=()):
    """Texte G-code de la maquette.

    path     : parcours de la buse en vraie grandeur, points (x, y, z) en mm (repère de la palette) ;
               z = hauteur au-dessus de la première couche (0 pour la première couche)
    machine  : section [wasp] de config/cellule.toml
    largeur, hauteur : cordon final (largeur, hauteur de couche), en mm
    largeur_essai    : largeur du cordon de la maquette (mm)
    palette  : (longueur, largeur) de la palette en vraie grandeur
    arrets   : [(indice dans path, message court pour l'écran, explication), …] : la machine
               s'arrête au point path[indice] et attend un clic (départ, pauses, fin)
    """
    reduits, k, hb = reduire(path, machine, largeur, hauteur, largeur_essai, palette)
    largeur_m, hauteur_m = largeur * k, hauteur * k            # cordon d'essai
    h = machine["hauteur_approche"]
    r_max = rayon_utile(machine)
    for x, y, z in reduits:
        if math.hypot(x, y) > r_max or z + h > machine["hauteur"]:
            raise ValueError("La maquette au 1:%g ne tient pas sur le plateau rond de Ø %g mm : prendre un "
                             "cordon d'essai de %.1f mm au plus." % (round(1 / k, 2), machine["diametre_plateau"],
                                                                    essai_maximal(path, machine, largeur, palette)))

    # points sans doublons ; un arrêt sur un point retiré passe au point gardé juste avant
    arret_de = {i: (court, long) for i, court, long in arrets}
    points, arrets_garde = [], {}
    for i, q in enumerate(reduits):
        if not points or math.dist(points[-1], q) >= 0.02:
            points.append(q)
        if i in arret_de:
            arrets_garde[len(points) - 1] = arret_de[i]
    if len(points) < 2:
        raise ValueError("Le chemin est vide : rien à imprimer.")

    f_imp = machine["vitesse"] * 60                   # G-code : mm/min
    f_dep = machine["vitesse_deplacement"] * 60
    longueur = sum(math.dist(a, b) for a, b in zip(points, points[1:]))

    def arreter(numero):
        court, long = arrets_garde[numero]
        return ["M400 ; attendre la fin des mouvements",
                "; %s" % ascii(long),
                "M117 %s" % ascii(court)[:20],
                "M0 %s" % ascii(court)[:20]]

    lignes = ["; G-code genere par trame-beton : NE PAS MODIFIER A LA MAIN",
              "; WASP 2040 (Marlin, delta), plateau rond %g mm, origine au centre" % machine["diametre_plateau"],
              "; Extrusion continue par le boitier externe : ce G-code ne commande que les deplacements",
              "; ESSAYER D'ABORD A VIDE (sans argile)"]
    lignes += ["; " + ascii(t) for t in entete]
    lignes += ["; MAQUETTE a l'echelle 1:%g (cordon final %g x %g mm -> essai %g x %g mm)"
               % (round(1 / k, 2), largeur, hauteur, round(largeur_m, 3), round(hauteur_m, 3)),
               "; vitesse %g mm/s : A ACCORDER avec le debit du boitier" % machine["vitesse"],
               "; %d points, %.1f m de cordon, environ %d min, %d arret(s) (clic sur l'ecran)"
               % (len(points), longueur / 1000, round(longueur / machine["vitesse"] / 60), len(arrets_garde)),
               "G21 ; millimetres",
               "G90 ; positions absolues",
               "M84 S0 ; ne jamais relacher les moteurs pendant un arret",
               "G28 ; prise d'origine (la tete monte en haut)",
               "G0 X%.2f Y%.2f Z%.2f F%d ; au-dessus du depart" % (points[0][0], points[0][1], points[0][2] + h, f_dep),
               "G0 Z%.2f F%d ; descente" % (points[0][2], f_dep)]
    if 0 in arrets_garde:
        lignes += arreter(0)
    lignes.append("G1 F%d ; vitesse d'impression" % f_imp)
    for numero, (x, y, z) in enumerate(points[1:], 1):
        lignes.append("G1 X%.2f Y%.2f Z%.2f" % (x, y, z))
        if numero in arrets_garde:
            lignes += arreter(numero)
    lignes += ["G0 Z%.2f F%d ; degagement" % (points[-1][2] + h, f_dep),
               "M400 ; attendre la fin des mouvements",
               "M117 Termine",
               "; fin", ""]
    return "\n".join(lignes)
