"""Bilan des contrôles d'un motif, en texte, pour les pull requests.

Depuis la racine du dépôt :
    python -m trame.bilan exemple                  (contour : haricot.dxf)
    python -m trame.bilan groupe_1 rectangle.svg
"""

import json
import pathlib
import sys

from trame.app import calculer

SYMBOLES = {"ok": "OK", "alerte": "ATTENTION", "erreur": "ERREUR"}


def bilan(motif, contour="haricot.dxf"):
    chemin = pathlib.Path(__file__).resolve().parent.parent / "contours" / contour
    r = json.loads(calculer(motif, "{}", chemin.read_text(encoding="utf-8"), contour))
    if "erreur" in r:
        return "ERREUR : %s\n%s" % (r["erreur"], r.get("details", ""))
    lignes = ["Motif %s sur %s (réglages par défaut)" % (motif, contour),
              "Longueur de cordon : %.1f m, durée : environ %d min, béton : environ %s L"
              % (r["longueur"] / 1000, round(r["duree"] / 60), r["volume"]), ""]
    for c in r["controles"]:
        lignes.append("%-9s %s" % (SYMBOLES[c["statut"]], c["titre"]))
        if c["statut"] != "ok":
            lignes.append("          " + c["message"])
    return "\n".join(lignes)


if __name__ == "__main__":
    print(bilan(*sys.argv[1:]))
