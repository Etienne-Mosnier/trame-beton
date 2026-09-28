"""
Vagues aux intersections - UN SEUL composant pour toutes les séries
(Rhino 8 : composant "Script" en Python 3 / Rhino 7 : GhPython)

ENTREES (nom exact, type hint, accès) :
  series   Curve  Tree Access   toutes les séries, UNE BRANCHE PAR SÉRIE
                                (Entwine : A en 0, B en 1, C en 2... chaque entrée en Flatten)
  weights  float  List Access   un poids par série, dans le même ordre (ex. 1, 2, 2)
                                vide = 1 pour toutes
  active   int    List Access   séries qui ondulent, par numéro (ex. 1, 2 pour B et C)
                                vide = toutes
  mode     str    Item Access   règle du coefficient à un croisement :
                                "own" (défaut) : en mode série = EMPILEMENT, la série monte
                                d'une couche au-dessus de ce qu'elle recouvre à cet endroit
                                (weights n'est plus utilisé) ; sinon "min", "max" ou "mul"
  amp      float  Item Access   hauteur de base
  d        float  Item Access   écart de base de part et d'autre de l'intersection
  tol      float  Item Access   tolérance (ex. 0.01)
  fuse     float  Item Access   OPTIONNELLE : distance de fusion de deux intersections
                                trop proches, ex. une diagonale sur un croisement (défaut 0.5)
  res      float  Item Access   OPTIONNELLE : pas des points au sol sur les courbes
                                non droites, offsets, arcs... (défaut 2.0)
  link     float  Item Access   OPTIONNELLE : longueur max d'une liaison entre deux vagues
                                dans path ; au-delà, nouveau morceau (défaut : auto)
  lane     float  Item Access   OPTIONNELLE (mode series) : décalage vers l'EXTÉRIEUR du contour
                                des liaisons d'une série à la suivante (ex. largeur de cordon) ;
                                les courbes sont prolongées jusqu'à la voie de leur série.
                                Évite que les liaisons de séries différentes se superposent.
  boundary Curve  List Access   OPTIONNELLE : contour fermé de la surface ; toutes les
                                séries sont découpées et on garde ce qui est à l'intérieur
Courbes fermées : la couture est déplacée automatiquement hors des bosses.
  zigzag   bool   Item Access   True = une polyligne continue par série

SORTIES :
  waves    les vagues, une branche par série active
  path     UNE polyligne : chemin d'impression de TOUTES les séries (à plat + vagues),
           dans l'ordre A, B, C... (si zigzag = True)
  (entrée optionnelle route : "series" (défaut) = série par série, A puis B puis C... ;
   "chrono" = toutes séries mélangées, dans l'ordre
   des extrémités le long du contour ; "zigzag" = chaque extrémité reliée à la
   plus proche de la courbe voisine ; "contour" = liaisons le long de boundary)
  jumps    les liaisons ajoutées entre morceaux (sauts), pour les repérer en G-code
  (entrée optionnelle hop : float, hauteur de levée pendant les sauts, défaut 0)
  pts      les points des vagues
  hits     les points d'intersection au sol
  info     diagnostic (brancher un Panel)

COEFFICIENT D'UNE BOSSE
  Une courbe de la série i croise une courbe de la série j :
    "own" -> coef = poids i si j ondule aussi, sinon 1
             ex. A=1, B=1, C=2, active = 1, 2 :
             C x B -> C monte x2, B monte x1 ; C x A -> 1 ; B x A -> 1
    "min" -> coef = min(poids i, poids j)
    "max" -> coef = max(poids i, poids j)
    "mul" -> coef = poids i x poids j
  Hauteur = amp x coef, écart = d x coef.
  Exemple : A=1, B=2, C=2 en "min" -> B x C = 2, B x A = 1, C x A = 1.
  Si plusieurs séries croisent au même endroit, on garde le coef le plus fort.

AJOUTER UNE SÉRIE : une entrée de plus dans Entwine + un poids de plus dans weights
(+ son numéro dans active si elle doit onduler). Rien d'autre.
"""

import math
import Rhino.Geometry as rg
import Grasshopper as gh
from Grasshopper.Kernel.Data import GH_Path

try:
    import rhinoscriptsyntax as rs
except Exception:
    rs = None


# --- conversions robustes ----------------------------------------------------
def to_curve(obj):
    if obj is None:
        return None
    if isinstance(obj, rg.Curve):
        return obj
    if rs is not None:
        try:
            return rs.coercecurve(obj)
        except Exception:
            return None
    return None


def as_list(v):
    if v is None:
        return []
    if isinstance(v, str) or not hasattr(v, "__iter__"):
        return [v]
    return list(v)


def num_list(v):
    out = []
    for x in as_list(v):
        for part in str(x).replace(";", " ").split():
            try:
                out.append(float(part.replace(",", ".")))
            except ValueError:
                pass
    return out


def num(v, default):
    l = num_list(v)
    return l[0] if l else default


tol = num(tol, 0.01)
if tol <= 0:
    tol = 0.01
amp = num(amp, 10.0)
# distance sous laquelle deux intersections sont considérées comme un seul point
# (ex. une diagonale qui passe pile sur un croisement A x B). Entrée optionnelle.
try:
    fuse
except NameError:
    fuse = None
fuse = num(fuse, 0.5)
# façon de relier les courbes dans path : "zigzag" (défaut) ou "contour". Optionnelle.
try:
    route
except NameError:
    route = None
route = str(route).strip().lower() if route else "series"
# hauteur de levée des liaisons (0 = au sol). Entrée optionnelle.
try:
    hop
except NameError:
    hop = None
hop = num(hop, 0.0)
# longueur max d'une liaison entre deux vagues dans "path". Entrée optionnelle.
try:
    link
except NameError:
    link = None
# pas des points intermédiaires au sol sur les courbes non droites. Entrée optionnelle.
try:
    res
except NameError:
    res = None
res = num(res, 2.0)
if res <= 0:
    res = 2.0
if fuse < tol:
    fuse = tol
d = num(d, 5.0)
mode = str(mode).strip().lower() if mode else "own"

# séries : une branche = une série
if series is None:
    S = []
elif hasattr(series, "Branches"):
    S = [[c for c in (to_curve(x) for x in b) if c is not None] for b in series.Branches]
else:
    S = [[c for c in (to_curve(x) for x in as_list(series)) if c is not None]]

# --- découpe par le contour de la surface (entrée optionnelle "boundary") ----
try:
    boundary
except NameError:
    boundary = None
bnd = None
bnd_msg = "boundary : non branche"
_b = [c for c in (to_curve(x) for x in as_list(boundary)) if c is not None]
if _b:
    joined = rg.Curve.JoinCurves(_b, max(tol, 0.1))
    closed = [c for c in joined if c.IsClosed] if joined else []
    if closed:
        # le plus grand contour fermé
        bnd = max(closed, key=lambda c: c.GetLength())
        bnd_msg = "boundary : OK (%d courbe(s) recue(s), contour ferme)" % len(_b)
    else:
        bnd_msg = ("boundary : %d courbe(s) recue(s) mais PAS FERMEE -> ignoree"
                   % len(_b))
elif boundary is not None:
    bnd_msg = "boundary : recu mais pas une courbe (type hint ?) -> ignoree"

# version à plat (XY) du contour pour le test intérieur / extérieur
if bnd is not None:
    ok, _pl = bnd.TryGetPlane(tol)
    if ok:
        bnd_flat, plane = bnd, _pl
    else:
        plane = rg.Plane.WorldXY
        bnd_flat = rg.Curve.ProjectToPlane(bnd, plane)


def clip(crv):
    """Garde seulement les morceaux de crv à l'intérieur de bnd."""
    if bnd is None:
        return [crv]
    x = rg.Intersect.Intersection.CurveCurve(crv, bnd, tol, tol)
    ts = sorted(e.ParameterA for e in x if e.IsPoint) if x else []
    pieces = crv.Split(ts) if ts else None
    if not pieces:
        pieces = [crv]
    out = []
    for p in pieces:
        if p.GetLength() <= tol:
            continue
        mid = plane.ClosestPoint(p.PointAtNormalizedLength(0.5))
        if bnd_flat.Contains(mid, plane, tol) == rg.PointContainment.Inside:
            out.append(p)
    return out


S = [[p for c in b for p in clip(c)] for b in S]

W = num_list(weights)
W = [W[i] if i < len(W) else (W[-1] if W else 1.0) for i in range(len(S))]

act = [int(x) for x in num_list(active)]
act = [i for i in act if 0 <= i < len(S)] if act else list(range(len(S)))


def combine(i, j):
    """Coefficient sur une courbe de la série i, là où elle croise la série j."""
    wi, wj = W[i], W[j]
    if mode == "min":
        return min(wi, wj)
    if mode == "max":
        return max(wi, wj)
    if mode == "mul":
        return wi * wj
    # "own" (défaut) : la série garde son propre poids quand elle croise
    # une autre série qui ondule ; aux croisements avec une série à plat -> 1
    return wi if j in act else 1.0


# --- calcul des vagues -------------------------------------------------------
def events_on(crv, i, SS=None):
    ev = []
    for j, branch in enumerate(S if SS is None else SS):
        if j == i:
            continue
        f = combine(i, j)
        flat = j not in act          # croisement avec une série à plat (A)
        for c in branch:
            x = rg.Intersect.Intersection.CurveCurve(crv, c, tol, tol)
            if not x:
                continue
            for e in x:
                if not e.IsPoint:
                    continue
                t = e.ParameterA
                L = crv.GetLength(rg.Interval(crv.Domain.Min, t))
                ev.append((L, t, f, flat))
    return process_events(ev)


def process_events(ev):
    """Tri, fusion des doublons et suppression des bosses qui se chevauchent.
    ev : liste de (L, t, coef, touche_A)."""
    ev = sorted(ev, key=lambda e: e[0])

    # doublons au même endroit : coef le plus fort, et "touche A" si l'un touche A
    merged = []
    for e in ev:
        if merged and abs(e[0] - merged[-1][0]) < fuse:
            m = merged[-1]
            f = max(e[2], m[2])
            t = e[1] if e[2] > m[2] else m[1]
            merged[-1] = (m[0], t, f, e[3] or m[3])
        else:
            merged.append(e)

    # bosses qui se chevauchent (trop proches pour l'écart d) :
    #  - coefficients différents : on garde la plus haute (elle passe au-dessus,
    #    et sa rampe couvre déjà l'autre croisement) -> plus de petits pics serrés
    #  - même coefficient : on supprime celle qui ne touche pas A
    kept = []
    for e in merged:
        while kept:
            k = kept[-1]
            too_close = e[0] - k[0] < d * (e[2] + k[2])
            if not too_close:
                break
            if e[2] != k[2]:
                if e[2] > k[2]:
                    kept.pop()            # k plus basse : supprimée
                    continue
                e = None                  # e plus basse : supprimée
                break
            if k[3] and not e[3]:
                e = None                  # e ne touche pas A : on le supprime
                break
            if e[3] and not k[3]:
                kept.pop()                # k ne touche pas A : on le supprime
                continue
            break
        if e is not None:
            kept.append(e)
    return [(L, t, f) for L, t, f, _ in kept]


def wave_points(crv, ev):
    total = crv.GetLength()
    out = [crv.PointAtStart]
    prev_b = 0.0
    n = len(ev)
    for k, (L, t, f) in enumerate(ev):
        # limites : on partage l'écart avec chaque voisine au prorata des coefs,
        # pour que deux bosses ne se croisent jamais (plus de vrille)
        if k > 0:
            Lp, _, fp = ev[k - 1]
            lo = Lp + (L - Lp) * fp / (fp + f)
        else:
            lo = 0.0
        if k < n - 1:
            Ln, _, fn = ev[k + 1]
            hi = L + (Ln - L) * f / (f + fn)
        else:
            hi = total
        a = max(L - d * f, lo)
        b = min(L + d * f, hi)
        ground(crv, prev_b, a, out)          # suit la courbe entre deux bosses
        out.append(crv.PointAtLength(a))
        out.append(crv.PointAt(t) + rg.Vector3d(0, 0, amp * f))
        out.append(crv.PointAtLength(b))
        prev_b = b
    ground(crv, prev_b, total, out)
    out.append(crv.PointAtEnd)
    return out


_vcache = {}


def ground(crv, l0, l1, out):
    """Points intermédiaires au sol entre les longueurs l0 et l1 (exclues),
    seulement si la courbe n'est pas droite."""
    if isinstance(crv, rg.PolylineCurve):
        # polyligne (chemin d'une série) : on garde exactement ses sommets
        key = id(crv)
        if key not in _vcache:
            vl, acc = [], 0.0
            for k in range(crv.PointCount):
                if k > 0:
                    acc += crv.Point(k).DistanceTo(crv.Point(k - 1))
                vl.append((acc, crv.Point(k)))
            _vcache[key] = vl
        for l, p in _vcache[key]:
            if l0 < l < l1:
                out.append(p)
        return
    if crv.IsLinear(tol) or l1 - l0 <= res:
        return
    n = int((l1 - l0) / res)
    for s in range(1, n + 1):
        l = l0 + (l1 - l0) * s / float(n + 1)
        out.append(crv.PointAtLength(l))


def reseam(crv, i):
    """Courbe fermée : place la couture au milieu du plus grand écart
    entre intersections, pour qu'aucune bosse ne soit coupée en deux."""
    ev = events_on(crv, i)
    if not ev:
        return crv
    total = crv.GetLength()
    Ls = [e[0] for e in ev]
    gaps = [(Ls[k + 1] - Ls[k], Ls[k]) for k in range(len(Ls) - 1)]
    gaps.append((total - Ls[-1] + Ls[0], Ls[-1]))
    g, start = max(gaps)
    mid = (start + g / 2.0) % total
    ok, t = crv.LengthParameter(mid)
    c = crv.DuplicateCurve()
    if ok:
        c.ChangeClosedCurveSeam(t)
    return c


waves = gh.DataTree[object]()
path = gh.DataTree[object]()
pts = gh.DataTree[object]()
hits = []
log = ["amp = %s, d = %s, tol = %s, fuse = %s, mode = %s" % (amp, d, tol, fuse, mode),
       bnd_msg,
       "series : %d  (courbes par serie : %s)" % (len(S), [len(b) for b in S]),
       "poids : %s" % W,
       "series qui ondulent : %s" % act, ""]

def inside(p):
    if bnd is None:
        return True
    q = plane.ClosestPoint(p)
    return bnd_flat.Contains(q, plane, tol) != rg.PointContainment.Outside


def link_ok(p, q):
    """Le segment de liaison p -> q reste-t-il dans le contour ?"""
    if bnd is None:
        return True
    for s in (0.25, 0.5, 0.75):
        if not inside(p + (q - p) * s):
            return False
    return True


# --- liaisons le long du contour, sans jamais repasser au même endroit -------
used = []          # portions du contour déjà empruntées : intervalles [a, b] en longueur
overlaps = []      # liaisons qui n'ont pas pu éviter une portion déjà utilisée
_bcache = {}


def bpos(pt):
    """Position d'un point sur le contour : (longueur depuis le début, distance au contour)."""
    key = (round(pt.X, 6), round(pt.Y, 6), round(pt.Z, 6))
    if key not in _bcache:
        ok, t = bnd.ClosestPoint(pt)
        l = bnd.GetLength(rg.Interval(bnd.Domain.Min, t)) if ok else 0.0
        _bcache[key] = (l, pt.DistanceTo(bnd.PointAt(t)) if ok else 1e9)
    return _bcache[key]


def arc_parts(s, length):
    L = bnd.GetLength()
    s = s % L
    e = s + length
    return [(s, e)] if e <= L else [(s, L), (0.0, e - L)]


def arc_free(s, length):
    eps = max(10 * tol, 0.2)
    for a, b in arc_parts(s, length):
        for c, d in used:
            if min(b, d) - max(a, c) > eps:
                return False
    return True


def arc_points(s, length, backward):
    """Points le long du contour à partir de la longueur s, sur 'length'."""
    L = bnd.GetLength()
    step = max(res, 0.5)
    n = int(length / step)
    out = []
    for k in range(0, n + 2):
        u = length * k / float(n + 1)
        out.append(bnd.PointAtLength(((s - u) if backward else (s + u)) % L))
    return out


def plan_link(p, q, dist, max_link):
    """Meilleure liaison p -> q.
    Renvoie (coût, libre, points, arc) ; arc = (début, longueur) à marquer, ou None."""
    if dist <= max_link and link_ok(p, q):
        arc = None
        if bnd is not None:
            lp, dp = bpos(p)
            lq, dq = bpos(q)
            if dp < 2 * res and dq < 2 * res:      # extrémités sur le bord
                L = bnd.GetLength()
                fwd = (lq - lp) % L
                arc = (lp, fwd) if fwd <= L - fwd else (lq, L - fwd)
        free = arc is None or arc_free(*arc)
        return (dist, free, [], arc)
    if bnd is None:
        return (dist, False, None, None)      # pas de contour : saut
    L = bnd.GetLength()
    lp, dp = bpos(p)
    lq, dq = bpos(q)
    fwd = (lq - lp) % L
    back = L - fwd
    options = [(fwd + dp + dq, arc_free(lp, fwd), False, (lp, fwd)),
               (back + dp + dq, arc_free(lq, back), True, (lq, back))]
    # on préfère un sens libre ; à défaut le plus court
    options.sort(key=lambda o: (not o[1], o[0]))
    cost, free, backward, arc = options[0]
    spec = (lp, fwd if not backward else back, backward)   # points calculés plus tard
    return (cost, free, spec, arc)


def order_and_chain(polys, paths):
    """Enchaîne les courbes d'une série à la suite du chemin en cours.
    À chaque étape on choisit la courbe suivante dont la liaison est la plus
    courte SANS repasser sur une portion de contour déjà utilisée."""
    left = [list(p) for p in polys if len(p) > 1]
    if not left:
        return paths

    max_link = num(link, 0.0)
    if max_link <= 0:
        near = []
        for a_idx, a in enumerate(left):
            ds = [min(a[-1].DistanceTo(b[0]), a[-1].DistanceTo(b[-1]))
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
                cost, free, pts, arc = plan_link(end, q, end.DistanceTo(q), max_link)
                key = (not free, cost)
                if best is None or key < best[0]:
                    best = (key, idx, rev, pts, arc, free)
        _, idx, rev, pts, arc, free = best
        nxt = left.pop(idx)
        if rev:
            nxt.reverse()
        if pts is None:
            paths.append(nxt)                     # pas de contour : nouveau morceau
            continue
        if pts:
            pts = arc_points(*pts)
            if not free:
                overlaps.append(1)
                if hop > 0:                       # repasse : on lève la liaison
                    up = rg.Vector3d(0, 0, hop)
                    pts = [pts[0]] + [x + up for x in pts] + [pts[-1]]
            routed.append(1)
            paths[-1].extend(pts)
        if arc is not None:
            used.extend(arc_parts(*arc))
        paths[-1].extend(nxt)
    return paths


def attach(paths, pts, max_link):
    """Ajoute la courbe 'pts' (déjà orientée) au chemin, avec une liaison
    directe si elle est courte et reste dans la forme, sinon en longeant le contour."""
    if not paths:
        paths.append(list(pts))
        return
    end = paths[-1][-1]
    cost, free, spec, arc = plan_link(end, pts[0], end.DistanceTo(pts[0]), max_link)
    if spec is None:                       # pas de contour et saut long
        paths.append(list(pts))
        return
    if spec:
        route_pts = arc_points(*spec)
        if not free:
            overlaps.append(1)
            if hop > 0:
                up = rg.Vector3d(0, 0, hop)
                route_pts = [route_pts[0]] + [x + up for x in route_pts] + [route_pts[-1]]
        routed.append(1)
        paths[-1].extend(route_pts)
    if arc is not None:
        used.extend(arc_parts(*arc))
    paths[-1].extend(pts)


def zigzag_chain(polys, paths):
    """Zigzag par ZONES : la forme est découpée en zones où chaque ligne n'a
    qu'un seul morceau ; on fait un zigzag complet dans une zone, puis on passe
    à la zone suivante la plus proche (en longeant le contour si besoin)."""
    left = [list(p) for p in polys if len(p) > 1]
    if not left:
        return paths

    def ends_mid(p):
        a, b = p[0], p[-1]
        return rg.Point3d((a.X + b.X) / 2, (a.Y + b.Y) / 2, 0)

    if all(p[0].DistanceTo(p[-1]) < tol for p in left):
        # courbes fermées (offsets) : de la plus petite à la plus grande
        for p in sorted(left, key=lambda p: rg.Polyline(p).Length):
            if paths:
                end = paths[-1][-1]
                if end.DistanceTo(p[-1]) < end.DistanceTo(p[0]):
                    p.reverse()
            attach(paths, p, float("inf"))
        return paths

    # direction moyenne (en plan) et normale
    dsum = rg.Vector3d(0, 0, 0)
    for p in left:
        v = rg.Vector3d(p[-1].X - p[0].X, p[-1].Y - p[0].Y, 0)
        if not v.Unitize():
            continue
        if v * dsum < 0:
            v.Reverse()
        dsum += v
    if not dsum.Unitize():
        dsum = rg.Vector3d(1, 0, 0)
    nrm = rg.Vector3d.CrossProduct(rg.Vector3d.ZAxis, dsum)

    def across(p):
        return rg.Vector3d(ends_mid(p)) * nrm

    def span(p):
        u = rg.Vector3d(p[0].X, p[0].Y, 0) * dsum
        w = rg.Vector3d(p[-1].X, p[-1].Y, 0) * dsum
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
    max_link = num(link, 0.0)
    if max_link <= 0:
        max_link = 3.0 * spacing

    # 2. zones : un morceau passe dans la zone du morceau de la rangée précédente
    #    qu'il chevauche, seulement si ce lien est unique dans les deux sens
    zones = []
    prev = []                     # (zone, morceau) de la rangée précédente
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
            if ref.DistanceTo(p[-1]) < ref.DistanceTo(p[0]):
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
                        c, free, _, _ = plan_link(end, sp, end.DistanceTo(sp), max_link)
                        key = (not free, c)
                    else:
                        key = (False, 0.0)
                    if best is None or key < best[0]:
                        best = (key, zi, last, sp)
        _, zi, last, sp = best
        remaining.remove(zi)
        for piece in zone_path(zones[zi], last, sp):
            attach(paths, piece, max_link)
    log.append("   zones : %d" % len(zones))
    return paths


def chrono_chain(polys, paths):
    """Toutes les courbes (A, B, C... mélangées) ont leurs extrémités sur le contour.
    On range toutes les extrémités dans l'ordre où on les rencontre le long du contour.
    Entre deux extrémités voisines il y a un "intervalle" de contour ; chaque
    intervalle sert AU PLUS UNE FOIS de liaison (jamais de superposition).
    On choisit les liaisons en commençant par les plus courtes, sans jamais créer
    de boucle : on obtient une seule ligne, avec un point d'entrée et un point
    de sortie, et naturellement une liaison sur deux le long du bord."""
    left = [list(p) for p in polys if len(p) > 1]
    if not left:
        return paths
    L = bnd.GetLength()
    near = 2 * max(res, fuse)

    curves, inner = [], []
    for p in left:
        (l0, d0), (l1, d1) = bpos(p[0]), bpos(p[-1])
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
            length = (v[0] - u[0]) % L
            gaps.append((length, k, (k + 1) % n))

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
            for length, k, k2 in order:
                if k in links or k2 in links:
                    continue
                c1, c2 = find(ends[k][1]), find(ends[k2][1])
                if c1 == c2:
                    continue
                parent[c1] = c2
                links[k] = (k2, False, length)
                links[k2] = (k, True, length)
                total += length
            n_pieces = len(curves) - len(links) // 2
            return (n_pieces, total, links)

        # ALTERNANCE STRICTE : en faisant le tour du contour, un intervalle sur deux
        # est une liaison, l'autre non. On essaie les deux décalages (0 ou 1) et on
        # garde celui qui forme le moins de boucles. Chaque boucle est ensuite ouverte
        # en retirant sa liaison la plus longue -> un point d'entrée, un point de sortie.
        def alternate(off):
            links = {}
            for length, k, k2 in gaps:
                if k % 2 == off:
                    links[k] = (k2, False, length)
                    links[k2] = (k, True, length)
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
            return sum(1 for kk, v in lk.items() if not v[1] and not arc_free(ends[kk][0], v[2]))
        link_of, loops = min(cands, key=lambda c: (n_clash(c[0]), len(c[1]),
                             sum(v[2] for kk, v in c[0].items() if not v[1])))
        # --- fusion des boucles SANS superposition ---------------------------
        # chaque extrémité -> n° de boucle
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
            length = gaps[k][0]
            link_of[k] = (k2, False, length)
            link_of[k2] = (k, True, length)

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
        loops_pieces = n_left
        mode_used = "alternance stricte (%d boucle(s))" % len(loops)
        if loops_pieces > 1:
            # l'alternance stricte laisse plusieurs morceaux : on cherche un autre
            # choix de liaisons (toujours sans superposition) qui relie tout
            import random
            rnd = random.Random(0)
            tries = [sorted(gaps)]
            for _ in range(300):
                tries.append(sorted(gaps, key=lambda g: g[0] * (0.5 + rnd.random())))
            best = min((build(o) for o in tries), key=lambda r: (r[0], r[1]))
            if best[0] < loops_pieces:
                link_of = best[2]
                mode_used = "recherche (alternance stricte impossible en 1 morceau)"
        # --- amélioration : "chemins alternés" entre deux extrémités libres -----
        # Entre deux extrémités libres e et f, si les intervalles alternent
        # (libre, liaison, libre, ..., libre), on inverse tout le tronçon :
        # une liaison de plus, sans jamais superposer. On garde si ça réduit
        # le nombre de morceaux sans créer de boucle.
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

        for k, (k2, backward, length) in link_of.items():
            if not backward:
                used.extend(arc_parts(ends[k][0], length))
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
                k_next, backward, length = link_of[k_out]
                route_pts = arc_points(ends[k_out][0], length, backward)
                routed.append(1)
                seq.extend(route_pts)
                k = k_next
            pieces.append((seq, k0, k_out))
        log.append("chrono : %d courbes, %d liaisons le long du bord, %d morceau(x) avant raccord"
                   % (len(curves), len(link_of) // 2, len(pieces)))

        # s'il reste plusieurs morceaux : on les raccorde (seul cas de repassage possible)
        if paths:
            cur = bpos(paths[-1][-1])[0]      # on continue depuis la fin du chemin (série précédente)
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
                    for length, backward, arc in ((fwd, False, (cur, fwd)),
                                                  (L - fwd, True, (lq, L - fwd))):
                        key = (not arc_free(*arc), length)
                        if best is None or key < best[0]:
                            best = (key, j, rev, length, backward, arc)
            key, j, rev, length, backward, arc = best
            sq, ka, kb = pieces.pop(j)
            if rev:
                sq = list(reversed(sq))
                ka, kb = kb, ka
            route_pts = arc_points(cur, length, backward)
            if key[0]:
                overlaps.append(1)
                if hop > 0:
                    up = rg.Vector3d(0, 0, hop)
                    route_pts = [route_pts[0]] + [x + up for x in route_pts] + [route_pts[-1]]
            routed.append(1)
            used.extend(arc_parts(*arc))
            paths[-1].extend(route_pts)
            paths[-1].extend(sq)
            cur = ends[kb][0]

    for p in inner:
        if paths:
            end = paths[-1][-1]
            if end.DistanceTo(p[-1]) < end.DistanceTo(p[0]):
                p.reverse()
        attach(paths, p, float("inf"))
    if inner:
        log.append("chrono : %d courbe(s) interieure(s) ajoutee(s) a la fin" % len(inner))
    return paths


def flat_points(crv):
    """Courbe à plat (série qui n'ondule pas) -> liste de points."""
    if crv.IsLinear(tol):
        return [crv.PointAtStart, crv.PointAtEnd]
    out = [crv.PointAtStart]
    ground(crv, 0.0, crv.GetLength(), out)
    out.append(crv.PointAtEnd)
    return out


chains = []   # chemin global, toutes séries, dans l'ordre A, B, C...
seg_range = [] # mode série : (série, début, fin) de chaque série dans le chemin
routed = []   # liaisons qui longent le contour
all_polys = [] # toutes les courbes de toutes les séries
# --- couloirs : chaque série a ses liaisons sur son propre contour décalé ------
# (entrée optionnelle "lane" : décalage vers l'intérieur entre deux séries, ex. la
#  largeur d'un cordon ; 0 = toutes les séries sur le même contour)
try:
    lane
except NameError:
    lane = None
lane = num(lane, 0.0)
bnd_outer = bnd


def set_boundary(B):
    """Change le contour utilisé pour les liaisons (et remet à zéro sa mémoire)."""
    global bnd, bnd_flat, plane
    bnd = B
    ok, _p = B.TryGetPlane(tol)
    if ok:
        bnd_flat, plane = B, _p
    else:
        plane = rg.Plane.WorldXY
        bnd_flat = rg.Curve.ProjectToPlane(B, plane)
    _bcache.clear()
    del used[:]


def outset(B, dist):
    """Contour B décalé de 'dist' vers l'EXTÉRIEUR."""
    if dist <= 0:
        return B
    ok, pln = B.TryGetPlane(tol)
    if not ok:
        pln = rg.Plane.WorldXY
    best = None
    for sgn in (1, -1):
        try:
            res_o = B.Offset(pln, sgn * dist, tol, rg.CurveOffsetCornerStyle.Round)
        except Exception:
            res_o = None
        if not res_o:
            continue
        j = rg.Curve.JoinCurves(res_o, max(tol, 0.1))
        cl = [c for c in j if c.IsClosed] if j else []
        for c in cl:
            if c.GetLength() > B.GetLength() and (best is None or c.GetLength() < best.GetLength()):
                best = c
    return best


def extend_to_lane(c, dist):
    """Prolonge la courbe c en ligne droite à ses deux bouts, puis la recoupe
    sur le contour courant (le couloir de la série) : elle s'arrête sur sa voie."""
    if c.IsClosed or dist <= 0:
        return [c]
    ext = c.Extend(rg.CurveEnd.Both, dist, rg.CurveExtensionStyle.Line)
    if ext is None:
        return [c]
    mid = c.PointAtNormalizedLength(0.5)
    for p in clip(ext):
        ok, t = p.ClosestPoint(mid)
        if ok and p.PointAt(t).DistanceTo(mid) < 10 * tol:
            return [p]
    return [c]


for i in range(len(S)):
    polys = []
    src = S[i]
    if zigzag and route == "series" and bnd_outer is not None and lane > 0:
        Bi = outset(bnd_outer, lane * i)
        if Bi is None:
            log.append("   serie %d : contour decale impossible" % i)
            Bi = bnd_outer
        set_boundary(Bi)
        # les courbes sont prolongées jusqu'à la voie de leur série
        src = [p for c in S[i] for p in extend_to_lane(c, 8 * lane * i + 1.0)]
    series_mode = zigzag and route == "series" and bnd_outer is not None
    if series_mode:
        # mode série : on construit d'abord le chemin À PLAT, les vagues viennent après
        polys = [flat_points(c) for c in src]
        start = len(chains[0]) if chains else 0
        before = len(overlaps)
        chrono_chain(polys, chains)
        seg_range.append((i, max(start - 1, 0), len(chains[0])))
        log.append("serie %d : %d courbes -> chemin (%d repassage(s) sur le bord)"
                   % (i, len(src), len(overlaps) - before))
        continue
    if i in act:
        n_ev = []
        for k, crv in enumerate(src):
            if crv.IsClosed:
                crv = reseam(crv, i)
            ev = events_on(crv, i)
            n_ev.append(len(ev))
            hits.extend(crv.PointAt(t) for _, t, _ in ev)
            pl = rg.Polyline(wave_points(crv, ev))
            pl.DeleteShortSegments(tol)
            waves.Add(rg.PolylineCurve(pl), GH_Path(i))
            pts.AddRange(list(pl), GH_Path(i, k))
            polys.append(pl)
        log.append("serie %d : %d courbes, intersections par courbe %s"
                   % (i, len(src), n_ev))
    else:
        polys = [flat_points(c) for c in src]
        log.append("serie %d : %d courbes a plat (incluses dans path)"
                   % (i, len(S[i])))
    all_polys.extend([list(p) for p in polys])
    if zigzag and route == "series" and bnd is not None:
        # parcours SÉRIE PAR SÉRIE (A, puis B, puis C...) : zigzag de la série
        # le long du bord, puis passage à la série suivante en longeant le contour
        before = len(overlaps)
        chrono_chain(polys, chains)
        log.append("   -> serie %d ajoutee au chemin (%d repassage(s) sur le bord)"
                   % (i, len(overlaps) - before))
    elif zigzag and not (route in ("chrono", "series") and bnd is not None):
        if route == "contour":
            order_and_chain(polys, chains)
        else:
            zigzag_chain(polys, chains)
        log.append("   -> path : %d morceau(x) au total apres cette serie"
                   % len(chains))

if seg_range and chains:
    # --- vagues sur le chemin de chaque série (courbes ET liaisons) -------------
    flat = chains[0]
    seg_pts, seg_crv = {}, {}
    waved_crv, waved_flat = {}, {}
    for i, a0, a1 in seg_range:
        pl0 = rg.Polyline(flat[a0:a1])
        pl0.DeleteShortSegments(tol)
        seg_pts[i] = list(pl0)
        seg_crv[i] = rg.PolylineCurve(pl0) if pl0.Count > 1 else None
    final = []
    for i, a0, a1 in seg_range:
        pts_i = seg_pts[i]
        c = seg_crv[i]
        if i in act and c is not None:
            # une série ne monte QUE là où elle passe sur une série déjà imprimée
            # (A, puis B, puis C...) : C monte sur A et B, D sur A, B et C, etc.
            cutters = [[seg_crv[j]] if (j < i and seg_crv.get(j) is not None) else []
                       for j in range(len(S))]
            total_i = c.GetLength()
            if mode in ("own", "stack"):
                # EMPILEMENT : à chaque croisement, la série monte d'une couche
                # au-dessus de ce qu'elle recouvre à cet endroit.
                # (B sur A -> 1 ; C sur B à plat -> 1 ; C sur B déjà levé -> 2 ...)
                raw = []
                for j in range(i):
                    cj = seg_crv.get(j)
                    if cj is None:
                        continue
                    x = rg.Intersect.Intersection.CurveCurve(c, cj, tol, tol)
                    if not x:
                        continue
                    for e in x:
                        if not e.IsPoint:
                            continue
                        t = e.ParameterA
                        L = c.GetLength(rg.Interval(c.Domain.Min, t))
                        if not (fuse < L < total_i - fuse):
                            continue          # pas de bosse sur les raccords
                        layers = 0
                        wj = waved_crv.get(j)
                        if wj is not None:
                            # hauteur de la série j (déjà ondulée) à cet endroit
                            wj_flat = waved_flat.get(j)
                            if wj_flat is not None:
                                p_plan = c.PointAt(t)
                                okf, tf = wj_flat.ClosestPoint(p_plan)
                                if okf:
                                    z = wj.PointAt(tf).Z - p_plan.Z
                                    layers = int(math.ceil(z / amp - 1e-6)) if amp > 0 else 0
                        raw.append((L, t, float(max(layers, 0) + 1), j not in act))
                ev = process_events(raw)
            else:
                ev = [e for e in events_on(c, i, cutters)
                      if fuse < e[0] < total_i - fuse]   # pas de bosse sur les raccords
            hits.extend(c.PointAt(t) for _, t, _ in ev)
            pl = rg.Polyline(wave_points(c, ev))
            pl.DeleteShortSegments(tol)
            pts_i = list(pl)
            waved_crv[i] = rg.PolylineCurve(pl)
            # copie "au sol" de la vague (mêmes sommets, Z du chemin à plat) pour
            # retrouver, en plan, la hauteur de la vague à un endroit donné
            fp = []
            for p in pl:
                okc, tc = c.ClosestPoint(rg.Point3d(p.X, p.Y, p.Z))
                fp.append(rg.Point3d(p.X, p.Y, c.PointAt(tc).Z))
            waved_flat[i] = rg.PolylineCurve(fp)
            log.append("   serie %d : %d bosses (courbes + liaisons), hauteurs %s"
                       % (i, len(ev), sorted(set(int(e[2]) for e in ev))))
        waves.Add(rg.PolylineCurve(pts_i), GH_Path(i))
        pts.AddRange(pts_i, GH_Path(i))
        if final and pts_i and final[-1].DistanceTo(pts_i[0]) < tol:
            pts_i = pts_i[1:]
        final.extend(pts_i)
    chains = [final]

if bnd_outer is not None and bnd is not bnd_outer:
    # pour le contrôle final : le contour le plus large (voie de la dernière série)
    _Bmax = outset(bnd_outer, lane * (len(S) - 1)) if lane > 0 else None
    set_boundary(_Bmax if _Bmax is not None else bnd_outer)

# courbes en double (même tracé) : on n'en garde qu'une
_uniq, n_dup = [], 0
for p in all_polys:
    if len(p) < 2:
        continue
    dup = False
    for q in _uniq:
        if len(q) == len(p) and (
                all(a.DistanceTo(b) < 10 * tol for a, b in zip(p, q)) or
                all(a.DistanceTo(b) < 10 * tol for a, b in zip(p, reversed(q)))):
            dup = True
            break
    if dup:
        n_dup += 1
    else:
        _uniq.append(p)
all_polys = _uniq
log.insert(0, "courbes en double supprimees : %d" % n_dup)

if zigzag and route == "chrono" and bnd is not None:
    chrono_chain(all_polys, chains)

# une SEULE polyligne : on relie les morceaux entre eux.
# Les liaisons ajoutées sont sorties à part dans "jumps" (sauts, pour le G-code).
# Entrée optionnelle "hop" : hauteur de levée pendant un saut (0 = liaison au sol).

jumps = []
one = []
for c in chains:
    if len(c) < 2:
        continue
    if one:
        p, q = one[-1], c[0]
        if hop > 0:
            up = rg.Vector3d(0, 0, hop)
            one.append(p + up)
            one.append(q + up)
            jumps.append(rg.PolylineCurve([p, p + up, q + up, q]))
        else:
            jumps.append(rg.LineCurve(p, q))
    one.extend(c)

if len(one) > 1:
    pl = rg.Polyline(one)
    pl.DeleteShortSegments(tol)
    path = rg.PolylineCurve(pl)
else:
    path = None
log.append("path : 1 polyligne, %d liaison(s) le long du contour, "
           "%d repassage(s) inevitable(s), %d saut(s) en ligne droite (voir jumps)"
           % (len(routed), len(overlaps), len(jumps)))
if jumps and bnd is None:
    log.append("   -> branche 'boundary' pour que les sauts longent le contour")

# --- contrôle du chemin : segments superposés et segments hors de la forme ----
bad = []
if path is not None:
    P = [p for p in rg.Polyline(pl)] if len(one) > 1 else []
    segs = [(P[k], P[k + 1]) for k in range(len(P) - 1) if P[k].DistanceTo(P[k + 1]) > tol]
    cell = max(2 * res, 1.0)
    grid = {}
    for si, (a, b) in enumerate(segs):
        xs = sorted((a.X, b.X)); ys = sorted((a.Y, b.Y))
        for gx in range(int(xs[0] // cell), int(xs[1] // cell) + 1):
            for gy in range(int(ys[0] // cell), int(ys[1] // cell) + 1):
                grid.setdefault((gx, gy), []).append(si)
    eps = max(10 * tol, 0.05)
    n_over = 0
    n_over_b = 0
    seen_pairs = set()
    for ids in grid.values():
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)):
                i1, i2 = ids[x], ids[y]
                if abs(i1 - i2) <= 1 or (i1, i2) in seen_pairs:
                    continue
                seen_pairs.add((i1, i2))
                a, b = segs[i1]; c, e = segs[i2]
                u = b - a; L1 = u.Length
                if L1 <= tol: continue
                u.Unitize()
                # distance de c et e à la droite (a, u)
                def dist_line(p):
                    w = p - a
                    return (w - u * (w * u)).Length
                if dist_line(c) > eps or dist_line(e) > eps:
                    continue
                t1, t2 = sorted(((c - a) * u, (e - a) * u))
                if min(L1, t2) - max(0.0, t1) > eps:
                    n_over += 1
                    on_b = bnd is not None and bpos(rg.Point3d((a.X + b.X) / 2, (a.Y + b.Y) / 2,
                                                              (a.Z + b.Z) / 2))[1] < 10 * tol
                    if on_b:
                        n_over_b += 1
                    bad.append(rg.Polyline([segs[i1][0], segs[i1][1]]).ToNurbsCurve())
    n_out = 0
    if bnd is not None:
        for a, b in segs:
            m = rg.Point3d((a.X + b.X) / 2, (a.Y + b.Y) / 2, (a.Z + b.Z) / 2)
            if not inside(m) and not (bpos(m)[1] < 2 * res):
                n_out += 1
                bad.append(rg.Polyline([a, b]).ToNurbsCurve())
    log.insert(0, "CONTROLE : %d superposition(s) dont %d sur le bord (liaisons), "
                  "%d dans la forme (courbes) ; %d segment(s) hors forme"
                  % (n_over, n_over_b, n_over - n_over_b, n_out))

info = "\n".join(log)