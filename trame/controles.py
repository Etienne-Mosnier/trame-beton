"""Contrôles d'imprimabilité d'un dessin, affichés dans l'aperçu.

Chaque contrôle renvoie un dictionnaire :
    titre    : ce qui est vérifié, en une phrase courte
    statut   : "ok", "alerte" (à discuter dans le groupe) ou "erreur" (impossible à imprimer)
    message  : explication en français
    points   : endroits à montrer en rouge [[x, y], …]
    segments : morceaux à montrer en rouge [[[x, y, z], [x, y, z]], …]

Un avertissement n'est pas un bug à masquer : il se discute dans le groupe.
"""

import math

import numpy as np
import shapely

# Un croisement plus rasant que ça fait des bosses qui se chevauchent (degrés).
ANGLE_MIN = 20.0
# Un changement de direction plus fort que ça, d'un coup, est un angle vif (degrés).
ANGLE_VIF = 45.0
# Nombre maximal de points ou segments renvoyés par contrôle (pour garder l'aperçu fluide).
MAX_MARQUES = 300


def controle(titre, statut, message, points=(), segments=()):
    return {"titre": titre, "statut": statut, "message": message,
            "points": [list(p) for p in points][:MAX_MARQUES],
            "segments": [list(s) for s in segments][:MAX_MARQUES]}


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


def liaisons_ajoutees(resultat, noms):
    """Liaisons droites ajoutées par le moteur : entre deux calques (choix « relié »), ou dans un
    calque tracé en plusieurs morceaux (la règle est un calque = une seule ligne). Une liaison qui
    passe par-dessus des cordons déjà imprimés se voit sur la trame (un cordon de plus, des bosses)."""
    liaisons = resultat.get("liaisons", [])
    longueur = sum(math.dist(a, b) for l in liaisons for a, b in zip(l["points"], l["points"][1:]))
    cordon = "%d mm" % round(longueur) if longueur < 1000 else ("%.1f m" % (longueur / 1000)).replace(".", ",")
    titre = "Liaisons ajoutées : %d (%s de cordon)" % (len(liaisons), cordon)
    if not liaisons:
        return controle("Liaisons ajoutées : aucune", "ok", "Le dessin s'imprime d'un seul trait.")
    dans = [l for l in liaisons if l["dans_calque"]]
    dessus = [l for l in liaisons if l.get("survols")]
    if not dans and not dessus:
        return controle(titre, "ok", "Une liaison droite entre deux calques qui se suivent, sans passer "
                                     "par-dessus le béton.")
    messages = []
    if dans:
        calques = sorted({noms[l["calque"]] for l in dans})
        messages.append("%d liaison(s) relient les morceaux d'un même calque (%s) : la règle est un calque = "
                        "une seule ligne." % (len(dans), ", ".join("« %s »" % n for n in calques)))
    if dessus:
        messages.append("%d liaison(s) passent par-dessus des cordons déjà imprimés (%d fois) : un cordon droit "
                        "de plus, avec ses bosses, qui se verra sur la trame. Le moteur n'a pas trouvé mieux ; "
                        "pour l'éviter, changer l'ordre des calques, ou faire commencer ou finir les lignes "
                        "ailleurs dans le dessin." % (len(dessus), sum(l["survols"] for l in dessus)))
    montrees = [l for l in liaisons if l["dans_calque"] or l.get("survols")]
    segments = [[p, q] for l in montrees for p, q in zip(l["points"], l["points"][1:])]
    return controle(titre, "alerte", " ".join(messages) + " Liaisons en rouge.", segments=segments)


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
    """Le béton coule déjà au départ, et encore à la fin : la buse attend à côté du dessin, et ses
    trajets buse levée ne passent ni au-dessus du béton imprimé, ni si possible au-dessus des
    endroits où des cordons seront imprimés (le béton qui coule y tomberait)."""
    titre = "Départ et fin à côté du dessin"
    bloques = [cle for cle in ("depart", "fin") if resultat.get(cle) and not resultat[cle]["libre"]]
    noms = {"depart": "le départ", "fin": "la fin"}

    def segments_de(cles):
        return [[a, b] for cle in cles for a, b in zip(resultat[cle]["trajet"], resultat[cle]["trajet"][1:])]

    if bloques:
        return controle(titre, "erreur",
                        "Pour %s, aucun passage entre les lignes : la buse passerait au-dessus du béton (trajet "
                        "en rouge). Changer l'ordre des calques." % " et ".join(noms[c] for c in bloques),
                        segments=segments_de(bloques))
    depart = resultat.get("depart")
    if depart and not depart.get("evite_suite", True):
        return controle(titre, "alerte",
                        "Pour atteindre le début du premier calque, la buse passe au-dessus d'endroits où des "
                        "cordons seront imprimés (trajet en rouge) : le béton qui coule déjà y tombe sur la "
                        "palette. Pour l'éviter, commencer par un calque qui touche le bord du dessin (changer "
                        "l'ordre des calques).", segments=segments_de(["depart"]))
    return controle(titre, "ok", "La buse attend à côté du dessin que l'on démarre puis coupe la pompe.")


def lignes_trop_proches(calques, ecart_min, pas=2.0):
    """Dans un même calque, deux passages à moins de ecart_min (2 × la largeur du cordon) : deux
    lignes différentes, ou deux passages d'une même ligne (deux tours d'une spirale, les deux
    jambes d'une épingle). Le long d'une même ligne, on ne compare que des points éloignés de plus
    de 2 × ecart_min (sinon deux points voisins seraient toujours « trop proches »).
    Deux passages qui se croisent sont forcément proches près du croisement : on ne compte que
    les passages à peu près parallèles (moins de 30° d'écart, dans un sens ou dans l'autre)."""
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


def croisements_rasants(calques, angle_min=ANGLE_MIN):
    """Croisements plus rasants que angle_min : entre deux calques, et aussi quand une ligne se
    recroise elle-même (une boucle), puisque le second passage monte sur le premier."""
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


def controler(resultat, calques, noms, reglages):
    """Tous les contrôles d'un dessin.

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
        lignes_trop_proches(calques, 2 * reglages["largeur_cordon"]),
        croisements_rasants(calques),
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
