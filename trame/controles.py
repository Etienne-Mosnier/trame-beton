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
        hors_forme(resultat),
        sur_la_palette(resultat, reglages["palette"], reglages["marge"]),
        lignes_trop_proches(lignes, 2 * reglages["largeur_cordon"]),
        croisements_rasants(lignes),
        virages_serres(toutes, rayon_min, "motif"),
        virages_serres([contour.exterior], rayon_min, "contour", anneau=True),
        passages_en_double(resultat, contour, reglages["lane"], len(series)),
    ]


def quantites(resultat, largeur_cordon, hauteur_couche, vitesse):
    """Longueur de cordon (mm), durée (s) et volume de béton (litres), estimés."""
    path = resultat["path"] or []
    longueur = sum(math.dist(a, b) for a, b in zip(path, path[1:]))
    return {
        "longueur": round(longueur),
        "duree": round(longueur / vitesse) if vitesse > 0 else None,
        "volume": round(longueur * largeur_cordon * hauteur_couche / 1e6, 1),
    }
