"""Trajet de la buse pendant une pause : sortir du dessin sans passer au-dessus du béton.

L'extrusion est continue : le programme ne peut pas arrêter la pompe, le béton coule pendant
toute la pause (sauf si quelqu'un coupe la pompe à la main). Donc :
1. au bout du calque, la buse continue un peu dans le prolongement de la ligne, à hauteur de
   cordon, jusqu'à être sortie du béton ; elle monte seulement là (pas de tas sur la pièce) ;
2. buse levée, elle va jusqu'à un point d'attente à côté du dessin en passant entre les lignes
   déjà imprimées (vu de dessus, comme dans un labyrinthe) et, si possible, en évitant aussi les
   lignes à imprimer ensuite : le béton qui tombe ne doit pas se retrouver sous elles ;
3. elle attend « Continuer » (le béton fait un tas, loin de la pièce) ;
4. elle revient de la même façon, redescend juste avant le début du calque suivant et y entre
   à hauteur de cordon.

« Au-dessus du béton » : à moins de 'rayon' mm (vu de dessus) de l'axe d'un cordon.
Le chemin le plus simple est essayé d'abord (ligne droite) ; sinon on cherche un passage sur
une grille de 'pas' mm.
"""

import heapq
import math

import numpy as np
import shapely
from shapely.geometry import LineString, MultiLineString, Point, box
from shapely.ops import nearest_points, unary_union

ECART_ATTENTE = 60.0   # mm : le point d'attente est à cette distance du dessin, en plus du rayon
                       # (le béton qui coule pendant la pause y fait un tas)


def obstacles(polylignes, rayon, cadre=None):
    """Zone interdite à la buse : les cordons déjà imprimés, élargis de 'rayon' (vus de dessus),
    et tout ce qui est hors du cadre (hors de la palette ou de la portée du robot)."""
    morceaux = [LineString([p[:2] for p in poly]) for poly in polylignes if len(poly) >= 2]
    zones = [MultiLineString(morceaux).buffer(rayon, quad_segs=4)] if morceaux else []
    if cadre is not None:
        zones.append(box(*cadre.bounds).buffer(100).difference(cadre))
    if not zones:
        return None
    zone = unary_union(zones)
    shapely.prepare(zone)
    return zone


def libre(zone, a, b=None):
    """Le point a (ou le segment a -> b) ne passe pas au-dessus du béton."""
    if zone is None:
        return True
    return not zone.intersects(Point(a) if b is None else LineString([a, b]))


def degager(point, direction, zone, distance):
    """Premier point libre à 'distance' du point : d'abord droit devant (dans le prolongement de
    la ligne), puis en tournant de plus en plus. None si tout est occupé."""
    angle = math.atan2(direction[1], direction[0])
    for ecart in (0, 30, -30, 60, -60, 90, -90, 120, -120, 150, -150, 180):
        a = angle + math.radians(ecart)
        q = (point[0] + distance * math.cos(a), point[1] + distance * math.sin(a))
        if libre(zone, q):
            return q
    return None


def chemin_libre(a, b, zone, cadre, pas):
    """Chemin de a à b (vus de dessus) qui ne passe jamais au-dessus du béton.

    cadre : (xmin, ymin, xmax, ymax), là où la buse peut aller.
    Renvoie la liste des points, ou None s'il n'y a aucun passage.
    """
    if libre(zone, a, b):
        return [a, b]
    xmin, ymin, xmax, ymax = cadre
    nx, ny = int((xmax - xmin) / pas) + 1, int((ymax - ymin) / pas) + 1
    X, Y = np.meshgrid(xmin + pas * np.arange(nx), ymin + pas * np.arange(ny), indexing="ij")
    bloque = shapely.contains_xy(zone, X.ravel(), Y.ravel()).reshape(nx, ny)

    def case_libre(p):
        """La case libre la plus proche du point p (on cherche autour, jusqu'à 3 cases)."""
        i0, j0 = round((p[0] - xmin) / pas), round((p[1] - ymin) / pas)
        meilleure = None
        for i in range(i0 - 3, i0 + 4):
            for j in range(j0 - 3, j0 + 4):
                if 0 <= i < nx and 0 <= j < ny and not bloque[i, j]:
                    d = math.hypot(i - i0, j - j0)
                    if meilleure is None or d < meilleure[0]:
                        meilleure = (d, (i, j))
        return meilleure[1] if meilleure else None

    depart, arrivee = case_libre(a), case_libre(b)
    if depart is None or arrivee is None:
        return None
    # recherche du plus court chemin sur la grille (8 voisins)
    voisins = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
               (1, 1, math.sqrt(2)), (1, -1, math.sqrt(2)), (-1, 1, math.sqrt(2)), (-1, -1, math.sqrt(2))]
    estimation = lambda c: math.hypot(c[0] - arrivee[0], c[1] - arrivee[1])
    a_voir = [(estimation(depart), 0.0, depart)]
    cout = {depart: 0.0}
    venant_de = {}
    while a_voir:
        _, g, c = heapq.heappop(a_voir)
        if c == arrivee:
            break
        if g > cout.get(c, math.inf):
            continue
        for di, dj, l in voisins:
            v = (c[0] + di, c[1] + dj)
            if not (0 <= v[0] < nx and 0 <= v[1] < ny) or bloque[v]:
                continue
            if di and dj and (bloque[c[0] + di, c[1]] or bloque[c[0], c[1] + dj]):
                continue        # pas en diagonale entre deux cases occupées
            nouveau = g + l
            if nouveau < cout.get(v, math.inf):
                cout[v] = nouveau
                venant_de[v] = c
                heapq.heappush(a_voir, (nouveau + estimation(v), nouveau, v))
    if arrivee not in cout:
        return None
    cases = [arrivee]
    while cases[-1] != depart:
        cases.append(venant_de[cases[-1]])
    points = [a] + [(xmin + pas * i, ymin + pas * j) for i, j in reversed(cases)] + [b]
    return raccourcir(points, zone)


def raccourcir(points, zone, fenetre=80):
    """Retire les détours de la grille : depuis chaque point, on va directement au point le plus
    loin que l'on voit sans passer au-dessus du béton."""
    sortie, i = [points[0]], 0
    while i < len(points) - 1:
        j = min(len(points) - 1, i + fenetre)
        while j > i + 1 and not libre(zone, points[i], points[j]):
            j -= 1
        sortie.append(points[j])
        i = j
    return sortie


def point_d_attente(depuis, enveloppe, cadre, zone, rayon):
    """Point d'attente juste à côté du dessin : hors du dessin (élargi), dans le cadre (à 5 mm de
    son bord au moins), au plus près de 'depuis'. À défaut, n'importe quel point libre du cadre.
    None s'il n'y en a aucun."""
    utile = cadre.buffer(-5)
    for region in (utile.difference(enveloppe.buffer(rayon + ECART_ATTENTE, quad_segs=8)),
                   utile.difference(zone) if zone is not None else utile):
        if not region.is_empty:
            q = nearest_points(region, Point(depuis))[0]
            return (q.x, q.y)
    return None


def direction(a, b):
    n = math.dist(a[:2], b[:2])
    return ((b[0] - a[0]) / n, (b[1] - a[1]) / n) if n > 0 else (1.0, 0.0)


def trajet_de_pause(fin, avant_fin, debut, apres_debut, imprime, futur, enveloppe, cadre, rayon, pas=5.0):
    """Trajet d'une pause, vu de dessus : [fin, sortie, …, attente, …, entrée, début].

    fin, avant_fin     : dernier et avant-dernier points imprimés (None : départ du dessin)
    debut, apres_debut : premier et deuxième points du calque suivant (None : fin du dessin)
    imprime, futur     : polylignes déjà imprimées, et celles à imprimer ensuite
    enveloppe          : forme du dessin entier (vu de dessus), pour placer le point d'attente
    cadre              : là où la buse peut aller (polygone : palette dans la portée du robot)
    Renvoie {"points", "sortie", "entree", "attente", "libre"} : entre 'fin' et 'sortie', et entre
    'entree' et 'debut', la buse est à hauteur de cordon ; entre les deux, elle est levée.
    Au départ du dessin, le trajet commence au point d'attente ; à la fin, il s'y arrête.
    'libre' est faux s'il a fallu passer au-dessus du béton déjà imprimé.
    """
    essai = None
    for lignes in (list(imprime) + list(futur), list(imprime)):
        zone = obstacles(lignes, rayon, cadre)
        marge = rayon + 2.0
        ok = True
        points = []
        # on quitte le bout du cordon dans son prolongement, et l'on arrive au début du suivant
        # dans le sens où il part
        sortie = entree = None
        if fin is not None:
            sortie = degager(fin, direction(avant_fin, fin), zone, marge)
            ok = ok and sortie is not None
            sortie = sortie or tuple(fin[:2])
        if debut is not None:
            entree = degager(debut, direction(apres_debut, debut), zone, marge)
            ok = ok and entree is not None
            entree = entree or tuple(debut[:2])
        attente = point_d_attente(sortie or entree, enveloppe, cadre, zone, rayon)
        ok = ok and attente is not None
        attente = attente or sortie or entree
        if fin is not None:
            aller = chemin_libre(sortie, attente, zone, cadre.bounds, pas)
            ok = ok and aller is not None
            points += [tuple(fin[:2])] + (aller or [sortie, attente])
        else:
            points.append(attente)
        if debut is not None:
            retour = chemin_libre(attente, entree, zone, cadre.bounds, pas)
            ok = ok and retour is not None
            points += (retour or [attente, entree])[1:] + [tuple(debut[:2])]
        essai = {"points": points, "sortie": sortie, "entree": entree, "attente": attente, "libre": ok}
        if ok:
            break
    return essai
