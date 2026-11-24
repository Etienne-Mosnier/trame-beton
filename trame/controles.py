"""Contrôles d'imprimabilité, affichés dans l'aperçu.

Chaque contrôle renvoie un dictionnaire :
    titre    : ce qui est vérifié, en une phrase courte
    statut   : "ok", "alerte" (à discuter avec les ingénieurs) ou "erreur" (impossible à imprimer)
    message  : explication en français
    points   : endroits à montrer en rouge [[x, y], …]
    segments : morceaux à montrer en rouge [[[x, y, z], [x, y, z]], …]

Un avertissement n'est pas un bug à masquer : il se discute avec les étudiants ingénieurs.
"""

import math

from shapely.geometry import LineString, Point

from trame.moteur.chemin import decaler_vers_exterieur

# Un croisement plus rasant que ça fait des bosses qui se chevauchent (degrés).
ANGLE_MIN = 20.0
# Un changement de direction plus fort que ça, d'un coup, est un angle vif (degrés).
ANGLE_VIF = 45.0
# Nombre maximal de points ou segments renvoyés par contrôle (pour garder l'aperçu fluide).
MAX_MARQUES = 300

LETTRES = "ABCDE"


def controle(titre, statut, message, points=(), segments=()):
    return {"titre": titre, "statut": statut, "message": message,
            "points": [list(p) for p in points][:MAX_MARQUES],
            "segments": [list(s) for s in segments][:MAX_MARQUES]}


def decouper(series, forme):
    """Les courbes de chaque série, découpées par la forme (ce qui sera vraiment imprimé)."""
    sortie = []
    for serie in series:
        morceaux = []
        for courbe in serie:
            partie = courbe.intersection(forme)
            for g in getattr(partie, "geoms", [partie]):
                if g.geom_type == "LineString" and g.length > 0:
                    morceaux.append(g)
        sortie.append(morceaux)
    return sortie


def direction(courbe, point):
    """Direction de la courbe au point donné (degrés, de 0 à 180)."""
    L = courbe.project(point)
    a = courbe.interpolate(max(L - 1.0, 0.0))
    b = courbe.interpolate(min(L + 1.0, courbe.length))
    return math.degrees(math.atan2(b.y - a.y, b.x - a.x)) % 180


# --- contrôles sur les lignes du motif ----------------------------------------------


def lignes_trop_proches(series, ecart_min):
    """Deux lignes d'une même série à moins de ecart_min (2 × la largeur du cordon)."""
    titre = "Lignes assez espacées"
    segments, plus_petit = [], None
    for serie in series:
        for a in range(len(serie)):
            for b in range(a + 1, len(serie)):
                d = serie[a].distance(serie[b])
                if d >= ecart_min:
                    continue
                plus_petit = d if plus_petit is None else min(plus_petit, d)
                # la partie de la ligne a trop près de la ligne b
                trop_pres = serie[a].intersection(serie[b].buffer(ecart_min))
                for g in getattr(trop_pres, "geoms", [trop_pres]):
                    if g.geom_type == "LineString":
                        segments.extend([[p[0], p[1], 0], [q[0], q[1], 0]]
                                        for p, q in zip(g.coords, list(g.coords)[1:]))
    if plus_petit is None:
        return controle(titre, "ok", "Les lignes d'une même série sont à plus de %g mm." % ecart_min)
    return controle(titre, "alerte",
                    "Des lignes d'une même série sont à moins de %g mm (2 × la largeur du cordon) : "
                    "les cordons vont se toucher. Écart le plus petit : %.0f mm." % (ecart_min, plus_petit),
                    segments=segments)


def lignes_qui_se_recoupent(series, forme=None):
    """Une courbe d'une série qui se croise elle-même (dans la forme) : le cordon repasse au
    même endroit. À appliquer aux courbes entières, avant découpage."""
    from collections import Counter

    from shapely.ops import unary_union

    titre = "Aucune ligne ne se recoupe"
    points = []
    for serie in series:
        for courbe in serie:
            if courbe.is_simple:
                continue
            # les nœuds où plus de deux morceaux se rejoignent sont les croisements
            decoupe = unary_union(courbe)
            bouts = Counter()
            for g in getattr(decoupe, "geoms", [decoupe]):
                bouts[g.coords[0]] += 1
                bouts[g.coords[-1]] += 1
            points += [p for p, n in bouts.items()
                       if n > 2 and (forme is None or forme.contains(Point(p)))]
    if not points:
        return controle(titre, "ok", "Aucune ligne ne se croise elle-même.")
    return controle(titre, "alerte",
                    "%d endroit(s) où une ligne se replie et se croise elle-même : le cordon passerait "
                    "deux fois au même endroit, à plat." % len(points), points=points)


def croisements_rasants(series, angle_min=ANGLE_MIN):
    """Croisements entre deux séries avec un angle plus petit que angle_min."""
    titre = "Croisements assez ouverts"
    points, plus_petit = [], None
    for i in range(len(series)):
        for j in range(i + 1, len(series)):
            for a in series[i]:
                for b in series[j]:
                    x = a.intersection(b)
                    for p in getattr(x, "geoms", [x]):
                        if p.geom_type != "Point":
                            continue
                        ecart = abs(direction(a, p) - direction(b, p))
                        angle = min(ecart, 180 - ecart)
                        if angle < angle_min:
                            points.append((p.x, p.y))
                            plus_petit = angle if plus_petit is None else min(plus_petit, angle)
    if plus_petit is None:
        return controle(titre, "ok", "Toutes les séries se croisent à plus de %g°." % angle_min)
    return controle(titre, "alerte",
                    "%d croisement(s) à moins de %g° : les bosses vont se chevaucher. "
                    "Angle le plus petit : %.0f°." % (len(points), angle_min, plus_petit),
                    points=points)


def virages_serres(courbes, rayon_min, nom, anneau=False):
    """Endroits où une courbe tourne plus serré que rayon_min, ou fait un angle vif."""
    points = []
    for courbe in courbes:
        c = [tuple(p[:2]) for p in courbe.coords]
        if anneau:
            c = c[:-1]
        n = len(c)
        indices = range(n) if anneau else range(1, n - 1)
        for k in indices:
            a, b, d = c[k - 1], c[k], c[(k + 1) % n]
            ab, bd, ad = math.dist(a, b), math.dist(b, d), math.dist(a, d)
            if ab == 0 or bd == 0:
                continue
            # changement de direction au sommet b
            t1 = math.atan2(b[1] - a[1], b[0] - a[0])
            t2 = math.atan2(d[1] - b[1], d[0] - b[0])
            tourne = abs(math.degrees((t2 - t1 + math.pi) % (2 * math.pi) - math.pi))
            if tourne > ANGLE_VIF:
                points.append(b)
                continue
            # rayon du cercle qui passe par a, b et d
            aire = abs((b[0] - a[0]) * (d[1] - a[1]) - (d[0] - a[0]) * (b[1] - a[1])) / 2
            if aire > 1e-9 and ab * bd * ad / (4 * aire) < rayon_min:
                points.append(b)
    titre = "Virages assez doux (%s)" % nom
    if not points:
        return controle(titre, "ok", "Pas de virage plus serré que %g mm de rayon." % rayon_min)
    return controle(titre, "alerte",
                    "%d endroit(s) du %s tournent plus serré que %g mm de rayon, ou font un angle vif : "
                    "la buse risque de déformer le cordon." % (len(points), nom, rayon_min),
                    points=points)


# --- contrôles sur le chemin --------------------------------------------------------


def une_seule_ligne(resultat):
    """Toutes les courbes sont reliées en zigzag (le long du bord) ou en spirale."""
    titre = "Une seule ligne : zigzag ou spirale"
    n = resultat.get("raccords_droits", 0)
    if not n:
        return controle(titre, "ok", "Les courbes s'enchaînent en zigzag le long du bord ou en spirale.")
    return controle(titre, "alerte",
                    "%d courbe(s) ne touchent pas le bord et ne forment pas une spirale : elles sont "
                    "raccordées en ligne droite à travers la forme. Fais traverser les courbes ouvertes "
                    "d'un bord à l'autre, ou emboîte les courbes fermées les unes dans les autres." % n)


def sauts(resultat):
    titre = "Chemin continu"
    jumps = resultat["jumps"]
    if not jumps:
        return controle(titre, "ok", "Le chemin est d'un seul tenant, sans saut.")
    segments = [[p, q] for j in jumps for p, q in zip(j, j[1:])]
    return controle(titre, "erreur",
                    "%d saut(s) : le chemin est coupé et la buse devrait traverser sans imprimer."
                    % len(jumps), segments=segments)


def hors_forme(resultat):
    titre = "Tout est dans la forme"
    segments = resultat["hors_forme"]
    if not segments:
        return controle(titre, "ok", "Aucun morceau du chemin ne sort de la forme.")
    return controle(titre, "erreur", "%d morceau(x) du chemin sortent de la forme." % len(segments),
                    segments=segments)


def passages_en_double(resultat, contour, lane, nb_series):
    """Segments imprimés deux fois. Sur un couloir (le long du bord) ou dans la forme."""
    titre = "Pas de passage en double"
    segments = resultat["superposes"]
    if not segments:
        return controle(titre, "ok", "Aucun endroit n'est imprimé deux fois.")
    # couloirs : le contour et ses décalages vers l'extérieur (un par série)
    anneau = list(contour.exterior.coords)
    couloirs = [LineString(decaler_vers_exterieur(anneau, lane * i)) if lane > 0 else contour.exterior
                for i in range(max(nb_series, 1))]
    sur_le_bord = 0
    for a, b in segments:
        milieu = Point((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        if min(c.distance(milieu) for c in couloirs) < 0.1:
            sur_le_bord += 1
    longueur = sum(math.dist(a, b) for a, b in segments)
    dans_la_forme = len(segments) - sur_le_bord
    message = "%.0f mm de cordon imprimés deux fois" % longueur
    if dans_la_forme == 0:
        message += ", tous le long du bord (liaisons entre deux lignes)."
    else:
        message += " : %d segment(s) le long du bord, %d dans la forme." % (sur_le_bord, dans_la_forme)
    return controle(titre, "alerte", message, segments=segments)


def sur_la_palette(resultat, palette, marge):
    titre = "Sur la palette"
    lx, ly = palette
    points = [p[:2] for p in resultat["path"] or []
              if not (marge <= p[0] <= lx - marge and marge <= p[1] <= ly - marge)]
    if not points:
        if marge > 0:
            return controle(titre, "ok", "Tout le chemin est sur la palette, à plus de %g mm du bord." % marge)
        return controle(titre, "ok", "Tout le chemin est sur la palette.")
    return controle(titre, "erreur",
                    "%d point(s) du chemin sont à moins de %g mm du bord de la palette, ou en dehors."
                    % (len(points), marge), points=points)


# --- tout ---------------------------------------------------------------------------


def controler(resultat, contour, series, reglages):
    """Tous les contrôles.

    resultat : sortie de calculer_chemin
    contour  : Polygon de la forme sur la palette
    series   : séries du motif (listes de LineString)
    reglages : largeur_cordon, rayon_courbure_min, lane, palette, marge
    """
    lignes = decouper(series, contour)
    toutes = [c for serie in lignes for c in serie]
    rayon_min = reglages["rayon_courbure_min"]
    return [
        sauts(resultat),
        une_seule_ligne(resultat),
        hors_forme(resultat),
        sur_la_palette(resultat, reglages["palette"], reglages["marge"]),
        lignes_trop_proches(lignes, 2 * reglages["largeur_cordon"]),
        lignes_qui_se_recoupent(series, contour),
        croisements_rasants(lignes),
        virages_serres(toutes, rayon_min, "motif"),
        virages_serres([contour.exterior], rayon_min, "contour", anneau=True),
        passages_en_double(resultat, contour, reglages["lane"], len(series)),
    ]


def liaisons_ajoutees(resultat, noms):
    """Liaisons droites ajoutées par le moteur : entre deux calques (choix « relié »), ou dans un
    calque tracé en plusieurs morceaux (la règle est un calque = une seule ligne)."""
    liaisons = resultat.get("liaisons", [])
    longueur = sum(math.dist(a, b) for l in liaisons for a, b in zip(l["points"], l["points"][1:]))
    cordon = "%d mm" % round(longueur) if longueur < 1000 else ("%.1f m" % (longueur / 1000)).replace(".", ",")
    titre = "Liaisons ajoutées : %d (%s de cordon)" % (len(liaisons), cordon)
    if not liaisons:
        return controle("Liaisons ajoutées : aucune", "ok", "Le dessin s'imprime d'un seul trait.")
    dans = [l for l in liaisons if l["dans_calque"]]
    if not dans:
        return controle(titre, "ok", "Une liaison droite entre deux calques qui se suivent.")
    calques = sorted({noms[l["calque"]] for l in dans})
    segments = [[p, q] for l in dans for p, q in zip(l["points"], l["points"][1:])]
    return controle(titre, "alerte",
                    "%d liaison(s) relient les morceaux d'un même calque (%s) : la règle est un calque = "
                    "une seule ligne. Elles sont imprimées en ligne droite, montrées en rouge."
                    % (len(dans), ", ".join("« %s »" % n for n in calques)), segments=segments)


def pauses_sans_survol(resultat, noms):
    """Pendant chaque pause, la buse sort du dessin et y revient sans passer au-dessus du béton."""
    pauses = resultat.get("pauses", [])
    titre = "Pauses : %d, sans passer au-dessus du béton" % len(pauses)
    bloquees = [(p, dep) for p, dep in zip(pauses, resultat["deplacements"]) if not p["libre"]]
    if not bloquees:
        return controle(titre, "ok", "La buse sort du dessin entre les lignes déjà imprimées, et y revient.")
    ou = ", ".join("après « %s » (couche %d)" % (noms[p["calque"]], p["couche"]) for p, _ in bloquees)
    segments = [[a, b] for _, dep in bloquees for a, b in zip(dep, dep[1:])]
    return controle(titre, "erreur",
                    "Pause %s : aucun passage entre les lignes déjà imprimées. La buse passerait au-dessus "
                    "du béton (trajet en rouge). Choisir « relié » à cet endroit, ou changer l'ordre des "
                    "calques." % ou, segments=segments)


def depart_et_fin(resultat):
    """Le béton coule déjà au départ, et encore à la fin : la buse attend à côté du dessin."""
    titre = "Départ et fin à côté du dessin"
    bloques = [nom for cle, nom in (("depart", "le départ"), ("fin", "la fin"))
               if resultat.get(cle) and not resultat[cle]["libre"]]
    if not bloques:
        return controle(titre, "ok", "La buse attend à côté du dessin que l'on démarre puis coupe la pompe.")
    segments = [[a, b] for cle in ("depart", "fin") if resultat.get(cle) and not resultat[cle]["libre"]
                for a, b in zip(resultat[cle]["trajet"], resultat[cle]["trajet"][1:])]
    return controle(titre, "erreur",
                    "Pour %s, aucun passage entre les lignes : la buse passerait au-dessus du béton (trajet "
                    "en rouge). Changer l'ordre des calques." % " et ".join(bloques), segments=segments)


def lignes_trop_proches_trace(calques, ecart_min, pas=2.0):
    """Dans un même calque, deux passages à moins de ecart_min (2 × la largeur du cordon) : deux
    lignes différentes, ou deux passages d'une même ligne (deux tours d'une spirale, les deux
    jambes d'une épingle). Le long d'une même ligne, on ne compare que des points éloignés de plus
    de 2 × ecart_min (sinon deux points voisins seraient toujours « trop proches »).
    Deux passages qui se croisent sont forcément proches près du croisement : on ne compte que
    les passages à peu près parallèles (moins de 30° d'écart, dans un sens ou dans l'autre)."""
    import numpy as np
    import shapely

    titre = "Lignes assez espacées"
    segments, plus_petit = [], None
    for calque in calques:
        P, S, C, D = [], [], [], []   # points tous les 'pas' mm, longueur sur leur ligne, ligne, direction
        for numero, courbe in enumerate(calque):
            s = np.linspace(0, courbe.length, max(1, math.ceil(courbe.length / pas)) + 1)
            point = lambda l: shapely.get_coordinates(shapely.line_interpolate_point(courbe, l))
            a, b = point(np.maximum(s - 1.0, 0.0)), point(np.minimum(s + 1.0, courbe.length))
            norme = np.maximum(np.hypot(*(b - a).T), 1e-9)[:, None]
            P.append(point(s))
            S.append(s)
            C.append(np.full(len(s), numero))
            D.append((b - a) / norme)
        if not P:
            continue
        P, S, C, D = np.concatenate(P), np.concatenate(S), np.concatenate(C), np.concatenate(D)
        if len(P) < 2:
            continue
        arbre = shapely.STRtree(shapely.points(P))
        i, j = arbre.query(shapely.points(P), predicate="dwithin", distance=ecart_min)
        paralleles = np.abs((D[i] * D[j]).sum(axis=1)) > math.cos(math.radians(30))
        garde = (i < j) & paralleles & ((C[i] != C[j]) | (np.abs(S[j] - S[i]) > 2 * ecart_min))
        i, j = i[garde], j[garde]
        if not len(i):
            continue
        distances = np.hypot(*(P[i] - P[j]).T)
        plus_petit = float(distances.min()) if plus_petit is None else min(plus_petit, float(distances.min()))
        # les endroits trop proches : un petit trait entre les deux passages
        for a, b in zip(i[:: max(1, len(i) // MAX_MARQUES)], j[:: max(1, len(i) // MAX_MARQUES)]):
            segments.append([[P[a][0], P[a][1], 0], [P[b][0], P[b][1], 0]])
    if plus_petit is None:
        return controle(titre, "ok", "Dans chaque calque, les passages sont à plus de %g mm." % ecart_min)
    return controle(titre, "alerte",
                    "Dans un même calque, des passages sont à moins de %g mm (2 × la largeur du cordon) : les "
                    "cordons vont se toucher. Écart le plus petit : %.0f mm." % (ecart_min, plus_petit),
                    segments=segments)


def croisements_rasants_trace(calques, angle_min=ANGLE_MIN):
    """Croisements plus rasants que angle_min : entre deux calques, et aussi quand une ligne se
    recroise elle-même (une boucle), puisque le second passage monte sur le premier."""
    import numpy as np
    import shapely

    titre = "Croisements assez ouverts"
    A, B, ligne, rang, fermee, longueur_ligne = [], [], [], [], [], []
    numero = 0
    for calque in calques:
        for courbe in calque:
            c = list(courbe.coords)
            for k in range(len(c) - 1):
                A.append(c[k][:2])
                B.append(c[k + 1][:2])
                ligne.append(numero)
                rang.append(k)
            fermee.append(len(c) > 3 and math.dist(c[0][:2], c[-1][:2]) < 0.5)
            longueur_ligne.append(len(c) - 1)
            numero += 1
    if not A:
        return controle(titre, "ok", "Aucun croisement.")
    A, B, ligne, rang = np.array(A), np.array(B), np.array(ligne), np.array(rang)
    morceaux = shapely.linestrings(np.stack([A, B], axis=1))
    i, j = shapely.STRtree(morceaux).query(morceaux, predicate="intersects")
    voisins = (ligne[i] == ligne[j]) & (np.abs(rang[i] - rang[j]) <= 1)
    # une courbe fermée : son dernier segment touche le premier
    bouclage = (ligne[i] == ligne[j]) & np.array([fermee[l] for l in ligne[i]]) & \
        (np.abs(rang[i] - rang[j]) == np.array([longueur_ligne[l] - 1 for l in ligne[i]]))
    garde = (i < j) & ~voisins & ~bouclage
    i, j = i[garde], j[garde]
    points, plus_petit = [], None
    for a, b, x in zip(i, j, shapely.intersection(morceaux[i], morceaux[j])):
        if x.geom_type != "Point":
            continue
        u, v = B[a] - A[a], B[b] - A[b]
        cos = abs(float(np.dot(u, v))) / (np.linalg.norm(u) * np.linalg.norm(v) or 1.0)
        angle = math.degrees(math.acos(min(cos, 1.0)))
        if angle < angle_min:
            points.append((x.x, x.y))
            plus_petit = angle if plus_petit is None else min(plus_petit, angle)
    if plus_petit is None:
        return controle(titre, "ok", "Toutes les lignes se croisent à plus de %g°." % angle_min)
    return controle(titre, "alerte",
                    "%d croisement(s) à moins de %g° : les bosses vont se chevaucher. "
                    "Angle le plus petit : %.0f°." % (len(points), angle_min, plus_petit),
                    points=points)


def controler_trace(resultat, calques, noms, reglages):
    """Contrôles d'un dessin importé (sans contour).

    resultat : sortie de enchainement.calculer_trace
    calques  : courbes placées de chaque calque imprimé (listes de LineString), dans l'ordre
    noms     : noms de ces calques
    reglages : largeur_cordon, rayon_courbure_min, palette
    """
    toutes = [c for calque in calques for c in calque]
    return [
        sur_la_palette(resultat, reglages["palette"], 0.0),
        liaisons_ajoutees(resultat, noms),
        *([pauses_sans_survol(resultat, noms)] if resultat.get("pauses") else []),
        depart_et_fin(resultat),
        lignes_trop_proches_trace(calques, 2 * reglages["largeur_cordon"]),
        croisements_rasants_trace(calques),
        virages_serres(toutes, reglages["rayon_courbure_min"], "dessin"),
    ]


def quantites(resultat, largeur_cordon, hauteur_couche, vitesse):
    """Longueur de cordon (mm), durée (s) et volume de béton (litres), estimés."""
    # extrusion continue : le béton coule tout le long du parcours, pauses comprises (hors attente)
    path = resultat["path"] or []
    longueur = sum(math.dist(a, b) for a, b in zip(path, path[1:]))
    return {
        "longueur": round(longueur),
        "duree": round(longueur / vitesse) if vitesse > 0 else None,
        "volume": round(longueur * largeur_cordon * hauteur_couche / 1e6, 1),
    }
