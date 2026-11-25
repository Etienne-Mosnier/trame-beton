"""Ce qui sert aux deux exports (DXF et SVG) : noms des calques, liaisons, attentes, bosses."""

LETTRES = "ABCDE"


def lignes_et_liaisons(resultat):
    """(lignes, liaisons) : lignes[i] = polylignes 3D du calque i hors liaisons,
    liaisons = polylignes 3D ajoutées par le moteur pour relier les lignes."""
    return resultat["lignes"], [l["points"] for l in resultat["liaisons"]]


def noms_des_calques(nb, noms=None):
    """Nom de chaque calque exporté, dans l'ordre d'impression : « 1. A vagues », « 2. B lignes »…
    (le rang en tête : réimporté, le fichier garde le même ordre). Sans noms : SERIE_A, SERIE_B…
    Les caractères refusés dans un nom de calque DXF sont remplacés par « _ »."""
    if not noms:
        return ["SERIE_%s" % LETTRES[i] for i in range(nb)]
    propre = lambda nom: "".join("_" if c in '<>/\\":;?*|=`' else c for c in nom)
    return ["%d. %s" % (i + 1, propre(nom)) for i, nom in enumerate(noms[:nb])]


def attentes(resultat):
    """Parcours levé de la buse et point d'attente : départ, chaque pause, fin.
    Renvoie [(nom, trajet 3D, point d'attente), …]."""
    sortie = []
    if resultat.get("depart"):
        sortie.append(("DEPART", resultat["depart"]["trajet"], resultat["depart"]["point"]))
    for numero, (dep, pause) in enumerate(zip(resultat.get("deplacements", []), resultat.get("pauses", [])), 1):
        sortie.append(("PAUSE %d" % numero, dep, pause["point"]))
    if resultat.get("fin"):
        sortie.append(("FIN", resultat["fin"]["trajet"], resultat["fin"]["point"]))
    return sortie


def sommets_des_bosses(waves):
    """Sommets des bosses : (x, y, z) là où la hauteur monte puis ne monte plus (un sommet pointu,
    ou le début d'un sommet plat)."""
    sommets = []
    for serie in waves:
        for poly in serie:
            for k in range(1, len(poly) - 1):
                if poly[k][2] > 0 and poly[k][2] > poly[k - 1][2] and poly[k][2] >= poly[k + 1][2]:
                    sommets.append(tuple(poly[k]))
    return sommets


def reperes_palette(palette):
    """Repères de calibration (CDC §7) : origine, un point sur le grand côté, un sur le petit."""
    lx, ly = palette
    return [("P1 origine", (0.0, 0.0)), ("P2 grand cote", (lx, 0.0)), ("P3 petit cote", (0.0, ly))]
