# Trame béton

Application web de création de **trames imprimées en béton** par un bras UR10e,
sur une bâche posée sur une palette EPAL (1200 × 800 mm).

- Règles pour les agents et les étudiants : [AGENTS.md](AGENTS.md)
- Cahier des charges : [CAHIER_DES_CHARGES.md](CAHIER_DES_CHARGES.md)
- Chaque groupe travaille uniquement dans `motifs/<groupe>/`.
- **Aperçu en ligne : https://etienne-mosnier.github.io/trame-beton/**
- Guide pour les étudiants : [docs/ETUDIANTS.md](docs/ETUDIANTS.md)

## Lancer les tests (enseignant)

```sh
python3 -m venv .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/pytest
```

## Ouvrir l'aperçu sur son ordinateur (enseignant)

```sh
python3 web/construire.py          # liste les fichiers à charger (motifs, contours…)
python3 -m http.server 8000        # puis ouvrir http://localhost:8000/web/
```
