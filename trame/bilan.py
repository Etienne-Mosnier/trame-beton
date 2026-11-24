"""Bilan des contrôles d'un dessin, en texte (pour une pull request ou un essai rapide).

Depuis la racine du dépôt :
    python -m trame.bilan dessins/vagues.svg
    python -m trame.bilan mon_dessin.dxf
Calques imprimés : ceux du départ, dans l'ordre alphabétique de leur nom.
"""

import json
import pathlib
import sys

from trame.app import calculer

SYMBOLES = {"ok": "OK", "alerte": "ATTENTION", "erreur": "ERREUR"}


def bilan(chemin):
    chemin = pathlib.Path(chemin)
    r = json.loads(calculer("{}", chemin.read_text(encoding="utf-8"), chemin.name))
    if "erreur" in r:
        return "ERREUR : %s\n%s" % (r["erreur"], r.get("details", ""))
    lignes = ["Dessin %s (réglages par défaut)" % chemin.name,
              r["message_dessin"],
              "Calques imprimés, dans l'ordre : %s" % ", ".join(r["calques"]),
              "Longueur de cordon : %.1f m, durée : environ %d min, béton : environ %s L"
              % (r["longueur"] / 1000, round(r["duree"] / 60), r["volume"]), ""]
    for c in r["controles"]:
        lignes.append("%-9s %s" % (SYMBOLES[c["statut"]], c["titre"]))
        if c["statut"] != "ok":
            lignes.append("          " + c["message"])
    return "\n".join(lignes)


if __name__ == "__main__":
    print(bilan(*sys.argv[1:]))
