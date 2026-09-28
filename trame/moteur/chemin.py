"""Enchaînement de toutes les courbes en un seul chemin continu le long du contour.

Port fidèle de la seconde moitié de reference/vagues_ghx.py : découpe par le contour,
couloirs (lane), liaisons le long du bord sans repasser au même endroit, chemin final,
sauts (jumps) et bilan CONTRÔLE.

Correspondance avec le script d'origine :
    clip              -> decouper
    inside, link_ok   -> dedans, liaison_dans_forme
    bpos              -> position_bord
    arc_parts         -> morceaux_arc
    arc_free          -> arc_libre
    arc_points        -> points_arc
    plan_link         -> preparer_liaison
    order_and_chain   -> enchainer_contour      (route = "contour")
    attach            -> accrocher
    zigzag_chain      -> enchainer_zigzag       (route = "zigzag")
    chrono_chain      -> enchainer_chrono       (route = "chrono" et "series")
    set_boundary      -> changer_bord
    outset            -> decaler_vers_exterieur
    extend_to_lane    -> prolonger_jusqu_au_couloir
    tout le reste     -> calculer_chemin

L'état partagé du script (contour courant, portions de bord utilisées, compteurs…) est
rangé dans un dictionnaire « ctx » passé à chaque fonction.

Le contour est une polyligne fermée : son point de départ et son sens comptent (comme
la couture et le sens d'une courbe Rhino), car les liaisons sont repérées le long du bord.
"""

import math
import random

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import split

from trame.moteur import croisements
from trame.moteur.croisements import en3d, supprimer_courts

# Réglages propres au chemin (ceux de reference/betonrobot.ghx) ;
# les réglages des bosses sont dans croisements.REGLAGES.
REGLAGES = {
    "res": 2.0,          # pas des points des liaisons le long du bord (mm)
    "link": 0.0,         # longueur max d'une liaison directe ; 0 = automatique
    "lane": 5.0,         # décalage vers l'extérieur du bord entre deux séries (mm)
    "route": "series",   # "series", "chrono", "zigzag" ou "contour"
    "hop": 0.0,          # hauteur de levée pendant les sauts (mm)
    "zigzag": True,      # True = un seul chemin continu
}


# --- petits calculs sur les points (x, y, z) -----------------------------------------


def entre(p, q, s):
    """Point à la fraction s du segment p -> q."""
    return tuple(p[m] + (q[m] - p[m]) * s for m in range(3))


def lever(p, h):
    return (p[0], p[1], p[2] + h)


def longueur(points):
    return sum(math.dist(points[k], points[k + 1]) for k in range(len(points) - 1))


# --- contour courant ----------------------------------------------------------------


def changer_bord(ctx, anneau):
    """Change le contour utilisé pour les liaisons (et remet à zéro sa mémoire)."""
    ctx["bord"] = LineString([p[:2] for p in anneau])
    ctx["forme"] = Polygon([p[:2] for p in anneau])
    ctx["L"] = ctx["bord"].length
    ctx["cache"] = {}
    ctx["used"] = []


def point_bord(ctx, l):
    """Point du contour à la longueur l (PointAtLength, en faisant le tour)."""
    p = ctx["bord"].interpolate(l % ctx["L"])
    return (p.x, p.y, 0.0)


def dedans(ctx, p):
    """Le point est dans la forme ou sur son bord (à tol près)."""
    if ctx["bord"] is None:
        return True
    q = Point(p[0], p[1])
    return ctx["forme"].contains(q) or ctx["bord"].distance(q) <= ctx["reg"]["tol"]


def liaison_dans_forme(ctx, p, q):
    """Le segment de liaison p -> q reste-t-il dans le contour ? (link_ok)"""
    if ctx["bord"] is None:
        return True
    return all(dedans(ctx, entre(p, q, s)) for s in (0.25, 0.5, 0.75))


def position_bord(ctx, pt):
    """Position d'un point sur le contour : (longueur depuis le début, distance au contour)."""
    cle = (round(pt[0], 6), round(pt[1], 6), round(pt[2], 6))
    if cle not in ctx["cache"]:
        l = ctx["bord"].project(Point(pt[0], pt[1]))
        ctx["cache"][cle] = (l, math.dist(pt, point_bord(ctx, l)))
    return ctx["cache"][cle]


def morceaux_arc(ctx, s, long):
    L = ctx["L"]
    s = s % L
    e = s + long
    return [(s, e)] if e <= L else [(s, L), (0.0, e - L)]


def arc_libre(ctx, s, long):
    """La portion de bord [s, s + long] n'a pas encore servi de liaison."""
    eps = max(10 * ctx["reg"]["tol"], 0.2)
    for a, b in morceaux_arc(ctx, s, long):
        for c, d in ctx["used"]:
            if min(b, d) - max(a, c) > eps:
                return False
    return True


def points_arc(ctx, s, long, en_arriere):
    """Points le long du contour à partir de la longueur s, sur 'long' (arc_points)."""
    pas = max(ctx["reg"]["res"], 0.5)
    n = int(long / pas)
    sortie = []
    for k in range(0, n + 2):
        u = long * k / float(n + 1)
        sortie.append(point_bord(ctx, (s - u) if en_arriere else (s + u)))
    return sortie


def decouper(ctx, points):
    """Garde seulement les morceaux de la courbe à l'intérieur du contour (clip)."""
    if ctx["bord"] is None:
        return [points]
    ligne = LineString([p[:2] for p in points])
    tol = ctx["reg"]["tol"]
    sortie = []
    for morceau in split(ligne, ctx["bord"]).geoms:
        if morceau.length <= tol:
            continue
        milieu = morceau.interpolate(0.5, normalized=True)
        # strictement à l'intérieur (pas sur le bord)
        if ctx["forme"].contains(milieu) and ctx["bord"].distance(milieu) > tol:
            sortie.append([en3d(p) for p in morceau.coords])
    return sortie


def decaler_vers_exterieur(anneau, dist):
    """Contour décalé de 'dist' vers l'EXTÉRIEUR, coins arrondis (outset).

    Le résultat garde le sens du contour d'origine et commence en face de son départ,
    comme le décalage de Rhino.
    """
    if dist <= 0:
        return anneau
    forme = Polygon([p[:2] for p in anneau])
    # 32 segments par quart de cercle : proche de l'arc exact de Rhino
    decale = forme.buffer(dist, quad_segs=32, join_style="round").exterior
    coords = list(decale.coords)[:-1]
    # même sens de parcours que le contour d'origine
    if (Polygon(coords).exterior.is_ccw) != (forme.exterior.is_ccw):
        coords.reverse()
    # départ : le point du nouveau contour le plus proche du départ d'origine
    nouveau = LineString(coords + [coords[0]])
    l = nouveau.project(Point(anneau[0][:2]))
    depart = nouveau.interpolate(l)
    cumul = 0.0
    apres, avant = [], []
    for k in range(len(coords)):
        if k > 0:
            cumul += math.dist(coords[k - 1], coords[k])
        (apres if cumul > l else avant).append(coords[k])
    tour = [(depart.x, depart.y)] + apres + avant + [(depart.x, depart.y)]
    return [en3d(p) for p in supprimer_courts(tour, 1e-9)]


def prolonger_jusqu_au_couloir(ctx, points, dist):
    """Prolonge la courbe en ligne droite à ses deux bouts, puis la recoupe sur le contour
    courant (le couloir de la série) : elle s'arrête sur sa voie (extend_to_lane)."""
    tol = ctx["reg"]["tol"]
    if dist <= 0 or math.dist(points[0], points[-1]) < tol:
        return [points]
    a, b = points[0], points[1]
    y, z = points[-2], points[-1]
    la, lz = math.dist(a, b), math.dist(y, z)
    if la == 0 or lz == 0:
        return [points]
    debut = tuple(a[m] - (b[m] - a[m]) / la * dist for m in range(3))
    fin = tuple(z[m] + (z[m] - y[m]) / lz * dist for m in range(3))
    prolongee = [debut] + list(points) + [fin]
    milieu = LineString([p[:2] for p in points]).interpolate(0.5, normalized=True)
    for morceau in decouper(ctx, prolongee):
        if LineString([p[:2] for p in morceau]).distance(milieu) < 10 * tol:
            return [morceau]
    return [points]


# --- liaisons -----------------------------------------------------------------------


def preparer_liaison(ctx, p, q, dist, max_link):
    """Meilleure liaison p -> q (plan_link).
    Renvoie (coût, libre, points, arc) ; points = [] pour une liaison directe,
    (début, longueur, en_arriere) pour une liaison le long du bord, None pour un saut ;
    arc = (début, longueur) de bord à marquer comme utilisé, ou None."""
    res = ctx["reg"]["res"]
    if dist <= max_link and liaison_dans_forme(ctx, p, q):
        arc = None
        if ctx["bord"] is not None:
            lp, dp = position_bord(ctx, p)
            lq, dq = position_bord(ctx, q)
            if dp < 2 * res and dq < 2 * res:      # extrémités sur le bord
                L = ctx["L"]
                avant = (lq - lp) % L
                arc = (lp, avant) if avant <= L - avant else (lq, L - avant)
        libre = arc is None or arc_libre(ctx, *arc)
        return (dist, libre, [], arc)
    if ctx["bord"] is None:
        return (dist, False, None, None)           # pas de contour : saut
    L = ctx["L"]
    lp, dp = position_bord(ctx, p)
    lq, dq = position_bord(ctx, q)
    avant = (lq - lp) % L
    arriere = L - avant
    options = [(avant + dp + dq, arc_libre(ctx, lp, avant), False, (lp, avant)),
               (arriere + dp + dq, arc_libre(ctx, lq, arriere), True, (lq, arriere))]
    # on préfère un sens libre ; à défaut le plus court
    options.sort(key=lambda o: (not o[1], o[0]))
    cout, libre, en_arriere, arc = options[0]
    spec = (lp, avant if not en_arriere else arriere, en_arriere)
    return (cout, libre, spec, arc)


def lever_liaison(ctx, pts):
    """Liaison qui repasse sur une portion déjà utilisée : on la lève de 'hop'."""
    ctx["overlaps"] += 1
    hop = ctx["reg"]["hop"]
    if hop > 0:
        pts = [pts[0]] + [lever(x, hop) for x in pts] + [pts[-1]]
    return pts


def enchainer_contour(ctx, polys, paths):
    """Enchaîne les courbes d'une série à la suite du chemin en cours (order_and_chain).
    À chaque étape on choisit la courbe suivante dont la liaison est la plus courte
    SANS repasser sur une portion de contour déjà utilisée."""
    left = [list(p) for p in polys if len(p) > 1]
    if not left:
        return paths

    max_link = ctx["reg"]["link"]
    if max_link <= 0:
        near = []
        for a_idx, a in enumerate(left):
            ds = [min(math.dist(a[-1], b[0]), math.dist(a[-1], b[-1]))
                  for b_idx, b in enumerate(left) if b_idx != a_idx]
            if ds:
                near.append(min(ds))
        near.sort()
        max_link = 2.0 * near[len(near) // 2] if near else float("inf")

    if not paths:
        paths.append(left.pop(0))
    while left:
        end = paths[-1][-1]
        best = None
        for idx, p in enumerate(left):
            for rev, q in ((False, p[0]), (True, p[-1])):
                cout, libre, pts, arc = preparer_liaison(ctx, end, q, math.dist(end, q), max_link)
                cle = (not libre, cout)
                if best is None or cle < best[0]:
                    best = (cle, idx, rev, pts, arc, libre)
        _, idx, rev, pts, arc, libre = best
        nxt = left.pop(idx)
        if rev:
            nxt.reverse()
        if pts is None:
            paths.append(nxt)                     # pas de contour : nouveau morceau
            continue
        if pts:
            pts = points_arc(ctx, *pts)
            if not libre:
                pts = lever_liaison(ctx, pts)
            ctx["routed"] += 1
            paths[-1].extend(pts)
        if arc is not None:
            ctx["used"].extend(morceaux_arc(ctx, *arc))
        paths[-1].extend(nxt)
    return paths


def accrocher(ctx, paths, pts, max_link):
    """Ajoute la courbe 'pts' (déjà orientée) au chemin, avec une liaison directe si elle
    est courte et reste dans la forme, sinon en longeant le contour (attach)."""
    if not paths:
        paths.append(list(pts))
        return
    end = paths[-1][-1]
    cout, libre, spec, arc = preparer_liaison(ctx, end, pts[0], math.dist(end, pts[0]), max_link)
    if spec is None:                       # pas de contour et saut long
        paths.append(list(pts))
        return
    if spec:
        route_pts = points_arc(ctx, *spec)
        if not libre:
            route_pts = lever_liaison(ctx, route_pts)
        ctx["routed"] += 1
        paths[-1].extend(route_pts)
    if arc is not None:
        ctx["used"].extend(morceaux_arc(ctx, *arc))
    paths[-1].extend(pts)


def enchainer_zigzag(ctx, polys, paths):
    """Zigzag par ZONES (zigzag_chain) : la forme est découpée en zones où chaque ligne
    n'a qu'un seul morceau ; on fait un zigzag complet dans une zone, puis on passe à
    la zone suivante la plus proche (en longeant le contour si besoin)."""
    reg = ctx["reg"]
    tol, fuse = reg["tol"], reg["fuse"]
    left = [list(p) for p in polys if len(p) > 1]
    if not left:
        return paths

    def ends_mid(p):
        a, b = p[0], p[-1]
        return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)

    if all(math.dist(p[0], p[-1]) < tol for p in left):
        # courbes fermées (offsets) : de la plus petite à la plus grande
        for p in sorted(left, key=longueur):
            if paths:
                end = paths[-1][-1]
                if math.dist(end, p[-1]) < math.dist(end, p[0]):
                    p.reverse()
            accrocher(ctx, paths, p, float("inf"))
        return paths

    # direction moyenne (en plan) et normale
    dx, dy = 0.0, 0.0
    for p in left:
        vx, vy = p[-1][0] - p[0][0], p[-1][1] - p[0][1]
        n = math.hypot(vx, vy)
        if n == 0:
            continue
        vx, vy = vx / n, vy / n
        if vx * dx + vy * dy < 0:
            vx, vy = -vx, -vy
        dx, dy = dx + vx, dy + vy
    n = math.hypot(dx, dy)
    dx, dy = (dx / n, dy / n) if n > 0 else (1.0, 0.0)
    nx, ny = -dy, dx                       # Z ^ direction

    def across(p):
        mx, my = ends_mid(p)
        return mx * nx + my * ny

    def span(p):
        u = p[0][0] * dx + p[0][1] * dy
        w = p[-1][0] * dx + p[-1][1] * dy
        return (min(u, w), max(u, w))

    # 1. rangées (même ligne de contour)
    items = sorted(left, key=across)
    rows = []
    for p in items:
        if rows and abs(across(p) - across(rows[-1][-1])) <= max(fuse, 10 * tol):
            rows[-1].append(p)
        else:
            rows.append([p])
    for r in rows:
        r.sort(key=lambda p: span(p)[0])

    gaps = sorted(abs(across(rows[k + 1][0]) - across(rows[k][0]))
                  for k in range(len(rows) - 1))
    spacing = gaps[len(gaps) // 2] if gaps else 1.0
    max_link = reg["link"]
    if max_link <= 0:
        max_link = 3.0 * spacing

    # 2. zones : un morceau passe dans la zone du morceau de la rangée précédente
    #    qu'il chevauche, seulement si ce lien est unique dans les deux sens
    zones = []
    prev = []
    for r in rows:
        cand = []
        for p in r:
            a0, a1 = span(p)
            cand.append([z for z, q in prev
                         if min(a1, span(q)[1]) - max(a0, span(q)[0]) > 0])
        count = {}
        for zs in cand:
            for z in zs:
                count[z] = count.get(z, 0) + 1
        cur = []
        for p, zs in zip(r, cand):
            if len(zs) == 1 and count[zs[0]] == 1:
                zones[zs[0]].append(p)
                cur.append((zs[0], p))
            else:
                zones.append([p])
                cur.append((len(zones) - 1, p))
        prev = cur

    # 3. chemin d'une zone depuis un point de départ donné
    def zone_path(zone, from_last_row, start_pt):
        seq = list(reversed(zone)) if from_last_row else list(zone)
        out = []
        for k, p in enumerate(seq):
            p = list(p)
            ref = start_pt if k == 0 else out[-1][-1]
            if math.dist(ref, p[-1]) < math.dist(ref, p[0]):
                p.reverse()
            out.append(p)
        return out

    # 4. enchaînement des zones : à chaque fois la plus proche
    remaining = list(range(len(zones)))
    while remaining:
        best = None
        for zi in remaining:
            z = zones[zi]
            for last in (False, True):
                first_piece = z[-1] if last else z[0]
                for sp in (first_piece[0], first_piece[-1]):
                    if paths:
                        end = paths[-1][-1]
                        c, libre, _, _ = preparer_liaison(ctx, end, sp, math.dist(end, sp), max_link)
                        cle = (not libre, c)
                    else:
                        cle = (False, 0.0)
                    if best is None or cle < best[0]:
                        best = (cle, zi, last, sp)
        _, zi, last, sp = best
        remaining.remove(zi)
        for piece in zone_path(zones[zi], last, sp):
            accrocher(ctx, paths, piece, max_link)
    ctx["log"].append("   zones : %d" % len(zones))
    return paths


def enchainer_chrono(ctx, polys, paths):
    """Toutes les courbes ont leurs extrémités sur le contour (chrono_chain).
    On range toutes les extrémités dans l'ordre où on les rencontre le long du contour.
    Entre deux extrémités voisines il y a un « intervalle » de contour ; chaque
    intervalle sert AU PLUS UNE FOIS de liaison (jamais de superposition).
    On obtient une seule ligne, avec un point d'entrée et un point de sortie, et
    naturellement une liaison sur deux le long du bord."""
    reg = ctx["reg"]
    log = ctx["log"]
    left = [list(p) for p in polys if len(p) > 1]
    if not left:
        return paths
    L = ctx["L"]
    near = 2 * max(reg["res"], reg["fuse"])

    curves, inner = [], []
    for p in left:
        (l0, d0), (l1, d1) = position_bord(ctx, p[0]), position_bord(ctx, p[-1])
        if d0 < near and d1 < near:
            curves.append((p, l0, l1))
        else:
            inner.append(p)

    if curves:
        # extrémités : (position sur le contour, n° de courbe, 0 = début / 1 = fin)
        ends = []
        for ci, (p, l0, l1) in enumerate(curves):
            ends.append((l0 % L, ci, 0))
            ends.append((l1 % L, ci, 1))
        ends.sort()
        n = len(ends)
        idx_of = {(e[1], e[2]): k for k, e in enumerate(ends)}

        # intervalles entre extrémités voisines (k -> k+1, en avançant)
        gaps = []
        for k in range(n):
            u, v = ends[k], ends[(k + 1) % n]
            gaps.append(((v[0] - u[0]) % L, k, (k + 1) % n))

        def build(order):
            """Choisit les liaisons dans l'ordre donné (sans boucle, 1 par extrémité).
            Renvoie (nb de morceaux, longueur totale, liaisons)."""
            parent = list(range(len(curves)))

            def find(x):
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x

            links = {}
            total = 0.0
            for long, k, k2 in order:
                if k in links or k2 in links:
                    continue
                c1, c2 = find(ends[k][1]), find(ends[k2][1])
                if c1 == c2:
                    continue
                parent[c1] = c2
                links[k] = (k2, False, long)
                links[k2] = (k, True, long)
                total += long
            n_pieces = len(curves) - len(links) // 2
            return (n_pieces, total, links)

        # ALTERNANCE STRICTE : en faisant le tour du contour, un intervalle sur deux
        # est une liaison, l'autre non. On essaie les deux décalages (0 ou 1) et on
        # garde celui qui forme le moins de boucles.
        def alternate(off):
            links = {}
            for long, k, k2 in gaps:
                if k % 2 == off:
                    links[k] = (k2, False, long)
                    links[k2] = (k, True, long)
            # boucles formées par courbes + liaisons
            seen, loops = set(), []
            for k0 in range(n):
                if k0 in seen:
                    continue
                loop, k = [], k0
                while k not in seen:
                    seen.add(k)
                    ci, side = ends[k][1], ends[k][2]
                    k_other = idx_of[(ci, 1 - side)]
                    seen.add(k_other)
                    loop.append(k_other)          # sortie de courbe = début de liaison
                    if k_other not in links:
                        break
                    k = links[k_other][0]
                loops.append(loop)
            return links, loops

        cands = [alternate(0), alternate(1)] if n % 2 == 0 else [alternate(0)]

        def n_clash(lk):
            return sum(1 for kk, v in lk.items()
                       if not v[1] and not arc_libre(ctx, ends[kk][0], v[2]))

        link_of, loops = min(cands, key=lambda c: (n_clash(c[0]), len(c[1]),
                             sum(v[2] for kk, v in c[0].items() if not v[1])))

        # --- fusion des boucles SANS superposition ---------------------------
        loop_id = {}
        for li, loop in enumerate(loops):
            for k in loop:
                ci, side = ends[k][1], ends[k][2]
                loop_id[k] = li
                loop_id[idx_of[(ci, 1 - side)]] = li

        def partner(k):
            return link_of[k][0] if k in link_of else None

        def add_gap(k):                        # liaison sur l'intervalle k -> k+1
            k2 = (k + 1) % n
            long = gaps[k][0]
            link_of[k] = (k2, False, long)
            link_of[k2] = (k, True, long)

        def remove_link(k):
            k2 = link_of[k][0]
            del link_of[k]
            del link_of[k2]

        def gap_between(k, k2):               # indice de l'intervalle entre deux voisines
            if (k + 1) % n == k2:
                return k
            if (k2 + 1) % n == k:
                return k2
            return None

        path_ends = []
        merged = set()
        if len(loops) == 1:
            # une seule boucle : on retire sa liaison la plus longue
            lk = [k for k in loops[0] if k in link_of]
            if lk:
                k_cut = max(lk, key=lambda k: link_of[k][2])
                path_ends = [k_cut, link_of[k_cut][0]]
                remove_link(k_cut)
            merged.add(0)
        elif len(loops) > 1:
            # 1er raccord : deux voisines b, c de boucles différentes (intervalle libre).
            # On retire la liaison de b et celle de c, on relie b-c : un seul chemin.
            best = None
            for k in range(n):
                b, c = k, (k + 1) % n
                if loop_id[b] != loop_id[c] and b in link_of and c in link_of \
                        and partner(b) != c:
                    ln = gaps[k][0]
                    if best is None or ln < best[0]:
                        best = (ln, b, c)
            if best is not None:
                _, b, c = best
                a, d = partner(b), partner(c)
                merged.update((loop_id[b], loop_id[c]))
                remove_link(b)
                remove_link(c)
                add_gap(gap_between(b, c))
                path_ends = [a, d]
                # ensuite : on accroche les autres boucles au bout du chemin
                progress = True
                while progress and len(merged) < len(loops):
                    progress = False
                    for ei, e in enumerate(path_ends):
                        for c in ((e + 1) % n, (e - 1) % n):
                            if loop_id[c] in merged or c not in link_of:
                                continue
                            g = gap_between(e, c)
                            if g is None:
                                continue
                            dd = partner(c)
                            merged.add(loop_id[c])
                            remove_link(c)
                            add_gap(g)
                            path_ends[ei] = dd
                            progress = True
                            break
                        if progress:
                            break
        # boucles restantes (pas accrochables sans superposition) : ouvertes
        for li, loop in enumerate(loops):
            if li in merged:
                continue
            lk = [k for k in loop if k in link_of]
            if lk:
                remove_link(max(lk, key=lambda k: link_of[k][2]))
        n_left = len(loops) - len(merged) + (1 if merged else 0)
        log.append("fusion des boucles : %d boucle(s) -> %d morceau(x)" % (len(loops), n_left))
        mode_used = "alternance stricte (%d boucle(s))" % len(loops)
        if n_left > 1:
            # l'alternance stricte laisse plusieurs morceaux : on cherche un autre
            # choix de liaisons (toujours sans superposition) qui relie tout
            rnd = random.Random(0)
            tries = [sorted(gaps)]
            for _ in range(300):
                tries.append(sorted(gaps, key=lambda g: g[0] * (0.5 + rnd.random())))
            best = min((build(o) for o in tries), key=lambda r: (r[0], r[1]))
            if best[0] < n_left:
                link_of = best[2]
                mode_used = "recherche (alternance stricte impossible en 1 morceau)"

        # --- amélioration : « chemins alternés » entre deux extrémités libres -----
        def gaps_used(lo):
            return [(k in lo and lo[k][0] == (k + 1) % n and not lo[k][1]) for k in range(n)]

        def count_pieces(gu):
            parent = list(range(len(curves)))

            def find(x):
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x
            m = 0
            for k in range(n):
                if gu[k]:
                    a, b = find(ends[k][1]), find(ends[(k + 1) % n][1])
                    if a == b:
                        return None            # boucle
                    parent[a] = b
                    m += 1
            return len(curves) - m

        gu = gaps_used(link_of)
        cur_pieces = count_pieces(gu)
        improved = cur_pieces is not None and cur_pieces > 1
        while improved:
            improved = False
            free = [k for k in range(n) if not gu[k] and not gu[(k - 1) % n]]
            for e in free:
                j, expect_link, seg = e, False, []
                for _ in range(n):
                    if gu[j] != expect_link:
                        break
                    seg.append(j)
                    j = (j + 1) % n
                    if not expect_link:
                        if not gu[j] and j != e:          # j libre : tronçon candidat
                            trial = list(gu)
                            for g_ in seg:
                                trial[g_] = not trial[g_]
                            pc = count_pieces(trial)
                            if pc is not None and pc < cur_pieces:
                                gu, cur_pieces, improved = trial, pc, True
                            break
                    expect_link = not expect_link
                if improved:
                    break
        if cur_pieces is not None:
            link_of = {}
            for k in range(n):
                if gu[k]:
                    k2 = (k + 1) % n
                    link_of[k] = (k2, False, gaps[k][0])
                    link_of[k2] = (k, True, gaps[k][0])
            log.append("apres amelioration : %d morceau(x)" % cur_pieces)

        for k, (k2, backward, long) in link_of.items():
            if not backward:
                ctx["used"].extend(morceaux_arc(ctx, ends[k][0], long))
        log.append("liaisons : " + mode_used)

        # parcours de chaque morceau depuis une extrémité libre (entrée)
        visited = set()
        pieces = []
        for k0 in range(n):
            if k0 in link_of or ends[k0][1] in visited:
                continue
            seq = []
            k = k0
            while True:
                l, ci, side = ends[k]
                visited.add(ci)
                p = curves[ci][0]
                seq.extend(p if side == 0 else list(reversed(p)))
                k_out = idx_of[(ci, 1 - side)]          # sortie de la courbe
                if k_out not in link_of:
                    break
                k_next, backward, long = link_of[k_out]
                seq.extend(points_arc(ctx, ends[k_out][0], long, backward))
                ctx["routed"] += 1
                k = k_next
            pieces.append((seq, k0, k_out))
        log.append("chrono : %d courbes, %d liaisons le long du bord, %d morceau(x) avant raccord"
                   % (len(curves), len(link_of) // 2, len(pieces)))

        # s'il reste plusieurs morceaux : on les raccorde (seul cas de repassage possible)
        if paths:
            cur = position_bord(ctx, paths[-1][-1])[0]   # on continue depuis la fin du chemin
        else:
            seq, _, k_end = pieces.pop(0)
            paths.append(seq)
            cur = ends[k_end][0]
        while pieces:
            best = None
            for j, (sq, ka, kb) in enumerate(pieces):
                for rev, kk in ((False, ka), (True, kb)):
                    lq = ends[kk][0]
                    fwd = (lq - cur) % L
                    for long, backward, arc in ((fwd, False, (cur, fwd)),
                                                (L - fwd, True, (lq, L - fwd))):
                        cle = (not arc_libre(ctx, *arc), long)
                        if best is None or cle < best[0]:
                            best = (cle, j, rev, long, backward, arc)
            cle, j, rev, long, backward, arc = best
            sq, ka, kb = pieces.pop(j)
            if rev:
                sq = list(reversed(sq))
                ka, kb = kb, ka
            route_pts = points_arc(ctx, cur, long, backward)
            if cle[0]:
                route_pts = lever_liaison(ctx, route_pts)
            ctx["routed"] += 1
            ctx["used"].extend(morceaux_arc(ctx, *arc))
            paths[-1].extend(route_pts)
            paths[-1].extend(sq)
            cur = ends[kb][0]

    for p in inner:
        if paths:
            end = paths[-1][-1]
            if math.dist(end, p[-1]) < math.dist(end, p[0]):
                p.reverse()
        accrocher(ctx, paths, p, float("inf"))
    if inner:
        log.append("chrono : %d courbe(s) interieure(s) ajoutee(s) a la fin" % len(inner))
    return paths


# --- contrôle du chemin -------------------------------------------------------------


def bilan_controle(ctx, P):
    """Segments superposés et segments hors de la forme (fin du script).
    Renvoie (nb superpositions, dont sur le bord, nb hors forme,
             segments superposés, segments hors forme)."""
    reg = ctx["reg"]
    tol, res = reg["tol"], reg["res"]
    segs = [(P[k], P[k + 1]) for k in range(len(P) - 1) if math.dist(P[k], P[k + 1]) > tol]
    cell = max(2 * res, 1.0)
    grid = {}
    for si, (a, b) in enumerate(segs):
        xs = sorted((a[0], b[0]))
        ys = sorted((a[1], b[1]))
        for gx in range(int(xs[0] // cell), int(xs[1] // cell) + 1):
            for gy in range(int(ys[0] // cell), int(ys[1] // cell) + 1):
                grid.setdefault((gx, gy), []).append(si)
    eps = max(10 * tol, 0.05)
    n_over = n_over_b = 0
    bad_over, bad_out = [], []
    seen_pairs = set()
    for ids in grid.values():
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)):
                i1, i2 = ids[x], ids[y]
                if abs(i1 - i2) <= 1 or (i1, i2) in seen_pairs:
                    continue
                seen_pairs.add((i1, i2))
                a, b = segs[i1]
                c, e = segs[i2]
                u = [b[m] - a[m] for m in range(3)]
                L1 = math.sqrt(sum(v * v for v in u))
                if L1 <= tol:
                    continue
                u = [v / L1 for v in u]

                def dist_line(p):
                    # distance de p à la droite (a, u)
                    w = [p[m] - a[m] for m in range(3)]
                    t = sum(w[m] * u[m] for m in range(3))
                    return math.sqrt(sum((w[m] - u[m] * t) ** 2 for m in range(3)))

                if dist_line(c) > eps or dist_line(e) > eps:
                    continue
                t1, t2 = sorted((sum((c[m] - a[m]) * u[m] for m in range(3)),
                                 sum((e[m] - a[m]) * u[m] for m in range(3))))
                if min(L1, t2) - max(0.0, t1) > eps:
                    n_over += 1
                    if ctx["bord"] is not None and \
                            position_bord(ctx, entre(a, b, 0.5))[1] < 10 * tol:
                        n_over_b += 1
                    bad_over.append([segs[i1][0], segs[i1][1]])
    n_out = 0
    if ctx["bord"] is not None:
        for a, b in segs:
            m = entre(a, b, 0.5)
            if not dedans(ctx, m) and not (position_bord(ctx, m)[1] < 2 * res):
                n_out += 1
                bad_out.append([a, b])
    return n_over, n_over_b, n_out, bad_over, bad_out


# --- tout le calcul -----------------------------------------------------------------


def calculer_chemin(series, contour=None, **reglages):
    """Des séries de courbes à plat au chemin d'impression continu, avec ses bosses.

    series  : liste de séries dans l'ordre d'impression ; une série = liste de polylignes
              (listes de points (x, y) en mm).
    contour : polyligne fermée (liste de points) ou Polygon shapely ; None = pas de contour.
    reglages: ceux de croisements.REGLAGES et de chemin.REGLAGES.

    Renvoie un dictionnaire avec les sorties du composant Grasshopper :
        path  : liste de points (x, y, z) ; None s'il n'y a rien à imprimer
        waves : une liste de polylignes 3D par série
        jumps : liaisons ajoutées entre morceaux (sauts)
        hits  : points des croisements au sol
        bad   : segments signalés par le CONTRÔLE (superposes + hors_forme)
        controle : {"superpositions", "sur_le_bord", "hors_forme", "sauts"}
        info  : texte de diagnostic (commence par la ligne CONTROLE)
    """
    reg = dict(croisements.REGLAGES)
    reg.update(REGLAGES)
    reg.update(reglages)
    reg = croisements.preparer(series, reg)
    reg["res"] = reg["res"] if reg["res"] > 0 else 2.0
    reg["route"] = str(reg["route"]).strip().lower() if reg["route"] else "series"
    reg["link"] = float(reg["link"] or 0.0)
    tol, amp, lane, hop = reg["tol"], reg["amp"], reg["lane"], reg["hop"]
    zigzag, route = reg["zigzag"], reg["route"]
    W, act = reg["weights"], reg["active"]

    ctx = {"reg": reg, "bord": None, "forme": None, "L": 0.0, "cache": {}, "used": [],
           "overlaps": 0, "routed": 0, "log": []}
    log = ctx["log"]

    # contour fermé
    anneau = None
    if contour is not None:
        coords = list(contour.exterior.coords) if hasattr(contour, "exterior") else list(contour)
        anneau = [en3d(p) for p in coords]
        if math.dist(anneau[0], anneau[-1]) > max(tol, 0.1):
            anneau = None
            bnd_msg = "boundary : recu mais PAS FERME -> ignore"
        else:
            anneau[-1] = anneau[0]
            changer_bord(ctx, anneau)
            bnd_msg = "boundary : OK (contour ferme)"
    else:
        bnd_msg = "boundary : non branche"

    # séries découpées par le contour
    S = [[p for c in serie for p in decouper(ctx, [en3d(q) for q in c])] for serie in series]

    log.extend(["amp = %s, d = %s, tol = %s, fuse = %s, mode = %s"
                % (amp, reg["d"], tol, reg["fuse"], reg["mode"]),
                bnd_msg,
                "series : %d  (courbes par serie : %s)" % (len(S), [len(b) for b in S]),
                "poids : %s" % W,
                "series qui ondulent : %s" % act, ""])

    chains = []      # chemin global, toutes séries, dans l'ordre A, B, C...
    seg_range = []   # mode série : (série, début, fin) de chaque série dans le chemin
    all_polys = []   # toutes les courbes de toutes les séries (route chrono)
    waves = [[] for _ in S]
    hits = []
    series_mode = zigzag and route == "series" and anneau is not None

    if not series_mode:
        # hors mode série : les vagues sont calculées courbe par courbe, avant le chemin
        v = croisements.vagues(S, **reg)
        waves, hits = v["waves"], v["hits"]
        log.extend(v["info"])

    for i in range(len(S)):
        src = S[i]
        if series_mode:
            if lane > 0:
                # couloirs : chaque série a ses liaisons sur son propre contour décalé
                Bi = decaler_vers_exterieur(anneau, lane * i)
                changer_bord(ctx, Bi)
                # les courbes sont prolongées jusqu'à la voie de leur série
                src = [p for c in S[i] for p in prolonger_jusqu_au_couloir(ctx, c, 8 * lane * i + 1.0)]
            # mode série : on construit d'abord le chemin À PLAT, les vagues viennent après
            start = len(chains[0]) if chains else 0
            before = ctx["overlaps"]
            enchainer_chrono(ctx, src, chains)
            seg_range.append((i, max(start - 1, 0), len(chains[0]) if chains else 0))
            log.append("serie %d : %d courbes -> chemin (%d repassage(s) sur le bord)"
                       % (i, len(src), ctx["overlaps"] - before))
            continue
        polys = waves[i]
        all_polys.extend([list(p) for p in polys])
        if zigzag and not (route in ("chrono", "series") and anneau is not None):
            if route == "contour":
                enchainer_contour(ctx, polys, chains)
            else:
                enchainer_zigzag(ctx, polys, chains)
            log.append("   -> path : %d morceau(x) au total apres cette serie" % len(chains))

    if seg_range and chains:
        # --- vagues sur le chemin de chaque série (courbes ET liaisons) ------------
        flat = chains[0]
        seg_pts = {}
        for i, a0, a1 in seg_range:
            seg_pts[i] = supprimer_courts(flat[a0:a1], tol) if a1 > a0 else []
        plates = [[seg_pts[i]] if len(seg_pts[i]) > 1 else [] for i in range(len(S))]
        v = croisements.empiler(plates, **reg)
        hits = v["hits"]
        log.extend("   " + t for t in v["info"])
        final = []
        for i, _, _ in seg_range:
            pts_i = v["waves"][i][0] if v["waves"][i] else seg_pts[i]
            waves[i] = [pts_i]
            if final and pts_i and math.dist(final[-1], pts_i[0]) < tol:
                pts_i = pts_i[1:]
            final.extend(pts_i)
        chains = [final]

    if series_mode and lane > 0:
        # pour le contrôle final : le contour le plus large (voie de la dernière série)
        changer_bord(ctx, decaler_vers_exterieur(anneau, lane * (len(S) - 1)))

    # courbes en double (même tracé) : on n'en garde qu'une
    uniq, n_dup = [], 0
    for p in all_polys:
        if len(p) < 2:
            continue
        dup = False
        for q in uniq:
            if len(q) == len(p) and (
                    all(math.dist(a, b) < 10 * tol for a, b in zip(p, q)) or
                    all(math.dist(a, b) < 10 * tol for a, b in zip(p, reversed(q)))):
                dup = True
                break
        if dup:
            n_dup += 1
        else:
            uniq.append(p)
    all_polys = uniq
    log.insert(0, "courbes en double supprimees : %d" % n_dup)

    if zigzag and route == "chrono" and anneau is not None:
        enchainer_chrono(ctx, all_polys, chains)

    # une SEULE polyligne : on relie les morceaux entre eux ; les liaisons ajoutées
    # sont sorties à part dans « jumps » (sauts)
    jumps = []
    one = []
    for c in chains:
        if len(c) < 2:
            continue
        if one:
            p, q = one[-1], c[0]
            if hop > 0:
                one.append(lever(p, hop))
                one.append(lever(q, hop))
                jumps.append([p, lever(p, hop), lever(q, hop), q])
            else:
                jumps.append([p, q])
        one.extend(c)

    path = supprimer_courts(one, tol) if len(one) > 1 else None
    log.append("path : 1 polyligne, %d liaison(s) le long du contour, "
               "%d repassage(s) inevitable(s), %d saut(s) en ligne droite (voir jumps)"
               % (ctx["routed"], ctx["overlaps"], len(jumps)))
    if jumps and anneau is None:
        log.append("   -> branche 'boundary' pour que les sauts longent le contour")

    n_over = n_over_b = n_out = 0
    bad_over, bad_out = [], []
    if path is not None:
        n_over, n_over_b, n_out, bad_over, bad_out = bilan_controle(ctx, path)
        log.insert(0, "CONTROLE : %d superposition(s) dont %d sur le bord (liaisons), "
                      "%d dans la forme (courbes) ; %d segment(s) hors forme"
                   % (n_over, n_over_b, n_over - n_over_b, n_out))

    return {
        "path": path,
        "waves": waves,
        "jumps": jumps,
        "hits": hits,
        "bad": bad_over + bad_out,
        "superposes": bad_over,
        "hors_forme": bad_out,
        "controle": {"superpositions": n_over, "sur_le_bord": n_over_b,
                     "hors_forme": n_out, "sauts": len(jumps)},
        "info": "\n".join(log),
    }
