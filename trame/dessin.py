"""Lecture d'un dessin en calques (DXF ou SVG) et placement sur la palette.

Le dessin est imprimé tel qu'il est tracé : rien n'est découpé, fermé ni transformé.
Un calque = une série, que l'étudiant trace en une seule ligne (spirale, zigzag, boucle…).

Utilisation :
    dessin = lire_dessin(texte_du_fichier, "trame.dxf")
    dessin = lire_dessins([(texte_1, "a_vagues.dxf"), (texte_2, "b_lignes.dxf")])   # plusieurs fichiers
    dessin["calques"] -> liste de calques, rangés dans l'ordre alphabétique de leur nom :
        {"nom": "A vagues", "courbes": [[(x, y), …], …], "couleur": "#rrggbb", "fichier": "trame.dxf",
         "imprime": True}     # False : calque masqué dans le fichier, cadre, palette…

Plusieurs fichiers : certains étudiants mettent chaque calque dans son propre fichier. Les
fichiers sont superposés tels quels (ils doivent venir de la même page, ou du même plan, dans le
logiciel). Un fichier qui n'a qu'un calque prend toujours le nom du fichier (même seul) : ainsi
le nom ne change pas quand on ajoute ou retire d'autres fichiers.
    place = placer_dessin([calque["courbes"] for calque in a_imprimer], marge, palette)

Logiciels prévus : Rhino et AutoCAD (DXF), Illustrator et Inkscape (SVG). Unités : mm.
"""

import io
import math
import re
import unicodedata
import xml.etree.ElementTree as ET

import ezdxf
import svgelements
from ezdxf import colors as couleurs_dxf
from ezdxf import path as chemins_dxf
from shapely import affinity
from shapely.geometry import LineString, MultiLineString, box

# Code d'unité d'un DXF ($INSUNITS) -> nombre de mm pour une unité.
# 0 = « sans unité » : on considère que le dessin est en mm.
UNITES_DXF = {0: 1.0, 1: 25.4, 2: 304.8, 4: 1.0, 5: 10.0, 6: 1000.0}

# Calques que l'on n'imprime pas au départ (on peut les rallumer dans l'aperçu) : cadre du
# gabarit et calques des exports de l'aperçu, pour qu'un fichier exporté se réimporte.
NON_IMPRIMES = {"palette", "cadre", "gabarit", "contour", "liaisons", "bosses", "sommets des bosses",
                "chemin", "sauts", "deplacements", "pauses"}

# Éléments SVG qui ne sont pas des dessins (styles, définitions, données d'Illustrator…).
SVG = "http://www.w3.org/2000/svg"
NON_DESSIN = {"defs", "style", "metadata", "title", "desc", "namedview", "foreignObject", "script",
              "symbol", "clipPath", "mask", "pattern", "linearGradient", "radialGradient", "filter"}
LIBELLES_SVG = ["{http://www.inkscape.org/namespaces/inkscape}label",   # Inkscape
                "data-name",                                            # Illustrator
                "{http://www.serif.com/}id",                            # Affinity
                "id"]
MARQUE = "data-trame-calque"   # numéro du calque, posé sur chaque calque avant la lecture


# --- noms des calques ---------------------------------------------------------------


def simplifier_nom(nom):
    """« Délimitation » -> « delimitation » : pour comparer des noms sans accents ni majuscules."""
    sans_accents = unicodedata.normalize("NFD", nom).encode("ascii", "ignore").decode()
    return " ".join(sans_accents.lower().replace("_", " ").split())


def cle_de_tri(nom):
    """Ordre alphabétique « naturel » : calque 2 avant calque 10."""
    return [int(m) if m.isdigit() else m for m in re.split(r"(\d+)", simplifier_nom(nom))]


# --- SVG ------------------------------------------------------------------------------


def nom_local(balise):
    return balise.rsplit("}", 1)[-1] if isinstance(balise, str) else ""


def nom_svg(element):
    for cle in LIBELLES_SVG:
        if element.get(cle):
            return element.get(cle).strip()
    return ""


def est_masque(element):
    style = element.get("style", "").replace(" ", "").lower()
    return (element.get("display") == "none" or "display:none" in style
            or element.get("visibility") == "hidden" or "visibility:hidden" in style)


def montrer(element):
    """Retire « masqué » d'un calque, pour pouvoir le lire quand même."""
    element.attrib.pop("display", None)
    element.attrib.pop("visibility", None)
    style = element.get("style", "")
    style = re.sub(r"(display\s*:\s*none|visibility\s*:\s*hidden)\s*;?", "", style)
    element.set("style", style)


def reperer_calques_svg(racine):
    """Repère les calques : les groupes du premier niveau du dessin.

    On descend d'abord dans les enveloppes sans nom (le « switch » d'Illustrator, un groupe
    unique sans nom). Chaque calque reçoit la marque MARQUE ; les formes posées hors de tout
    groupe forment un calque à part. Renvoie [(nom, masqué), …] dans l'ordre du fichier.
    """
    conteneur = racine
    while True:
        enfants = [e for e in conteneur if nom_local(e.tag) not in NON_DESSIN]
        if (len(enfants) == 1 and nom_local(enfants[0].tag) in ("g", "switch")
                and not nom_svg(enfants[0])):
            conteneur = enfants[0]
        else:
            break
    calques, hors_groupe = [], None
    for element in enfants:
        if nom_local(element.tag) in ("g", "a"):
            element.set(MARQUE, str(len(calques)))
            calques.append((nom_svg(element), est_masque(element)))
            if est_masque(element):
                montrer(element)
        else:
            if hors_groupe is None:
                hors_groupe = len(calques)
                # formes hors calque : un seul calque dans Illustrator, qui met son nom sur la racine
                calques.append((racine.get("data-name", "").strip(), False))
            element.set(MARQUE, str(hors_groupe))
    return calques


def vient_d_illustrator(texte, racine):
    """Illustrator compte 72 points par pouce, au lieu des 96 pixels du web : sans correction,
    un dessin d'Illustrator arriverait à 75 % de sa taille."""
    debut = texte[:3000]
    return "Adobe Illustrator" in debut or racine.get("data-name") is not None or 'data-name="' in debut


def lire_svg(texte, pas=2.0):
    """Courbes d'un SVG, rangées par calque. Renvoie (calques, nb_remplies, page) avec
    calques = [{"nom", "masque", "courbes": [(points, couleur), …]}, …] et page = (largeur,
    hauteur) de la page en mm (le dessin est dans le rectangle (0, 0) – (largeur, hauteur))."""
    try:
        racine = ET.fromstring(texte)
    except ET.ParseError as e:
        raise ValueError("Le fichier SVG est illisible (%s)." % e) from None
    reperes = reperer_calques_svg(racine)
    ppi = 72.0 if vient_d_illustrator(texte, racine) else 96.0
    ET.register_namespace("", SVG)
    svg = svgelements.SVG.parse(io.StringIO(ET.tostring(racine, encoding="unicode")), ppi=ppi)
    mm_par_px = 25.4 / ppi
    # en SVG, y descend depuis le haut de la page ; on le compte depuis le bas, comme dans un DXF :
    # un calque exporté en SVG et un autre en DXF, depuis la même page, se superposent
    hauteur = float(svg.height) if isinstance(svg.height, (int, float)) else 0.0

    calques = [{"nom": nom, "masque": masque, "courbes": []} for nom, masque in reperes]
    sans_calque = None
    nb_remplies = 0
    for element in svg.elements():
        if not isinstance(element, svgelements.Shape):
            continue  # textes, images : ignorés
        numero = element.values.get(MARQUE)
        if numero is None:
            if sans_calque is None:
                calques.append({"nom": "", "masque": False, "courbes": []})
                sans_calque = len(calques) - 1
            numero = sans_calque
        trait = element.stroke if element.stroke is not None and element.stroke.value is not None else None
        if trait is None and element.fill is not None and element.fill.value is not None:
            nb_remplies += 1   # forme remplie sans trait : peut-être un trait vectorisé
        couleur = (trait or element.fill or svgelements.Color("black")).hexrgb
        for points in points_svg(element, mm_par_px, hauteur, pas):
            calques[int(numero)]["courbes"].append((points, couleur))
    largeur = float(svg.width) if isinstance(svg.width, (int, float)) else 0.0
    return calques, nb_remplies, (largeur * mm_par_px, hauteur * mm_par_px)


def points_svg(element, mm_par_px, hauteur, pas):
    """Une forme SVG -> listes de points (x, y) en mm, une par sous-chemin (y depuis le bas de la
    page, de hauteur 'hauteur' pixels)."""
    sortie = []
    for sous_chemin in svgelements.Path(element).as_subpaths():
        points = []
        for segment in sous_chemin:
            if isinstance(segment, (svgelements.Move, svgelements.Line, svgelements.Close)):
                points.append(segment.end)
            else:
                # courbe (Bézier, arc) : plusieurs points le long du segment
                n = max(2, math.ceil(longueur_approchee(segment) * mm_par_px / pas))
                points.extend(segment.point(k / n) for k in range(1, n + 1))
        # en SVG, y descend : on le retourne pour que le dessin ne soit pas en miroir
        points = [(p.x * mm_par_px, (hauteur - p.y) * mm_par_px) for p in points if p is not None]
        points = [p for k, p in enumerate(points) if k == 0 or p != points[k - 1]]
        if len(points) >= 2:
            sortie.append(points)
    return sortie


def longueur_approchee(segment, n=32):
    """Longueur d'une courbe SVG mesurée sur n petits morceaux droits."""
    points = [segment.point(k / n) for k in range(n + 1)]
    return sum(abs(points[k + 1] - points[k]) for k in range(n))


# --- DXF ------------------------------------------------------------------------------

TYPES_DXF = {"LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE", "ELLIPSE", "SPLINE", "HELIX"}


def entites_dxf(entites, calque_du_bloc=None, profondeur=0):
    """Les lignes et courbes d'une liste d'entités, blocs décomposés : (entité, calque).
    Dans un bloc, ce qui est sur le calque « 0 » prend le calque du bloc (règle du DXF)."""
    for entite in entites:
        type_dxf = entite.dxftype()
        calque = entite.dxf.get("layer", "0")
        if calque == "0" and calque_du_bloc:
            calque = calque_du_bloc
        if type_dxf == "INSERT" and profondeur < 10:
            try:
                yield from entites_dxf(list(entite.virtual_entities()), calque, profondeur + 1)
            except Exception:
                continue   # bloc illisible : ignoré
        elif type_dxf in TYPES_DXF:
            if type_dxf == "POLYLINE" and (entite.is_poly_face_mesh or entite.is_polygon_mesh):
                continue   # maillages : ignorés
            yield entite, calque


def couleur_dxf(entite, table):
    """Couleur d'une entité DXF en #rrggbb (couleur vraie, sinon couleur AutoCAD, sinon celle du calque)."""
    if entite.dxf.hasattr("true_color"):
        r, g, b = couleurs_dxf.int2rgb(entite.dxf.true_color)
        return "#%02x%02x%02x" % (r, g, b)
    aci = entite.dxf.get("color", 256)
    if aci in (0, 256) and entite.dxf.get("layer", "0") in table:
        aci = abs(table.get(entite.dxf.layer).dxf.get("color", 7))
    r, g, b = couleurs_dxf.aci2rgb(aci if 1 <= aci <= 255 else 7)
    return "#%02x%02x%02x" % (r, g, b)


def lire_dxf(texte, ecart=0.1):
    """Courbes d'un DXF, rangées par calque (mêmes sorties que lire_svg, sans page : None).
    Les arcs et courbes sont suivis à 'ecart' mm près. Seul l'espace objet est lu."""
    try:
        document = ezdxf.read(io.StringIO(texte))
    except Exception as e:
        raise ValueError("Le fichier DXF est illisible (%s)." % e) from None
    mm_par_unite = UNITES_DXF.get(document.header.get("$INSUNITS", 0), 1.0)
    table = document.layers
    par_nom = {}
    for entite, calque in entites_dxf(document.modelspace()):
        if simplifier_nom(calque) == "defpoints":
            continue   # calque technique d'AutoCAD, jamais imprimé
        if calque not in par_nom:
            infos = table.get(calque) if calque in table else None
            masque = bool(infos and (infos.is_off() or infos.is_frozen()))
            par_nom[calque] = {"nom": calque, "masque": masque, "courbes": []}
        try:
            chemin = chemins_dxf.make_path(entite)
        except (TypeError, ValueError):
            continue
        couleur = couleur_dxf(entite, table)
        for sous_chemin in chemin.sub_paths():
            points = [(p.x * mm_par_unite, p.y * mm_par_unite)
                      for p in sous_chemin.flattening(ecart / mm_par_unite)]
            points = [p for k, p in enumerate(points) if k == 0 or p != points[k - 1]]
            if len(points) >= 2:
                par_nom[calque]["courbes"].append((points, couleur))
    calques = list(par_nom.values())
    # sous-calques de Rhino (« Parent::Enfant ») : on garde le dernier nom s'il reste unique
    courts = [re.split(r"::|\$", c["nom"])[-1].strip() for c in calques]
    for calque, court in zip(calques, courts):
        if court and courts.count(court) == 1:
            calque["nom"] = court
    return calques, 0, None


# --- tout en un -----------------------------------------------------------------------


def lire_fichier(texte, nom_fichier):
    """Calques d'un seul fichier, sans calque vide : [{"nom", "masque", "courbes": [(points,
    couleur), …]}, …]. Un seul calque en plusieurs couleurs : chaque couleur devient un calque.
    Renvoie (calques, nombre de formes remplies sans trait, page en mm ou None)."""
    extension = nom_fichier.lower().rsplit(".", 1)[-1]
    if extension == "svg":
        calques, nb_remplies, page = lire_svg(texte)
    elif extension == "dxf":
        calques, nb_remplies, page = lire_dxf(texte)
    else:
        raise ValueError("Format non reconnu : « %s ». Importer un fichier .svg ou .dxf." % nom_fichier)

    calques = [c for c in calques if c["courbes"]]
    if not calques:
        raise ValueError("Aucune ligne dans « %s » : il ne contient que du texte, des images "
                         "ou des hachures." % nom_fichier)
    if len(calques) == 1 and len({couleur for _, couleur in calques[0]["courbes"]}) > 1:
        seul = calques[0]
        couleurs = sorted({couleur for _, couleur in seul["courbes"]})
        calques = [{"nom": "Couleur %s" % couleur, "masque": seul["masque"],
                    "courbes": [(p, c) for p, c in seul["courbes"] if c == couleur]} for couleur in couleurs]
    return calques, nb_remplies, page


def nom_court(nom_fichier):
    """« dossier/A vagues.dxf » -> « A vagues »."""
    return re.split(r"[\\/]", nom_fichier)[-1].rsplit(".", 1)[0]


def boite(calques):
    """(xmin, ymin, xmax, ymax) de toutes les courbes de ces calques."""
    return MultiLineString([LineString(courbe) for c in calques for courbe, _ in c["courbes"]]).bounds


def page_ajustee(cadre, page, part=0.03):
    """La page d'un SVG est ajustée à son dessin quand le dessin touche presque ses quatre bords
    (à 'part' de la page près) : c'est le cas d'un export sans plan de travail (« Exporter sous »
    d'Illustrator, case « Utiliser les plans de travail » décochée). La position du dessin sur
    la page ne dit alors plus rien de sa position dans le document d'origine."""
    if not page or not page[0] or not page[1]:
        return False
    largeur, hauteur = page
    xmin, ymin, xmax, ymax = cadre
    marge = part * max(largeur, hauteur)
    return xmin <= marge and ymin <= marge and largeur - xmax <= marge and hauteur - ymax <= marge


def decaler(calques, dx, dy):
    for calque in calques:
        calque["courbes"] = [([(x + dx, y + dy) for x, y in points], couleur) for points, couleur in calque["courbes"]]


def centrer_pages_ajustees(lus):
    """Plusieurs fichiers : ceux dont la page est ajustée au dessin sont centrés sur les autres
    (sur le premier, si tous le sont). lus = [(nom du fichier, calques, page)]. Renvoie les noms
    des fichiers centrés."""
    ajustes = [l for l in lus if page_ajustee(boite(l[1]), l[2])]
    if not ajustes:
        return []
    fixes = [l for l in lus if l not in ajustes] or ajustes[:1]
    cadres = [boite(calques) for _, calques, _ in fixes]
    cx = (min(c[0] for c in cadres) + max(c[2] for c in cadres)) / 2
    cy = (min(c[1] for c in cadres) + max(c[3] for c in cadres)) / 2
    for _, calques, _ in ajustes:
        xmin, ymin, xmax, ymax = boite(calques)
        decaler(calques, cx - (xmin + xmax) / 2, cy - (ymin + ymax) / 2)
    return [nom for nom, _, _ in ajustes]


def lire_dessins(fichiers):
    """Lit un ou plusieurs fichiers SVG ou DXF, fichiers = [(texte, nom du fichier), …], et réunit
    leurs calques (voir le début du module). Renvoie {"calques", "fichiers", "message"}."""
    plusieurs = len(fichiers) > 1
    lus, nb_remplies = [], 0
    for texte, nom_fichier in fichiers:
        du_fichier, n, page = lire_fichier(texte, nom_fichier)
        nb_remplies += n
        # un calque par fichier : le fichier porte le nom du calque (le calque, souvent « 0 » ou
        # « Calque 1 », ne dit rien) ; sauf un cadre ou une palette, qui garde son nom
        if len(du_fichier) == 1 and simplifier_nom(du_fichier[0]["nom"]) not in NON_IMPRIMES:
            du_fichier[0]["nom"] = nom_court(nom_fichier)
        for calque in du_fichier:
            calque["fichier"] = nom_fichier
        lus.append((nom_fichier, du_fichier, page))
    centres = centrer_pages_ajustees(lus) if plusieurs else []
    calques = [c for _, du_fichier, _ in lus for c in du_fichier]
    boites = [(nom, box(*boite(du_fichier)).buffer(1.0)) for nom, du_fichier, _ in lus]

    # noms : jamais vides, jamais deux fois le même (le même nom dans deux fichiers : le nom
    # du fichier entre parenthèses)
    for numero, calque in enumerate(calques):
        calque["nom"] = calque["nom"] or "Calque %d" % (numero + 1)
    if plusieurs:
        tous = [c["nom"] for c in calques]
        doublons = {nom for nom in tous if tous.count(nom) > 1}
        for calque in calques:
            if calque["nom"] in doublons:
                calque["nom"] = "%s (%s)" % (calque["nom"], nom_court(calque["fichier"]))
    vus = set()
    for calque in calques:
        base, k = calque["nom"], 2
        while calque["nom"] in vus:
            calque["nom"], k = "%s (%d)" % (base, k), k + 1
        vus.add(calque["nom"])

    sortie = []
    for calque in sorted(calques, key=lambda c: cle_de_tri(c["nom"])):
        couleurs = [c for _, c in calque["courbes"]]
        sortie.append({
            "nom": calque["nom"],
            "courbes": [p for p, _ in calque["courbes"]],
            "couleur": max(set(couleurs), key=couleurs.count),
            "fichier": calque["fichier"],
            "imprime": not calque["masque"] and simplifier_nom(calque["nom"]) not in NON_IMPRIMES,
        })
    message = "%d calque%s" % (len(sortie), "s" if len(sortie) > 1 else "")
    if plusieurs:
        message = "%d fichiers, %s" % (len(fichiers), message)
        if centres:
            noms = ", ".join("« %s »" % n for n in centres)
            if len(centres) == len(fichiers):
                message += (" ; %s : exportés sans plan de travail (page ajustée au dessin), donc centrés "
                            "les uns sur les autres" % noms)
            else:
                pluriel = "s" if len(centres) > 1 else ""
                message += (" ; %s : exporté%s sans plan de travail (page ajustée au dessin), donc centré%s "
                            "sur les autres fichiers" % (noms, pluriel, pluriel))
        # un fichier qui ne recouvre aucun autre : sans doute exporté avec une autre page
        for nom_fichier, cadre in boites:
            autres = [b for n, b in boites if n != nom_fichier]
            if not any(cadre.intersects(b) for b in autres):
                message += (" ; « %s » ne recouvre aucun autre fichier : vérifier que tous les fichiers "
                            "viennent de la même page (ou du même plan de travail)" % nom_fichier)
    if nb_remplies:
        message += (" ; %d forme(s) remplie(s) sans trait : si ce sont des traits vectorisés, "
                    "chaque ligne sera imprimée deux fois (son contour)" % nb_remplies)
    return {"calques": sortie, "fichiers": [nom for _, nom in fichiers], "message": message}


def lire_dessin(texte, nom_fichier):
    """Lit un seul fichier SVG ou DXF (voir lire_dessins)."""
    return lire_dessins([(texte, nom_fichier)])


# --- placement sur la palette -------------------------------------------------------


def placer_dessin(courbes_par_calque, marge=20.0, palette=(1200.0, 800.0), echelle=None, reference=None):
    """Pose le dessin au centre de la palette, en gardant 'marge' mm sur les bords.

    Sans 'echelle' (nouveau dessin) : à sa taille réelle s'il tient ; sinon tourné de 90° s'il
    tient ainsi ; sinon réduit, dans le sens où il reste le plus grand.
    echelle : l'échelle choisie (1 = taille réelle). Elle est gardée telle quelle, même si le
    dessin ne tient plus sur la palette (le message et les contrôles le disent) : l'échelle ne
    change jamais toute seule.
    reference : courbes du dessin entier (calques éteints compris), qui décident de la taille et
    de la position ; par défaut, celles des calques placés. Ainsi, éteindre un calque ne change
    ni la taille ni la place des autres.

    Renvoie {"courbes": mêmes listes que courbes_par_calque, placées ; "rotation", "echelle",
    "echelle_max" (la plus grande qui tient), "tient", "dimensions" (du dessin entier), "message"}.
    """
    lignes = [LineString(c) for courbes in courbes_par_calque for c in courbes]
    if not lignes:
        raise ValueError("Aucun calque à imprimer : rallumer au moins un calque (œil) dans la liste.")
    dessin = MultiLineString(lignes)
    entier = MultiLineString([LineString(c) for c in reference]) if reference else dessin
    utile_x, utile_y = palette[0] - 2 * marge, palette[1] - 2 * marge
    xmin, ymin, xmax, ymax = entier.bounds
    largeur, hauteur = max(xmax - xmin, 1e-6), max(ymax - ymin, 1e-6)

    echelle_droit = min(utile_x / largeur, utile_y / hauteur)
    echelle_tourne = min(utile_x / hauteur, utile_y / largeur)
    # on ne tourne le dessin que si cela lui fait vraiment gagner de la place (2 % au moins)
    tourner = echelle_tourne > echelle_droit * 1.02
    echelle_max = echelle_tourne if tourner else echelle_droit
    tient = 1 - 1e-9   # évite qu'un arrondi fasse refuser un dessin qui tient pile
    choisie = echelle is not None
    if choisie:
        echelle = max(float(echelle), 0.01)
        rotation = 90 if tourner and echelle > echelle_droit / tient else 0
    elif echelle_droit >= tient:
        rotation, echelle = 0, 1.0
    elif echelle_tourne >= tient:
        rotation, echelle = 90, 1.0
    elif not tourner:
        rotation, echelle = 0, echelle_droit
    else:
        rotation, echelle = 90, echelle_tourne

    # le dessin entier, tourné et mis à l'échelle autour de son centre, puis centré sur la palette ;
    # les calques placés suivent exactement le même mouvement
    centre = ((xmin + xmax) / 2, (ymin + ymax) / 2)

    def bouger(geometrie):
        geometrie = affinity.rotate(geometrie, rotation, origin=centre)
        return affinity.scale(geometrie, echelle, echelle, origin=centre)

    entier = bouger(entier)
    xmin, ymin, xmax, ymax = entier.bounds
    dx, dy = palette[0] / 2 - (xmin + xmax) / 2, palette[1] / 2 - (ymin + ymax) / 2
    dessin = affinity.translate(bouger(dessin), dx, dy)

    # on range les lignes placées dans leurs calques, dans le même ordre
    placees = iter(list(g.coords) for g in dessin.geoms)
    courbes = [[next(placees) for _ in calque] for calque in courbes_par_calque]
    return {
        "courbes": courbes,
        "rotation": rotation,
        "echelle": echelle,
        "echelle_max": echelle_max,
        "tient": echelle <= echelle_max / tient,
        "dimensions": (round(xmax - xmin), round(ymax - ymin)),
        "message": decrire(rotation, echelle, largeur, hauteur, choisie=choisie, maximum=echelle_max),
    }


def pourcentage(echelle):
    """0,997 -> « 99,7 » (et pas « 100 », qui laisserait croire que rien n'a changé)."""
    p = echelle * 100
    return str(round(p)) if round(p) != 100 or abs(p - 100) < 0.05 else ("%.1f" % p).replace(".", ",")


def decrire(rotation, echelle, largeur, hauteur, choisie=False, maximum=None):
    """Phrase qui explique ce qui est arrivé au dessin."""
    texte = "Dessin de %d × %d mm" % (round(largeur), round(hauteur))
    if rotation:
        texte += ", tourné de 90°"
    if maximum is not None and echelle > maximum * (1 + 1e-9):
        return texte + (", à %s %% de sa taille réelle : trop grand pour la palette, réduire la taille "
                        "(%s %% au plus)." % (pourcentage(echelle), pourcentage(maximum)))
    if choisie:
        return texte + ", à %s %% de sa taille réelle (taille choisie)." % pourcentage(echelle)
    if abs(echelle - 1) < 1e-9:
        return texte + ", gardé à sa taille réelle."
    return texte + ", réduit à %s %% pour tenir sur la palette." % pourcentage(echelle)
