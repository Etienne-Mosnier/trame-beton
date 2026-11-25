# Règles pour les agents (Claude Code)

Ce fichier est lu par tous les agents qui travaillent sur ce dépôt. `CLAUDE.md` renvoie ici :
**les règles ne s'écrivent qu'ici.**

## Le projet

Application web (aperçu dans le navigateur, Python via Pyodide) qui prépare l'impression de
**trames en béton** par un bras UR10e, sur un support posé sur une palette EPAL (1200 × 800 mm).
Après l'impression, une action manuelle sur le support met la trame en mouvement ; chaque groupe
d'étudiants choisit son support et son action.

Les étudiants **dessinent leur trame dans leur logiciel** (Rhino, AutoCAD, Illustrator, Inkscape)
et l'**importent en DXF ou SVG** dans l'aperçu. Ils ne codent pas et ne passent pas par GitHub.
L'enseignant est designer, pas développeur : explications courtes, pas à pas, avec les gestes
des logiciels qu'il connaît.

## Comment l'application fonctionne

```
dessin DXF / SVG ──> CALQUES (trame/dessin.py) : un calque = une ligne d'un seul trait
   └─> ORDRE et PAUSES choisis dans l'aperçu (liste des calques, « relié » ou « pause »)
         └─> MOTEUR (trame/moteur/enchainement.py, deplacements.py) : un seul parcours de buse,
             bosses aux croisements, départ, pauses et fin à côté du dessin
               └─> CONTRÔLES (trame/controles.py) ──> APERÇU (web/)
               └─> EXPORTS : DXF/SVG (trame/export/), URScript robot (trame/robot/urscript.py),
                   G-code de la maquette WASP 2040 (trame/export/gcode.py)
```

## Règles physiques (à respecter dans tout changement)

- **Le dessin est imprimé tel qu'il est tracé** : pas de découpe, pas de contour, pas de spirale
  automatique. Chaque calque est une ligne d'un seul trait ; un calque en plusieurs morceaux est
  relié au plus court, avec un avertissement. 5 calques imprimés au plus.
- **Plusieurs fichiers** : un dessin peut arriver en plusieurs fichiers (souvent un calque par
  fichier). Chaque import s'ajoute au dessin en cours ; × retire un calque (et le fichier, quand il
  n'en a plus). Les fichiers sont superposés tels quels (même page dans le logiciel ; en SVG, y est
  compté depuis le bas de la page, comme en DXF) ; un fichier d'un seul calque prend le nom du fichier.
- **Ordre d'impression** = ordre de la liste dans l'aperçu (alphabétique au départ, glisser pour
  le changer). Départ et sens de chaque calque sont choisis par le moteur.
- **Taille et position sur la palette** : celles du dessin entier, calques éteints compris (sauf
  les calques techniques et ceux retirés avec ×) : éteindre un calque ne bouge pas les autres.
  Un dessin n'est tourné de 90° que s'il y gagne au moins 2 % de taille.
- **Bosses** : à chaque croisement, le passage le plus récent monte au-dessus des plus anciens,
  sur toute la largeur du cordon franchi, y compris quand une ligne se recroise elle-même. Pente :
  une hauteur de couche sur une largeur de cordon. Des cordons trop serrés pour que la buse
  redescende au sol (sur au moins une largeur de cordon) se franchissent d'un seul plateau.
- **Extrusion continue** (robot et WASP) : le programme ne coupe jamais la pompe. Le parcours
  commence et finit **à côté du dessin**, buse levée, avec un arrêt (« démarrer la pompe »,
  « couper la pompe »). Une **pause** sort la buse du dessin **sans jamais passer au-dessus du
  béton** (écart d'un cordon + 5 mm), attend « Continuer », puis revient. La buse sort d'une ligne
  et y entre par un petit prolongement imprimé (dessiné avec la ligne) ; le trajet buse levée ne
  compte pas comme béton posé (pas de bosse au-dessus).
- Le **robot** ne va que dans sa zone de portée (`zone_de_travail` dans `trame/app.py`).
- **Maquette WASP 2040** : delta, Marlin, plateau rond de 200 mm, extrusion par un boîtier
  externe (aucun axe E dans le G-code), arrêts `M0`. Voir `docs/MAQUETTE.md`.

Les valeurs du béton (cordon, couche, rayon de courbure) sont dans `config/cellule.toml` ; celles
qui valent 0 sont provisoires et signalées dans l'aperçu. Les contrôles signalent les problèmes :
**un avertissement n'est pas un bug à masquer**, il se discute dans le groupe.

## Ce que tu as le droit de modifier

| Dossier | Règle |
|---|---|
| `trame/`, `web/`, `tests/`, `dessins/`, `gabarits/`, `docs/` | à la demande de l'enseignant |
| `config/cellule.toml` | **seulement sur demande explicite** (réglages physiques du robot et du WASP) |
| `tests/` | ne jamais supprimer ni affaiblir un test pour le faire passer |
| `reference/` | ne pas modifier : programme Grasshopper et script d'origine, pour mémoire |

## Écrire du code ici

- Noms de variables, fonctions et commentaires **en français** ; fonctions courtes, boucles
  simples, pas de classes ni d'astuces. Unités : **millimètres** et **degrés**.
- Python : seulement `math`, `numpy`, `shapely`, `ezdxf`, `svgelements` et la bibliothèque
  standard (tout doit tourner dans Pyodide).
- Textes affichés aux étudiants (aperçu, messages, contrôles) : tournures impersonnelles
  (« Glisser le fichier… », « Choisir « relié »… »), jamais de tutoiement ; pas de distinction
  designers / ingénieurs.
- Robot : tout programme URScript se valide dans URSim avant le vrai robot (`docs/URSIM.md`).

## Vérifier avant de livrer

```sh
pytest                                         # tous les tests
python -m trame.bilan dessins/vagues.svg       # bilan des contrôles d'un dessin
python3 web/construire.py && node tests/pyodide/verifier.mjs   # tout marche dans Pyodide
python3 web/construire.py && python3 -m http.server 8000      # aperçu : http://localhost:8000/web/
```

Vérifier aussi le rendu de l'aperçu (capture d'écran) quand l'interface change.
