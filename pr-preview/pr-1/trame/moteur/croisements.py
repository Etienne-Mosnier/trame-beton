"""Bosses aux croisements et empilement des séries.

Port fidèle de reference/vagues_ghx.py (composant Grasshopper « Vagues aux intersections »),
RhinoCommon remplacé par shapely et quelques calculs simples.

Correspondance avec le script d'origine :
    combine          -> coefficient
    events_on        -> evenements
    process_events   -> trier_evenements
    wave_points      -> points_vague
    ground           -> sommets_entre
    reseam           -> recoudre
    flat_points      -> en3d
    boucle i in act  -> vagues        (mode hors série : chaque courbe à part)
    « EMPILEMENT »   -> empiler       (mode série : A, puis B par-dessus, puis C…)

Écarts voulus :
- Toutes les courbes sont des polylignes (listes de points). Le script garde exactement
  les sommets d'une PolylineCurve ; on fait pareil pour toutes les courbes.
- Un événement garde la longueur du croisement (L) et celle du sommet de la bosse (Lpic),
  qui remplace le paramètre t de Rhino : les deux diffèrent seulement après une fusion.
- Les points sont des tuples (x, y) à plat ou (x, y, z) ; les unités sont des mm.
"""

import bisect
import math

import shapely
from shapely.geometry import LineString, Point

# Réglages par défaut : ceux de reference/betonrobot.ghx.
# amp vaudra la hauteur de couche de config/cellule.toml quand elle sera connue.
REGLAGES = {
    "amp": 5.0,        # hauteur de base d'une bosse (mm)
    "d": 10.0,         # demi-largeur de base d'une bosse, de part et d'autre du croisement (mm)
    "tol": 0.01,       # tolérance (mm)
    "fuse": 0.5,       # deux croisements plus proches que ça n'en font qu'un (mm)
    "mode": "own",     # "own" (empilement en mode série), "min", "max" ou "mul"
    "weights": [],     # un poids par série ; vide = 1 pour toutes
    "active": [],      # numéros des séries qui ondulent ; vide = toutes
}


def preparer(series, reglages):
    """Complète les réglages comme le fait le début du script (valeurs par défaut, bornes)."""
    reg = dict(REGLAGES)
    reg.update(reglages)
    n = len(series)
    if reg["tol"] <= 0:
        reg["tol"] = 0.01
    reg["fuse"] = max(reg["fuse"], reg["tol"])
    reg["mode"] = str(reg["mode"]).strip().lower() or "own"
    w = [float(x) for x in reg["weights"]]
    reg["weights"] = [w[i] if i < len(w) else (w[-1] if w else 1.0) for i in range(n)]
    act = [int(x) for x in reg["active"]]
    reg["active"] = [i for i in act if 0 <= i < n] if act else list(range(n))
    return reg


# --- petits outils sur les polylignes -----------------------------------------------


def en3d(p):
    """Point (x, y) ou (x, y, z) -> (x, y, z)."""
    return (p[0], p[1], p[2] if len(p) > 2 else 0.0)


def longueurs_cumulees(points):
    """Longueur depuis le début jusqu'à chaque sommet."""
    cumul = [0.0]
    for k in range(1, len(points)):
        cumul.append(cumul[-1] + math.dist(en3d(points[k - 1]), en3d(points[k])))
    return cumul


def point_a(points, cumul, L):
    """Point de la polyligne à la longueur L (PointAtLength)."""
    L = min(max(L, 0.0), cumul[-1])
    k = min(max(bisect.bisect_right(cumul, L) - 1, 0), len(points) - 2)
    longueur = cumul[k + 1] - cumul[k]
    u = (L - cumul[k]) / longueur if longueur > 0 else 0.0
    a, b = en3d(points[k]), en3d(points[k + 1])
    return tuple(a[m] + (b[m] - a[m]) * u for m in range(3))


def est_fermee(points, tol):
    return len(points) > 3 and math.dist(en3d(points[0]), en3d(points[-1])) < tol


def supprimer_courts(points, tol):
    """Retire les segments plus courts que tol (DeleteShortSegments)."""
    sortie = [points[0]]
    for p in points[1:]:
        if math.dist(p, sortie[-1]) >= tol:
            sortie.append(p)
    if len(points) > 1 and sortie[-1] is not points[-1]:
        # le dernier point tombait trop près : on garde le vrai bout
        if len(sortie) > 1:
            sortie[-1] = points[-1]
        else:
            sortie.append(points[-1])
    return sortie


def croisements(points, autres):
    """Longueurs, depuis le début de 'points', où la polyligne croise les polylignes 'autres'.

    Remplace Intersection.CurveCurve : seuls les croisements en un point comptent,
    une superposition (deux lignes confondues) est ignorée comme dans le script.
    """
    cumul = longueurs_cumulees(points)
    morceaux = [LineString([points[k][:2], points[k + 1][:2]]) for k in range(len(points) - 1)]
    cibles = [LineString([q[k][:2], q[k + 1][:2]]) for q in autres for k in range(len(q) - 1)]
    if not morceaux or not cibles:
        return []
    arbre = shapely.STRtree(cibles)
    paires = arbre.query(morceaux, predicate="intersects")
    longueurs = []
    for a, b in zip(paires[0], paires[1]):
        x = morceaux[a].intersection(cibles[b])
        if x.geom_type != "Point":
            continue
        # position du croisement le long du morceau a
        longueur_plan = morceaux[a].length
        u = morceaux[a].project(x) / longueur_plan if longueur_plan > 0 else 0.0
        longueurs.append(cumul[a] + u * (cumul[a + 1] - cumul[a]))
    return sorted(longueurs)


# --- calcul des vagues (port direct) ------------------------------------------------


def coefficient(i, j, reg):
    """Coefficient sur une courbe de la série i, là où elle croise la série j (combine)."""
    wi, wj = reg["weights"][i], reg["weights"][j]
    if reg["mode"] == "min":
        return min(wi, wj)
    if reg["mode"] == "max":
        return max(wi, wj)
    if reg["mode"] == "mul":
        return wi * wj
    # "own" : la série garde son propre poids quand elle croise une série qui ondule ;
    # aux croisements avec une série à plat -> 1
    return wi if j in reg["active"] else 1.0


def evenements(points, i, series, reg):
    """Croisements de la courbe (série i) avec toutes les autres séries (events_on)."""
    ev = []
    for j, courbes in enumerate(series):
        if j == i:
            continue
        f = coefficient(i, j, reg)
        plat = j not in reg["active"]      # croisement avec une série à plat (A)
        for L in croisements(points, courbes):
            ev.append((L, L, f, plat))
    return trier_evenements(ev, reg["d"], reg["fuse"])


def trier_evenements(ev, d, fuse):
    """Tri, fusion des doublons et suppression des bosses qui se chevauchent (process_events).

    ev : liste de (L, Lpic, coef, touche_A). Renvoie une liste de (L, Lpic, coef).
    """
    ev = sorted(ev, key=lambda e: e[0])

    # doublons au même endroit : coef le plus fort, et « touche A » si l'un touche A
    fusionnes = []
    for e in ev:
        if fusionnes and abs(e[0] - fusionnes[-1][0]) < fuse:
            m = fusionnes[-1]
            f = max(e[2], m[2])
            pic = e[1] if e[2] > m[2] else m[1]
            fusionnes[-1] = (m[0], pic, f, e[3] or m[3])
        else:
            fusionnes.append(e)

    # bosses qui se chevauchent (trop proches pour l'écart d) :
    #  - coefficients différents : on garde la plus haute
    #  - même coefficient : on supprime celle qui ne touche pas A
    gardes = []
    for e in fusionnes:
        while gardes:
            k = gardes[-1]
            trop_proches = e[0] - k[0] < d * (e[2] + k[2])
            if not trop_proches:
                break
            if e[2] != k[2]:
                if e[2] > k[2]:
                    gardes.pop()          # k plus basse : supprimée
                    continue
                e = None                  # e plus basse : supprimée
                break
            if k[3] and not e[3]:
                e = None                  # e ne touche pas A : supprimée
                break
            if e[3] and not k[3]:
                gardes.pop()              # k ne touche pas A : supprimée
                continue
            break
        if e is not None:
            gardes.append(e)
    return [(L, pic, f) for L, pic, f, _ in gardes]


def sommets_entre(points, cumul, l0, l1, sortie):
    """Ajoute les sommets de la polyligne situés strictement entre les longueurs l0 et l1 (ground)."""
    for k in range(len(points)):
        if l0 < cumul[k] < l1:
            sortie.append(en3d(points[k]))


def points_vague(points, ev, amp, d):
    """Polyligne 3D : la courbe à plat avec une bosse à chaque événement (wave_points)."""
    cumul = longueurs_cumulees(points)
    total = cumul[-1]
    sortie = [en3d(points[0])]
    fin_prec = 0.0
    n = len(ev)
    for k, (L, pic, f) in enumerate(ev):
        # limites : on partage l'écart avec chaque voisine au prorata des coefs,
        # pour que deux bosses ne se croisent jamais
        if k > 0:
            Lp, _, fp = ev[k - 1]
            bas = Lp + (L - Lp) * fp / (fp + f)
        else:
            bas = 0.0
        if k < n - 1:
            Ln, _, fn = ev[k + 1]
            haut = L + (Ln - L) * f / (f + fn)
        else:
            haut = total
        a = max(L - d * f, bas)
        b = min(L + d * f, haut)
        sommets_entre(points, cumul, fin_prec, a, sortie)   # suit la courbe entre deux bosses
        sortie.append(point_a(points, cumul, a))
        x, y, z = point_a(points, cumul, pic)
        sortie.append((x, y, z + amp * f))
        sortie.append(point_a(points, cumul, b))
        fin_prec = b
    sommets_entre(points, cumul, fin_prec, total, sortie)
    sortie.append(en3d(points[-1]))
    return sortie


def recoudre(points, i, series, reg):
    """Courbe fermée : déplace le départ au milieu du plus grand écart entre croisements,
    pour qu'aucune bosse ne soit coupée en deux (reseam)."""
    ev = evenements(points, i, series, reg)
    if not ev:
        return points
    cumul = longueurs_cumulees(points)
    total = cumul[-1]
    Ls = [e[0] for e in ev]
    ecarts = [(Ls[k + 1] - Ls[k], Ls[k]) for k in range(len(Ls) - 1)]
    ecarts.append((total - Ls[-1] + Ls[0], Ls[-1]))
    g, debut = max(ecarts)
    milieu = (debut + g / 2.0) % total
    couture = point_a(points, cumul, milieu)
    apres = [en3d(points[k]) for k in range(len(points) - 1) if cumul[k] > milieu]
    avant = [en3d(points[k]) for k in range(len(points) - 1) if cumul[k] < milieu]
    return [couture] + apres + avant + [couture]


# --- les deux façons de calculer les bosses ------------------------------------------


def vagues(series, **reglages):
    """Mode hors série : chaque courbe d'une série qui ondule monte à tous ses croisements
    avec les autres séries (avant ou après elle).

    series : liste de séries ; une série = liste de polylignes (listes de points).
    Renvoie {"waves": une liste de polylignes 3D par série, "hits": points au sol, "info": textes}.
    """
    reg = preparer(series, reglages)
    waves, hits, info = [], [], []
    for i, courbes in enumerate(series):
        sortie = []
        if i in reg["active"]:
            nb = []
            for points in courbes:
                if est_fermee(points, reg["tol"]):
                    points = recoudre(points, i, series, reg)
                ev = evenements(points, i, series, reg)
                nb.append(len(ev))
                cumul = longueurs_cumulees(points)
                hits.extend(point_a(points, cumul, pic)[:2] for _, pic, _ in ev)
                vague = points_vague(points, ev, reg["amp"], reg["d"])
                sortie.append(supprimer_courts(vague, reg["tol"]))
            info.append("serie %d : %d courbes, intersections par courbe %s"
                        % (i, len(courbes), nb))
        else:
            sortie = [[en3d(p) for p in points] for points in courbes]
            info.append("serie %d : %d courbes a plat" % (i, len(courbes)))
        waves.append(sortie)
    return {"waves": waves, "hits": hits, "info": info}


def hauteur_sous(vagues_j, x, y):
    """Hauteur (z) des vagues d'une série à l'endroit (x, y) : on prend le point de la
    vague le plus proche en plan, et sa hauteur (ClosestPoint sur la copie au sol)."""
    p = Point(x, y)
    meilleure = None
    for vague in vagues_j:
        plan = LineString([q[:2] for q in vague])
        distance = plan.distance(p)
        if meilleure is not None and distance >= meilleure[0]:
            continue
        # hauteur interpolée le long du segment, comme PointAt(tf) sur la vague 3D
        cumul_plan = [0.0]
        for k in range(1, len(vague)):
            cumul_plan.append(cumul_plan[-1] + math.dist(vague[k - 1][:2], vague[k][:2]))
        L = plan.project(p)
        k = min(max(bisect.bisect_right(cumul_plan, L) - 1, 0), len(vague) - 2)
        longueur = cumul_plan[k + 1] - cumul_plan[k]
        u = (L - cumul_plan[k]) / longueur if longueur > 0 else 0.0
        z = vague[k][2] + (vague[k + 1][2] - vague[k][2]) * u
        meilleure = (distance, z)
    return meilleure[1] if meilleure else 0.0


def empiler(series, **reglages):
    """Mode série : les séries s'impriment dans l'ordre A, B, C…
    Une série ne monte que là où elle passe sur une série déjà imprimée, et en mode
    "own" elle monte d'une couche au-dessus de ce qu'elle recouvre (EMPILEMENT) :
    B sur A -> 1 ; C sur B à plat -> 1 ; C sur une bosse de B -> 2…

    Mêmes entrées et sorties que vagues(). Dans le moteur complet (étape 5), chaque série
    est un seul chemin (ses courbes enchaînées) ; ici une série peut avoir plusieurs courbes.
    """
    reg = preparer(series, reglages)
    amp, d, fuse, tol = reg["amp"], reg["d"], reg["fuse"], reg["tol"]
    waves, hits, info = [], [], []
    for i, courbes in enumerate(series):
        if i not in reg["active"]:
            waves.append([[en3d(p) for p in points] for points in courbes])
            continue
        sortie, hauteurs, nb = [], set(), 0
        for points in courbes:
            cumul = longueurs_cumulees(points)
            total = cumul[-1]
            if reg["mode"] in ("own", "stack"):
                brut = []
                for j in range(i):
                    for L in croisements(points, series[j]):
                        if not (fuse < L < total - fuse):
                            continue          # pas de bosse sur les raccords
                        couches = 0
                        if j in reg["active"]:
                            # hauteur de la série j (déjà ondulée) à cet endroit
                            x, y, z0 = point_a(points, cumul, L)
                            z = hauteur_sous(waves[j], x, y) - z0
                            couches = int(math.ceil(z / amp - 1e-6)) if amp > 0 else 0
                        brut.append((L, L, float(max(couches, 0) + 1), j not in reg["active"]))
                ev = trier_evenements(brut, d, fuse)
            else:
                # seulement les séries déjà imprimées (j < i) coupent la série i
                avant = [series[j] if j < i else [] for j in range(len(series))]
                ev = [e for e in evenements(points, i, avant, reg)
                      if fuse < e[0] < total - fuse]
            hits.extend(point_a(points, cumul, pic)[:2] for _, pic, _ in ev)
            nb += len(ev)
            hauteurs.update(int(f) for _, _, f in ev)
            sortie.append(supprimer_courts(points_vague(points, ev, amp, d), tol))
        waves.append(sortie)
        info.append("serie %d : %d bosses, hauteurs %s" % (i, nb, sorted(hauteurs)))
    return {"waves": waves, "hits": hits, "info": info}
