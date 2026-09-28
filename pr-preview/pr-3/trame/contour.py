"""Import du contour (SVG/DXF), fermeture et mise à l'échelle dans la palette.

Utilisation :
    resultat = charger_contour(texte_du_fichier, "forme.svg")
    resultat["contour"]   -> Polygon shapely, en mm, dans le repère de la palette
    resultat["message"]   -> phrase en français à afficher dans l'aperçu

Repère de la palette : origine (0, 0) sur un coin, x le long du grand côté (1200 mm),
y le long du petit côté (800 mm).
"""

import io
import math

import ezdxf
import svgelements
from ezdxf import path as chemins_dxf
from shapely import affinity
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union

# Un SVG est lu en pixels à 96 par pouce (norme CSS, Inkscape).
MM_PAR_PIXEL = 25.4 / 96

# Code d'unité d'un DXF ($INSUNITS) -> nombre de mm pour une unité.
# 0 = « sans unité » : on considère que le dessin est en mm.
UNITES_DXF = {0: 1.0, 1: 25.4, 2: 304.8, 4: 1.0, 5: 10.0, 6: 1000.0}

# Écart en dessous duquel une courbe presque fermée est considérée comme fermée (mm).
TOLERANCE_FERMETURE = 0.5


# --- lecture des fichiers : chaque courbe devient une liste de points (x, y) en mm ---


def lire_svg(texte, pas=2.0):
    """Toutes les courbes d'un SVG, découpées en points tous les 'pas' mm environ."""
    svg = svgelements.SVG.parse(io.StringIO(texte))
    courbes = []
    for element in svg.elements():
        if not isinstance(element, svgelements.Shape):
            continue  # textes, images, groupes : ignorés
        for sous_chemin in svgelements.Path(element).as_subpaths():
            points = []
            for segment in sous_chemin:
                if isinstance(segment, (svgelements.Move, svgelements.Line, svgelements.Close)):
                    points.append(segment.end)
                else:
                    # courbe (Bézier, arc) : plusieurs points le long du segment
                    n = max(2, math.ceil(longueur_approchee(segment) * MM_PAR_PIXEL / pas))
                    for k in range(1, n + 1):
                        points.append(segment.point(k / n))
            # en SVG, y descend : on le retourne pour que le dessin ne soit pas en miroir
            points = [(p.x * MM_PAR_PIXEL, -p.y * MM_PAR_PIXEL) for p in points if p is not None]
            if len(points) >= 2:
                courbes.append(points)
    return courbes


def longueur_approchee(segment, n=32):
    """Longueur d'une courbe SVG mesurée sur n petits morceaux droits.
    (segment.length() de svgelements est très lent sur les arcs.)"""
    points = [segment.point(k / n) for k in range(n + 1)]
    return sum(abs(points[k + 1] - points[k]) for k in range(n))


def lire_dxf(texte, ecart=0.1):
    """Toutes les courbes d'un DXF texte ; les arcs sont suivis à 'ecart' mm près."""
    document = ezdxf.read(io.StringIO(texte))
    mm_par_unite = UNITES_DXF.get(document.header.get("$INSUNITS", 0), 1.0)
    courbes = []
    for entite in document.modelspace():
        try:
            chemin = chemins_dxf.make_path(entite)
        except TypeError:
            continue  # textes, cotes, hachures : ignorés
        for sous_chemin in chemin.sub_paths():
            points = [(p.x * mm_par_unite, p.y * mm_par_unite)
                      for p in sous_chemin.flattening(ecart / mm_par_unite)]
            if len(points) >= 2:
                courbes.append(points)
    return courbes


# --- choix du contour ---------------------------------------------------------------


def plus_grand_contour(courbes):
    """Le plus grand contour fermé parmi les courbes.

    Une courbe dont les deux bouts se touchent (à TOLERANCE_FERMETURE près) est fermée.
    S'il n'y en a aucune, on essaie d'assembler les courbes ouvertes (par exemple
    quatre lignes séparées qui forment un rectangle).
    """
    formes = []
    ouvertes = []
    for points in courbes:
        (x0, y0), (x1, y1) = points[0], points[-1]
        if len(points) >= 4 and math.hypot(x1 - x0, y1 - y0) <= TOLERANCE_FERMETURE:
            # buffer(0) répare une forme qui se recoupe elle-même
            forme = Polygon(points).buffer(0)
            formes.extend(getattr(forme, "geoms", [forme]))
        else:
            ouvertes.append(LineString(points))

    if not formes and ouvertes:
        formes = list(polygonize(unary_union(ouvertes)))

    formes = [f for f in formes if not f.is_empty and f.area > 0]
    if not formes:
        raise ValueError("Aucun contour fermé dans le fichier : vérifie que la forme "
                         "est bien fermée (les deux bouts de la ligne doivent se toucher).")
    plus_grande = max(formes, key=lambda f: f.area)
    return Polygon(plus_grande.exterior)  # les trous éventuels sont ignorés


# --- placement sur la palette -------------------------------------------------------


def placer(contour, marge=20.0, palette=(1200.0, 800.0), remplir=False):
    """Pose le contour au centre de la palette, en gardant 'marge' mm sur les bords.

    1. S'il tient à sa taille réelle, il est gardé tel quel.
    2. Sinon, s'il tient une fois tourné de 90°, il est tourné.
    3. Sinon, il est réduit, dans le sens où il reste le plus grand.
    remplir = True : la forme est agrandie ou réduite pour occuper toute la palette.
    """
    utile_x = palette[0] - 2 * marge
    utile_y = palette[1] - 2 * marge
    xmin, ymin, xmax, ymax = contour.bounds
    largeur, hauteur = xmax - xmin, ymax - ymin

    # plus grande échelle possible sans tourner, et en tournant de 90°
    echelle_droit = min(utile_x / largeur, utile_y / hauteur)
    echelle_tourne = min(utile_x / hauteur, utile_y / largeur)
    tient = 1 - 1e-9  # évite qu'un arrondi fasse refuser une forme qui tient pile

    if not remplir and echelle_droit >= tient:
        rotation, echelle = 0, 1.0
    elif not remplir and echelle_tourne >= tient:
        rotation, echelle = 90, 1.0
    elif echelle_droit >= echelle_tourne:
        rotation, echelle = 0, echelle_droit
    else:
        rotation, echelle = 90, echelle_tourne

    forme = affinity.rotate(contour, rotation, origin="center")
    forme = affinity.scale(forme, echelle, echelle, origin="center")
    # centre de la forme au centre de la palette
    xmin, ymin, xmax, ymax = forme.bounds
    forme = affinity.translate(forme, palette[0] / 2 - (xmin + xmax) / 2,
                               palette[1] / 2 - (ymin + ymax) / 2)

    return {
        "contour": forme,
        "rotation": rotation,
        "echelle": echelle,
        "message": decrire(rotation, echelle, largeur, hauteur),
    }


def decrire(rotation, echelle, largeur, hauteur):
    """Phrase qui explique à l'étudiant ce qui est arrivé à sa forme."""
    taille = "Forme de %d × %d mm" % (round(largeur), round(hauteur))
    if rotation:
        taille += ", tournée de 90°"
    if abs(echelle - 1) < 1e-9:
        return taille + ", gardée à sa taille réelle."
    if echelle < 1:
        return taille + ", réduite à %d %% pour tenir sur la palette." % round(echelle * 100)
    return taille + ", agrandie à %d %% pour remplir la palette." % round(echelle * 100)


# --- tout en un ---------------------------------------------------------------------


def charger_contour(texte, nom_fichier, marge=20.0, palette=(1200.0, 800.0), remplir=False):
    """Lit un fichier SVG ou DXF, garde le plus grand contour fermé et le pose sur la palette."""
    extension = nom_fichier.lower().rsplit(".", 1)[-1]
    if extension == "svg":
        courbes = lire_svg(texte)
    elif extension == "dxf":
        courbes = lire_dxf(texte)
    else:
        raise ValueError("Format non reconnu : « %s ». Utilise un fichier .svg ou .dxf."
                         % nom_fichier)
    contour = plus_grand_contour(courbes)
    return placer(contour, marge, palette, remplir)
