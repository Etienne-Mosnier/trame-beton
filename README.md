# Trame béton

Application web qui prépare l'impression de **trames en béton** par un bras UR10e, sur une
palette EPAL (1200 × 800 mm). Les étudiants importent leur dessin en calques (DXF ou SVG, depuis
Rhino, AutoCAD, Illustrator ou Inkscape), choisissent l'ordre d'impression et les pauses, vérifient
que la trame s'imprime, puis exportent le programme du robot ou une maquette pour le WASP 2040.

- **Aperçu en ligne : https://etienne-mosnier.github.io/trame-beton/**
- Gabarit de la palette, calques prêts : [gabarits/](gabarits/)
- Règles pour les agents : [AGENTS.md](AGENTS.md)
- Cahier des charges (première version, par motifs) : [CAHIER_DES_CHARGES.md](CAHIER_DES_CHARGES.md)
- Maquette sur le WASP 2040 : [docs/MAQUETTE.md](docs/MAQUETTE.md) ; robot dans URSim : [docs/URSIM.md](docs/URSIM.md)

## Lancer les tests (enseignant)

```sh
python3 -m venv .venv
.venv/bin/pip install -e ".[test,import]"
.venv/bin/pytest
```

## Ouvrir l'aperçu sur son ordinateur (enseignant)

```sh
python3 web/construire.py          # liste les fichiers à charger (dessins d'exemple, gabarits…)
python3 -m http.server 8000        # puis ouvrir http://localhost:8000/web/
```
