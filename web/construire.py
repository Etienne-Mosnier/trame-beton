"""Écrit web/fichiers.json : la liste des fichiers du dépôt à copier dans Pyodide.

À lancer depuis la racine du dépôt avant d'ouvrir l'aperçu (et dans la publication) :
    python3 web/construire.py
Les nouveaux motifs des groupes sont ainsi pris en compte sans modifier web/.
"""

import json
import pathlib

RACINE = pathlib.Path(__file__).resolve().parent.parent
MOTIFS = ["trame/**/*.py", "motifs/*/motif.py", "motifs/*/aide.md",
          "contours/*.svg", "contours/*.dxf", "config/cellule.toml"]


def lister():
    fichiers = set()
    for motif in MOTIFS:
        fichiers.update(p.relative_to(RACINE).as_posix() for p in RACINE.glob(motif))
    return sorted(f for f in fichiers if "__pycache__" not in f)


if __name__ == "__main__":
    fichiers = lister()
    (RACINE / "web" / "fichiers.json").write_text(json.dumps(fichiers, indent=1), encoding="utf-8")
    print("web/fichiers.json : %d fichiers" % len(fichiers))
