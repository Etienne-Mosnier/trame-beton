"""Un dessin en calques -> le parcours de la buse, avec ses bosses et ses pauses.

Le dessin est imprimé tel qu'il est tracé. L'extrusion est continue : le béton coule tout le
temps, le programme ne peut pas arrêter la pompe. Le moteur :
1. enchaîne les calques dans l'ordre d'impression (enchainer). Entre deux calques :
   - « relié » : une liaison droite, imprimée, de la fin d'un calque au début du suivant ;
   - « pause » : la buse sort du dessin sans passer au-dessus du béton, attend « Continuer »
     à côté du dessin, puis revient (voir deplacements.py).
   Départ et sens sont choisis tout seuls : liaisons courtes qui évitent de passer sur une ligne
   déjà imprimée et, autour d'une pause, des bouts de calque faciles à atteindre de l'extérieur ;
2. répète le tout pour les couches 2, 3… (la trame réimprimée par-dessus elle-même) ;
3. trace le trajet de chaque pause (tracer_pauses) ;
4. pose chaque point sur le béton déjà imprimé dessous (poser) : à chaque croisement, le passage
   le plus récent monte au-dessus des plus anciens, y compris dans un même calque (une boucle
   passe par-dessus son propre début), et par-dessus le béton tombé pendant une pause.
   Les montées ont la pente des bosses : une hauteur de couche (amp) sur une largeur de cordon (d).

Utilisation :
    r = calculer_trace([courbes_du_calque_1, courbes_du_calque_2, …], largeur_cordon=10, amp=5,
                       pauses=[True, False])       # une pause après le calque 1
    r["path"]   -> tout le parcours de la buse, d'un seul tenant
    r["pauses"] -> les points d'attente, et leur place dans r["path"]
"""

import math

import numpy as np
import shapely
from shapely.geometry import LineString, MultiLineString, Point, box
from shapely.ops import nearest_points, substring

from trame.moteur.deplacements import trajet_de_pause

TOL = 0.5      # mm : deux bouts plus proches que ça se touchent (courbe fermée, pas de liaison)
PAS = 1.0      # mm : pas du calcul des hauteurs le long du chemin
RAYON = 1.0    # mm : un cordon plus proche que ça (vu de dessus) est « dessous »
PENALITE = 200.0         # mm : passer sur une ligne déjà imprimée « coûte » 200 mm de liaison en plus
LARGEUR_RECHERCHE = 16   # nombre de débuts de chemin gardés pendant la recherche du meilleur départ
MARGE_PAUSE = 5.0        # mm : pendant une pause, le béton qui tombe de la buse reste à 5 mm des cordons


# --- 1. enchaîner les courbes -----------------------------------------------------------


def est_fermee(points):
    return len(points) >= 4 and math.dist(points[0], points[-1]) < TOL


def longueur(points):
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def entrer_dans_boucle(points, depuis, ecart):
    """Courbe fermée parcourue à partir de son point le plus proche de 'depuis' (ou de son
    début), arrêtée 'ecart' mm avant de revenir à son départ : la buse ne repasse pas dessus."""
    ligne = LineString(points)
    tour_complet = ligne.length
    L = ligne.project(Point(depuis)) if depuis is not None else 0.0
    if 1e-6 < L < tour_complet - 1e-6:
        tour = list(substring(ligne, L, tour_complet).coords) + list(substring(ligne, 0, L).coords)[1:]
    else:
        tour = list(ligne.coords)
    # une petite boucle garde au moins la moitié de son tour
    fin = max(tour_complet - ecart, tour_complet / 2)
    return [tuple(p[:2]) for p in substring(LineString(tour), 0, fin).coords]


def enchainer_calque(courbes, depuis, ecart, premiere=None):
    """Les courbes d'un calque, une à une, en allant chaque fois à la plus proche.

    depuis   : point où se trouve la buse (fin du calque précédent), ou None (départ libre)
    premiere : (numéro, à l'envers) de la courbe par laquelle commencer, ou None
    Renvoie ([("liaison" ou "ligne", points), …], point d'arrivée).
    """
    restantes = list(range(len(courbes)))
    morceaux, position = [], depuis
    while restantes:
        if premiere is not None and not morceaux:
            k, inverse = premiere
        else:
            meilleur = None
            for k in restantes:
                c = courbes[k]
                if est_fermee(c):
                    options = [(LineString(c).distance(Point(position)) if position is not None else 0.0, False)]
                else:
                    options = [(math.dist(position, c[0]) if position is not None else 0.0, False),
                               (math.dist(position, c[-1]) if position is not None else 0.0, True)]
                for distance, inverse in options:
                    if meilleur is None or distance < meilleur[0]:
                        meilleur = (distance, k, inverse)
            _, k, inverse = meilleur
        restantes.remove(k)
        c = courbes[k]
        if est_fermee(c):
            points = entrer_dans_boucle(c, position, ecart)
        else:
            points = [tuple(p[:2]) for p in (reversed(c) if inverse else c)]
        if position is not None:
            if math.dist(position, points[0]) > TOL:
                morceaux.append(("liaison", [position, points[0]]))
            else:
                points[0] = position    # bouts qui se touchent : on part exactement d'où l'on est
        morceaux.append(("ligne", points))
        position = points[-1]
    return morceaux, position


def departs_possibles(courbes, nb_max):
    """Courbes (et sens) par lesquelles un calque peut commencer : les bouts les plus éloignés
    du centre du calque d'abord (un bon départ est souvent au bord du dessin)."""
    bouts = [p for c in courbes for p in (c[0], c[-1])]
    cx = sum(p[0] for p in bouts) / len(bouts)
    cy = sum(p[1] for p in bouts) / len(bouts)
    options = []
    for k, c in enumerate(courbes):
        options.append((math.dist(c[0], (cx, cy)), (k, False)))
        if not est_fermee(c):
            options.append((math.dist(c[-1], (cx, cy)), (k, True)))
    options.sort(reverse=True)
    return [o for _, o in options[:nb_max]]


def facons(courbes, depuis, ecart, centre, nb_departs):
    """Façons d'imprimer un calque à partir du point 'depuis' (None : départ libre, au début du
    dessin ou après une pause). Renvoie [(morceaux, arrivée), …]."""
    if len(courbes) == 1 and not est_fermee(courbes[0]):
        return [enchainer_calque(courbes, depuis, ecart, (0, inverse)) for inverse in (False, True)]
    if len(courbes) == 1:
        if depuis is None:
            # courbe fermée, départ libre : par son point le plus à l'extérieur du dessin
            loin = max(courbes[0], key=lambda p: math.dist(p, centre))
            suite, arrivee = enchainer_calque(courbes, loin, ecart)
            return [([m for m in suite if m[0] == "ligne"], arrivee)]
        return [enchainer_calque(courbes, depuis, ecart)]
    if depuis is None:
        return [enchainer_calque(courbes, None, ecart, d) for d in departs_possibles(courbes, nb_departs)]
    return [enchainer_calque(courbes, depuis, ecart)]


def croisements(points, imprime):
    """Nombre de fois où la polyligne passe sur une ligne déjà imprimée (sans compter ses deux
    bouts, qui touchent les lignes qu'elle relie)."""
    if not imprime or len(points) < 2:
        return 0
    x = LineString(points).intersection(MultiLineString(imprime))
    bouts = [Point(points[0]), Point(points[-1])]
    n = 0
    for g in getattr(x, "geoms", [x]):
        if g.is_empty:
            continue
        if g.geom_type != "Point" or min(g.distance(b) for b in bouts) > 1.0:
            n += 1
    return n


def cout_acces(point, imprime, enveloppe):
    """Difficulté d'atteindre un point depuis l'extérieur du dessin (pour une pause) : la
    distance jusqu'au tour du dessin, plus une pénalité par ligne imprimée à survoler."""
    q = nearest_points(enveloppe.exterior, Point(point))[0]
    segment = [tuple(point[:2]), (q.x, q.y)]
    return math.dist(*segment) + PENALITE * croisements(segment, imprime)


def enveloppe_du_dessin(calques):
    """Forme du dessin entier vue de dessus (son enveloppe convexe)."""
    lignes = [LineString(c) for courbes in calques for c in courbes if len(c) >= 2]
    return MultiLineString(lignes).convex_hull.buffer(1.0)


def enchainer(calques, ecart, pauses=None, pause_entre_couches=False):
    """calques : dans l'ordre d'impression, chacun une liste de courbes [(x, y), …].
    ecart    : distance laissée à la fin d'une courbe fermée (une largeur de cordon).
    pauses   : pauses[i] vrai -> pause après le calque i (sinon : relié).
    pause_entre_couches : la couche suivante reprend après une pause ; son début et la fin de
                          celle-ci doivent alors aussi être faciles à atteindre.

    Renvoie la suite des morceaux, dans l'ordre d'impression :
        {"calque": numéro, "nature": "ligne", "liaison" ou "pause", "points": [(x, y), …]}
    (une pause a pour points [fin du calque, début du suivant]).
    On garde, calque après calque, les meilleurs débuts de chemin (liaisons les plus courtes,
    sans passer sur une ligne déjà imprimée ; bouts accessibles autour des pauses).
    """
    calques = [[c for c in courbes if len(c) >= 2] for courbes in calques]
    pauses = list(pauses or []) + [False] * len(calques)
    nb_courbes = sum(len(c) for c in calques)
    if not nb_courbes:
        return []
    enveloppe = enveloppe_du_dessin(calques)
    centre = enveloppe.centroid.coords[0]
    grand = nb_courbes > 60
    nb_departs, largeur = (2, 2) if grand else (24, LARGEUR_RECHERCHE)

    etats = [(0.0, [], None, [])]      # coût, morceaux, position de la buse, lignes imprimées
    precedent = None
    for i, courbes in enumerate(calques):
        if not courbes:
            continue
        pause = precedent is not None and pauses[precedent]
        nouveaux = []
        for cout, morceaux, position, imprime in etats:
            for suite, arrivee in facons(courbes, None if pause else position, ecart, centre, nb_departs):
                c, m, imp = cout, list(morceaux), list(imprime)
                if pause:
                    debut = suite[0][1][0]
                    c += cout_acces(position, imp, enveloppe) + cout_acces(debut, imp, enveloppe)
                    m.append({"calque": precedent, "nature": "pause", "points": [position, debut]})
                for nature, pts in suite:
                    if nature == "liaison":
                        c += longueur(pts) + PENALITE * croisements(pts, imp)
                    m.append({"calque": i, "nature": nature, "points": pts})
                    imp.append(LineString(pts))
                nouveaux.append((c, m, arrivee, imp))
        nouveaux.sort(key=lambda e: e[0])
        etats = nouveaux[:largeur]
        precedent = i
    if pause_entre_couches:
        # la couche suivante repart du même début : il faut pouvoir sortir de la fin de celle-ci,
        # puis rejoindre son début, sans survoler ce qui est imprimé
        etats = sorted(etats, key=lambda e: e[0] + cout_acces(e[2], e[3], enveloppe)
                       + cout_acces(e[1][0]["points"][0], e[3], enveloppe))
    return etats[0][1]


def repeter(morceaux, couches, pause_entre_couches=False):
    """Couches 2, 3… : la même suite de morceaux, reprise depuis le début. Entre deux couches,
    une liaison droite, ou une pause."""
    sortie = [dict(m, couche=1) for m in morceaux]
    for couche in range(2, couches + 1):
        fin, debut = sortie[-1]["points"][-1], morceaux[0]["points"][0]
        if pause_entre_couches:
            sortie.append({"calque": sortie[-1]["calque"], "nature": "pause", "points": [fin, debut],
                           "couche": couche - 1})
        elif math.dist(fin, debut) > TOL:
            sortie.append({"calque": morceaux[0]["calque"], "nature": "liaison", "points": [fin, debut],
                           "couche": couche})
        sortie += [dict(m, couche=couche) for m in morceaux]
    return sortie


# --- 2. poser le chemin sur le béton déjà imprimé ---------------------------------------


def reechantillonner(points, pas):
    """Points tous les 'pas' mm au plus. Renvoie (points, sommets) : sommets[k] dit si le point
    k est un sommet du dessin (gardé à la fin) ou un point ajouté pour le calcul."""
    sortie, sommets = [tuple(points[0][:2])], [True]
    for a, b in zip(points, points[1:]):
        n = max(1, math.ceil(math.dist(a[:2], b[:2]) / pas))
        for k in range(1, n + 1):
            sortie.append((a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n))
            sommets.append(k == n)
    return sortie, sommets


def poser(morceaux, amp, d, exclusion=None):
    """Hauteur de chaque point imprimé : le dessus du béton déjà imprimé dessous, montées en
    pente douce.

    Un point est « au-dessus » d'un passage plus ancien s'il en est à moins de RAYON (vu de
    dessus) et s'il est plus loin que 'exclusion' le long du chemin (ce qui vient juste avant
    n'est pas dessous : c'est le cordon que l'on est en train de poser).
    Les pauses coupent le chemin : rien n'est imprimé entre deux tronçons.
    Renvoie la liste des morceaux avec leurs points en 3D (x, y, z) ; les pauses sont gardées telles quelles.
    """
    exclusion = 3 * d if exclusion is None else exclusion
    P, sommets, bornes, coupes = [], [], [], []
    nouvelle = True
    for morceau in morceaux:
        if morceau["nature"] == "pause":
            bornes.append(None)
            nouvelle = True
            continue
        pts, som = reechantillonner(morceau["points"], PAS)
        if P and not nouvelle and math.dist(P[-1], pts[0]) < 1e-6:
            debut = len(P) - 1          # le morceau part du dernier point du précédent
            pts, som = pts[1:], som[1:]
        else:
            if P:
                coupes.append(len(P))   # rien d'imprimé entre le point d'avant et celui-ci
            debut = len(P)
        nouvelle = False
        P += pts
        sommets += som
        bornes.append((debut, len(P) - 1))
    P = np.array(P, dtype=float)
    longueurs = np.hypot(*np.diff(P, axis=0).T)
    coupe = np.zeros(len(longueurs), dtype=bool)
    if coupes:
        coupe[np.array(coupes) - 1] = True
    longueurs[coupe] = 1e6             # deux tronçons sont « très loin » l'un de l'autre
    s = np.concatenate([[0.0], np.cumsum(longueurs)])

    # paires (point, segment imprimé plus ancien juste dessous)
    valides = np.flatnonzero(~coupe)
    arbre = shapely.STRtree(shapely.linestrings(np.stack([P[valides], P[valides + 1]], axis=1)))
    i_pt, i_rel = arbre.query(shapely.points(P), predicate="dwithin", distance=RAYON)
    i_seg = valides[i_rel]
    garde = s[i_seg + 1] < s[i_pt] - exclusion
    i_pt, i_seg = i_pt[garde], i_seg[garde]
    a, b = P[i_seg], P[i_seg + 1]
    ab = b - a
    long2 = (ab ** 2).sum(axis=1)
    t = np.clip(np.where(long2 > 0, ((P[i_pt] - a) * ab).sum(axis=1) / np.where(long2 > 0, long2, 1), 0), 0, 1)

    # z = dessus du béton dessous, puis montées et descentes en pente douce ; on recommence
    # tant que ça change (un passage peut reposer sur une montée calculée juste avant)
    pente = amp / d if d > 0 else 1e9
    z = np.zeros(len(P))
    for _ in range(50):
        H = np.zeros(len(P))
        if len(i_pt):
            np.maximum.at(H, i_pt, z[i_seg] + (z[i_seg + 1] - z[i_seg]) * t + amp)
        avant = np.maximum.accumulate(H + pente * s) - pente * s
        apres = np.maximum.accumulate((H - pente * s)[::-1])[::-1] + pente * s
        nouveau = np.maximum(avant, apres)
        fini = np.allclose(nouveau, z, atol=1e-6)
        z = nouveau
        if fini:
            break

    # on ne garde que les sommets du dessin et les points où la pente change
    garder = np.array(sommets)
    garder[0] = garder[-1] = True
    if len(P) > 2:
        pentes = np.diff(z) / np.maximum(np.diff(s), 1e-9)
        garder[1:-1] |= np.abs(np.diff(pentes)) > 1e-7
    sortie = []
    for morceau, borne in zip(morceaux, bornes):
        if borne is None:
            sortie.append(dict(morceau))
            continue
        debut, fin = borne
        indices = [k for k in range(debut, fin + 1) if garder[k] or k in (debut, fin)]
        points = [(round(float(P[k, 0]), 3), round(float(P[k, 1]), 3), round(float(z[k]), 3)) for k in indices]
        sortie.append(dict(morceau, points=points))
    return sortie


# --- tout en un ---------------------------------------------------------------------------


def tracer_pauses(morceaux, enveloppe, cadre, rayon):
    """Remplace chaque pause par le trajet de la buse, vu de dessus (deplacements.py) :
    {"nature": "pause", "points": [fin, sortie, …, attente, …, entrée, début], "sortie",
    "entree", "attente", "libre"}. Le béton qui tombe en chemin compte comme imprimé."""
    sortie = []
    for k, m in enumerate(morceaux):
        if m["nature"] != "pause":
            sortie.append(m)
            continue
        avant, apres = sortie[-1]["points"], morceaux[k + 1]["points"]
        imprime = [x["points"] for x in sortie]
        futur = [x["points"] for x in morceaux[k + 1:] if x["nature"] != "pause"]
        trajet = trajet_de_pause(avant[-1], avant[-2], apres[0], apres[1], imprime, futur, enveloppe, cadre, rayon)
        sortie.append(dict(m, **trajet))
    return sortie


def lever(morceau, hauteur):
    """Parcours de la buse pendant une pause : à hauteur de cordon jusqu'à la sortie, levée
    jusqu'à l'entrée, puis de nouveau à hauteur de cordon. Renvoie (points 3D, place de l'attente)."""
    points = morceau["points"]
    proche = lambda q: min(range(len(points)), key=lambda k: math.dist(points[k][:2], q))
    i_sortie, i_entree = proche(morceau["sortie"]), proche(morceau["entree"])
    i_entree = max(i_entree, i_sortie)
    haut = [(p[0], p[1], hauteur) for p in points[i_sortie:i_entree + 1]]
    parcours = points[:i_sortie + 1] + haut + points[i_entree:]
    attente = min(range(len(haut)), key=lambda k: math.dist(haut[k][:2], morceau["attente"]))
    return parcours, i_sortie + 1 + attente


def calculer_trace(calques, largeur_cordon=10.0, amp=5.0, d=None, couches=1, pauses=None,
                   levee=50.0, cadre=None):
    """Des calques à plat (dans l'ordre d'impression) au parcours 3D de la buse.

    pauses : pauses[i] vrai -> pause après le calque i ; après le dernier : entre deux couches.
    levee  : hauteur de la buse au-dessus de tout le béton imprimé, pendant une pause (mm).
    cadre  : là où la buse peut aller pendant une pause : polygone (palette dans la portée du
             robot) ou (xmin, ymin, xmax, ymax) ; par défaut, le dessin et 150 mm autour.

    Renvoie un dictionnaire proche de celui de chemin.calculer_chemin :
        path         : tout le parcours de la buse (x, y, z), d'un seul tenant
        pauses       : {"point": point d'attente, "indice": sa place dans path, "calque", "couche",
                        "libre"} pour chaque pause
        deplacements : partie levée du parcours de chaque pause (3D)
        waves        : pour chaque calque, ses morceaux 3D (lignes et liaisons), toutes couches
        lignes       : pour chaque calque, ses lignes 3D seulement
        liaisons     : liaisons droites ajoutées, 3D, avec "dans_calque" (calque en plusieurs morceaux)
        jumps        : [] ; controle, info
    """
    d = largeur_cordon if d is None else d
    couches = min(max(int(couches), 1), 5)
    pauses = list(pauses or []) + [False] * len(calques)
    dernier = max((i for i, c in enumerate(calques) if c), default=0)
    pause_entre_couches = couches > 1 and pauses[dernier]
    morceaux = enchainer(calques, largeur_cordon, pauses, pause_entre_couches)
    if not morceaux:
        return {"path": None, "pauses": [], "deplacements": [], "waves": [[] for _ in calques],
                "lignes": [[] for _ in calques], "liaisons": [], "jumps": [], "hits": [],
                "controle": {"sauts": 0, "liaisons": 0, "liaisons_dans_calque": 0, "pauses": 0,
                             "pauses_bloquees": 0},
                "info": "rien à imprimer"}

    enveloppe = enveloppe_du_dessin(calques)
    if cadre is None:
        xmin, ymin, xmax, ymax = enveloppe.bounds
        cadre = (xmin - 150, ymin - 150, xmax + 150, ymax + 150)
    if isinstance(cadre, (tuple, list)):
        cadre = box(*cadre)
    # le béton qui tombe pendant une pause ne doit pas toucher les cordons : un cordon d'écart, + 5 mm
    rayon = largeur_cordon + MARGE_PAUSE
    morceaux = tracer_pauses(repeter(morceaux, couches, pause_entre_couches), enveloppe, cadre, rayon)
    # le béton tombé pendant les pauses est posé comme le reste : les lignes suivantes montent dessus
    morceaux = poser([dict(m, nature="trajet") if m["nature"] == "pause" else m for m in morceaux], amp, d)

    path, infos_pauses, deplacements = [], [], []
    waves, lignes, liaisons = [[] for _ in calques], [[] for _ in calques], []
    plus_haut = 0.0
    for k, m in enumerate(morceaux):
        pts = m["points"]
        if m["nature"] == "trajet":
            pts, attente = lever(m, plus_haut + levee)
            debut_haut = next(i for i, p in enumerate(pts) if p[2] == plus_haut + levee)
            fin_haut = max(i for i, p in enumerate(pts) if p[2] == plus_haut + levee)
            deplacements.append(pts[debut_haut - 1:fin_haut + 2])
            decalage = len(path) - (1 if path and math.dist(path[-1], pts[0]) < 1e-6 else 0)
            infos_pauses.append({"point": pts[attente], "indice": decalage + attente, "calque": m["calque"],
                                 "couche": m["couche"], "libre": m["libre"]})
        else:
            plus_haut = max(plus_haut, max(p[2] for p in pts))
            waves[m["calque"]].append(pts)
            if m["nature"] == "ligne":
                lignes[m["calque"]].append(pts)
            else:
                avant = morceaux[k - 1] if k > 0 else None
                dans_calque = bool(avant and avant["nature"] != "trajet" and avant["calque"] == m["calque"]
                                   and avant["couche"] == m["couche"])
                liaisons.append({"points": pts, "calque": m["calque"], "dans_calque": dans_calque})
        path += pts[1:] if path and math.dist(path[-1], pts[0]) < 1e-6 else pts

    n_dans = sum(1 for l in liaisons if l["dans_calque"])
    n_bloquees = sum(1 for p in infos_pauses if not p["libre"])
    info = ["calques : %d, couches : %d" % (len(calques), couches),
            "courbes par calque : %s" % [len(c) for c in calques],
            "liaisons ajoutées : %d (dont %d dans un calque en plusieurs morceaux)" % (len(liaisons), n_dans),
            "pauses : %d (dont %d sans passage libre)" % (len(infos_pauses), n_bloquees),
            "hauteur max du béton : %.1f mm" % plus_haut,
            "parcours : 1 polyligne, %d points" % len(path)]
    return {
        "path": path,
        "pauses": infos_pauses,
        "deplacements": deplacements,
        "waves": waves,
        "lignes": lignes,
        "liaisons": liaisons,
        "jumps": [],
        "hits": [],
        "controle": {"sauts": 0, "liaisons": len(liaisons), "liaisons_dans_calque": n_dans,
                     "pauses": len(infos_pauses), "pauses_bloquees": n_bloquees},
        "info": "\n".join(info),
    }
