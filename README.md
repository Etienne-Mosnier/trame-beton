# Trame béton

Application web de création de **trames imprimées en béton** par un bras UR10e,
sur une bâche posée sur une palette EPAL (1200 × 800 mm).

- Règles pour les agents et les étudiants : [AGENTS.md](AGENTS.md)
- Cahier des charges : [CAHIER_DES_CHARGES.md](CAHIER_DES_CHARGES.md)
- Chaque groupe travaille uniquement dans `motifs/<groupe>/`.

## Lancer les tests (enseignant)

```sh
python3 -m venv .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/pytest
```
