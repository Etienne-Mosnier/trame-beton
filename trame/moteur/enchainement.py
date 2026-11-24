"""Un dessin en calques -> un seul chemin d'impression continu, avec ses bosses.

Le dessin est imprimé tel qu'il est tracé. Le moteur :
1. enchaîne les calques dans l'ordre d'impression (enchainer) : les lignes d'un calque, puis
   celles du suivant, reliées par des liaisons droites. Départ et sens sont choisis tout seuls,
   pour que les liaisons soient les plus courtes possible ;
2. répète le tout pour les couches 2, 3… (la trame réimprimée par-dessus elle-même) ;
3. pose chaque point du chemin sur le béton déjà imprimé dessous (poser) : à chaque croisement,
   le passage le plus récent monte au-dessus des plus anciens, y compris dans un même calque
   (une boucle passe par-dessus son propre début). Les montées ont la pente des bosses :
   une hauteur de couche (amp) sur une largeur de cordon (d).

Utilisation :
    r = calculer_trace([courbes_du_calque_1, courbes_du_calque_2, …], largeur_cordon=10, amp=5)
    r["path"] -> le chemin 3D complet ; r["waves"] -> les morceaux 3D de chaque calque.
"""

import math

import numpy as np
import shapely
from shapely.geometry import LineString, Point
from shapely.ops import substring

TOL = 0.5      # mm : deux bouts plus proches que ça se touchent (courbe fermée, pas de liaison)
PAS = 1.0      # mm : pas du calcul des hauteurs le long du chemin
RAYON = 1.0    # mm : un cordon plus proche que ça (vu de dessus) est « dessous »


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

    depuis   : point où se trouve la buse (fin du calque précédent), ou None au tout début
    premiere : (numéro, à l'envers) de la courbe par laquelle commencer, ou None
    Renvoie ([("liaison" ou "ligne", points), …], point d'arrivée).
    """
    restantes = list(range(len(courbes)))
    morceaux, position = [], depuis
    while restantes:
        if premiere is not None and position is None:
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
    """Courbes (et sens) par lesquelles le dessin peut commencer : les bouts les plus éloignés
    du centre du calque d'abord (un bon départ est souvent au bord du dessin)."""
    bouts = [p for c in courbes for p in (c[0], c[-1])]
    cx = sum(p[0] for p in bouts) / len(bouts)
    cy = sum(p[1] for p in bouts) / len(bouts)
    options = []
    for k, c in enumerate(courbes):
        if est_fermee(c):
            options.append((math.dist(c[0], (cx, cy)), (k, False)))
        else:
            options.append((math.dist(c[0], (cx, cy)), (k, False)))
            options.append((math.dist(c[-1], (cx, cy)), (k, True)))
    options.sort(reverse=True)
    return [o for _, o in options[:nb_max]]


def enchainer(calques, ecart):
    """calques : dans l'ordre d'impression, chacun une liste de courbes [(x, y), …].
    ecart : distance laissée à la fin d'une courbe fermée (une largeur de cordon).

    Renvoie la suite des morceaux, dans l'ordre d'impression :
        {"calque": numéro, "nature": "ligne" ou "liaison", "points": [(x, y), …]}
    On essaie plusieurs départs et on garde celui qui fait les liaisons les plus courtes.
    """
    calques = [[c for c in courbes if len(c) >= 2] for courbes in calques]
    if not any(calques):
        return []
    premier = next(i for i, c in enumerate(calques) if c)
    nb_courbes = sum(len(c) for c in calques)
    nb_departs = 24 if nb_courbes <= 60 else 2

    def tout(depart):
        morceaux, position = [], None
        for i, courbes in enumerate(calques):
            suite, position = enchainer_calque(courbes, position, ecart, depart if i == premier else None)
            morceaux += [{"calque": i, "nature": n, "points": p} for n, p in suite]
        return morceaux

    essais = [tout(d) for d in departs_possibles(calques[premier], nb_departs)]
    return min(essais, key=lambda m: sum(longueur(x["points"]) for x in m if x["nature"] == "liaison"))


def repeter(morceaux, couches):
    """Couches 2, 3… : la même suite de morceaux, reprise depuis le début ; une liaison droite
    va de la fin d'une couche au début de la suivante."""
    sortie = [dict(m, couche=1) for m in morceaux]
    for couche in range(2, couches + 1):
        fin, debut = sortie[-1]["points"][-1], morceaux[0]["points"][0]
        if math.dist(fin, debut) > TOL:
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
    """Hauteur de chaque point : le dessus du béton déjà imprimé dessous, montées en pente douce.

    Un point est « au-dessus » d'un passage plus ancien s'il en est à moins de RAYON (vu de
    dessus) et s'il est plus loin que 'exclusion' le long du chemin (ce qui vient juste avant
    n'est pas dessous : c'est le cordon que l'on est en train de poser).
    Renvoie la liste des morceaux avec leurs points en 3D (x, y, z).
    """
    exclusion = 3 * d if exclusion is None else exclusion
    P, sommets, bornes = [], [], []
    for morceau in morceaux:
        pts, som = reechantillonner(morceau["points"], PAS)
        if P and math.dist(P[-1], pts[0]) < 1e-6:
            debut = len(P) - 1          # le morceau part du dernier point du précédent
            pts, som = pts[1:], som[1:]
        else:
            debut = len(P)
        P += pts
        sommets += som
        bornes.append((debut, len(P) - 1))
    P = np.array(P, dtype=float)
    s = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(P, axis=0).T))])

    # paires (point, segment plus ancien juste dessous)
    segments = shapely.linestrings(np.stack([P[:-1], P[1:]], axis=1))
    arbre = shapely.STRtree(segments)
    i_pt, i_seg = arbre.query(shapely.points(P), predicate="dwithin", distance=RAYON)
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
    for morceau, (debut, fin) in zip(morceaux, bornes):
        indices = [k for k in range(debut, fin + 1) if garder[k] or k in (debut, fin)]
        points = [(round(float(P[k, 0]), 3), round(float(P[k, 1]), 3), round(float(z[k]), 3)) for k in indices]
        sortie.append(dict(morceau, points=points))
    return sortie


# --- tout en un ---------------------------------------------------------------------------


def calculer_trace(calques, largeur_cordon=10.0, amp=5.0, d=None, couches=1):
    """Des calques à plat (dans l'ordre d'impression) au chemin 3D continu.

    Renvoie un dictionnaire proche de celui de chemin.calculer_chemin :
        path     : liste de points (x, y, z) ; None s'il n'y a rien à imprimer
        waves    : pour chaque calque, ses morceaux 3D (lignes et liaisons), toutes couches
        lignes   : pour chaque calque, ses lignes 3D seulement
        liaisons : liaisons droites ajoutées, 3D, avec "dans_calque" (calque en plusieurs morceaux)
        jumps    : [] (le chemin est toujours d'un seul tenant)
        controle, info
    """
    d = largeur_cordon if d is None else d
    couches = min(max(int(couches), 1), 5)
    morceaux = enchainer(calques, largeur_cordon)
    if not morceaux:
        return {"path": None, "waves": [[] for _ in calques], "lignes": [[] for _ in calques],
                "liaisons": [], "jumps": [], "hits": [],
                "controle": {"sauts": 0, "liaisons": 0, "liaisons_dans_calque": 0}, "info": "rien à imprimer"}
    morceaux = poser(repeter(morceaux, couches), amp, d)

    path, waves, lignes, liaisons = [], [[] for _ in calques], [[] for _ in calques], []
    for k, m in enumerate(morceaux):
        pts = m["points"]
        path += pts[1:] if path and pts and math.dist(path[-1], pts[0]) < 1e-6 else pts
        waves[m["calque"]].append(pts)
        if m["nature"] == "ligne":
            lignes[m["calque"]].append(pts)
        else:
            # liaison dans un calque : le calque d'avant et celui d'après sont les mêmes,
            # et ce n'est pas le passage d'une couche à la suivante
            avant = morceaux[k - 1] if k > 0 else None
            dans_calque = bool(avant and avant["calque"] == m["calque"] and avant["couche"] == m["couche"])
            liaisons.append({"points": pts, "calque": m["calque"], "dans_calque": dans_calque})

    n_dans = sum(1 for l in liaisons if l["dans_calque"])
    info = ["calques : %d, couches : %d" % (len(calques), couches),
            "courbes par calque : %s" % [len(c) for c in calques],
            "liaisons ajoutées : %d (dont %d dans un calque en plusieurs morceaux)" % (len(liaisons), n_dans),
            "hauteur max : %.1f mm" % max(p[2] for p in path),
            "path : 1 polyligne, %d points" % len(path)]
    return {
        "path": path,
        "waves": waves,
        "lignes": lignes,
        "liaisons": liaisons,
        "jumps": [],
        "hits": [],
        "controle": {"sauts": 0, "liaisons": len(liaisons), "liaisons_dans_calque": n_dans},
        "info": "\n".join(info),
    }
