"""Écrit web/fichiers.json : la liste des fichiers du dépôt à copier dans Pyodide.
Avec --site DOSSIER, assemble aussi le site publié sur GitHub Pages dans DOSSIER.

À lancer depuis la racine du dépôt avant d'ouvrir l'aperçu :
    python3 web/construire.py
Pour la publication (GitHub Actions) :
    python3 web/construire.py --site _site
Les nouveaux motifs des groupes sont ainsi pris en compte sans modifier web/.
"""

import json
import os
import pathlib
import shutil
import sys
import time

RACINE = pathlib.Path(__file__).resolve().parent.parent
MOTIFS = ["trame/**/*.py", "motifs/*/motif.py", "motifs/*/aide.md",
          "motifs/*/*/motif.py", "motifs/*/*/aide.md",
          "contours/*.svg", "contours/*.dxf", "config/cellule.toml"]

# page d'accueil du site : renvoie vers l'aperçu
ACCUEIL = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="0; url=web/">
<title>Trame béton</title></head>
<body><a href="web/">Ouvrir l'aperçu</a></body></html>
"""


def lister():
    fichiers = set()
    for motif in MOTIFS:
        fichiers.update(p.relative_to(RACINE).as_posix() for p in RACINE.glob(motif))
    return sorted(f for f in fichiers if "__pycache__" not in f)


def assembler_site(dossier):
    """Copie la page web et tous les fichiers listés dans 'dossier' (effacé avant)."""
    site = pathlib.Path(dossier)
    if site.exists():
        shutil.rmtree(site)
    shutil.copytree(RACINE / "web", site / "web",
                    ignore=shutil.ignore_patterns("construire.py", "__pycache__"))
    for f in lister():
        cible = site / f
        cible.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RACINE / f, cible)
    # numéro de version dans les noms des fichiers de la page : après une mise à jour, le
    # navigateur recharge la nouvelle version au lieu de garder l'ancienne en cache
    version = os.environ.get("GITHUB_SHA", str(int(time.time())))[:12]
    remplacements = {
        "index.html": [('src="app.js"', 'src="app.js?v=%s"' % version),
                       ('href="style.css"', 'href="style.css?v=%s"' % version)],
        "app.js": [('"./pyodide_trame.mjs"', '"./pyodide_trame.mjs?v=%s"' % version),
                   ('"./robot.js"', '"./robot.js?v=%s"' % version)],
    }
    for nom, paires in remplacements.items():
        fichier = site / "web" / nom
        texte = fichier.read_text(encoding="utf-8")
        for avant, apres in paires:
            assert avant in texte, (nom, avant)
            texte = texte.replace(avant, apres)
        fichier.write_text(texte, encoding="utf-8")
    (site / "index.html").write_text(ACCUEIL, encoding="utf-8")
    (site / ".nojekyll").write_text("", encoding="utf-8")   # GitHub Pages : servir tel quel


if __name__ == "__main__":
    fichiers = lister()
    (RACINE / "web" / "fichiers.json").write_text(json.dumps(fichiers, indent=1), encoding="utf-8")
    print("web/fichiers.json : %d fichiers" % len(fichiers))
    if "--site" in sys.argv:
        dossier = sys.argv[sys.argv.index("--site") + 1]
        assembler_site(dossier)
        print("site assemblé dans %s" % dossier)
