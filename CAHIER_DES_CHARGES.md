# Trame béton : cahier des charges de la base

À donner à Claude Code au démarrage du dépôt, avec `AGENTS.md` et le dossier `reference/`.

## 1. Contexte

- 16 étudiants designers en 4 groupes, chacun associé à des étudiants ingénieurs en génie civil.
  Un motif par groupe.
- Déroulé : 2 séances Grasshopper/application, 4 séances d'avancement, 2 séances d'impression
  béton, 1 séance de rendu.
- Résultat : des trames de cordons de béton imprimées sur une bâche posée sur une palette EPAL.
  La bâche est ensuite soulevée en certains points pour créer un volume. Le moment du levage
  (béton frais ou pris) fait partie de l'expérimentation.
- Les étudiants ne savent pas coder. Ils travaillent avec GitHub Copilot (plan Student) par issues
  assignées à l'agent. L'enseignant construit la base avec Claude Code.

## 2. Référence existante (`reference/`)

| Fichier | Contenu |
|---|---|
| `betonrobot.ghx` | Définition Grasshopper d'origine |
| `vagues_ghx.py` | Script Python « Vagues aux intersections » extrait du .ghx (1 335 lignes, RhinoCommon) |
| `betonrobot.script` | URScript généré par le plugin Robots (8 838 `movej`) |
| `chemin_script_xyz.csv` | Trajectoire de la buse recalculée depuis le .script par cinématique directe UR10e (mm, repère base robot) |

**Réglages de la définition :**
- **Séries** : 3 séries de lignes parallèles (Contour sur une surface plane), espacées de 50 mm,
  avec des directions à 45°, 119° et 250°, via Entwine.
  Vérifié sur `chemin_script_xyz.csv` : ces angles sont les **normales** des lignes (lignes à
  135°, 29° et 160°), les lignes passent à 50 mm × k de l'origine du repère robot, et l'ordre
  d'impression réel est **A = 250°, B = 119°, C = 45°** (A à plat, 127 bosses sur B,
  175 sur C dont 47 doubles).
- **Script** :
  - `weights = 1,1,2,3`, `active = 1,2,3` (B et C ondulent, A reste à plat) ;
  - `mode` = défaut `"own"`, qui équivaut à l'empilement en mode série ;
  - `amp = 5`, `d = 10`, `lane = 5`, `zigzag = True`, `route` = défaut `"series"`.
- **Contour** : courbe référencée dans Rhino, absente du .ghx. Le chemin recalculé montre une forme
  en haricot d'environ 735 × 885 mm.
- **Robot** :
  - UR10e, TCP `p[0.1744, 0, 0.02886, 1.2092, 1.2092, 1.2092]`, charge de 0,1 kg ;
  - mouvements Joint, 72 mm/s, zone 0 ;
  - plan d'impression à z ≈ 8,7 mm dans le repère base, une seule passe.

**Défauts du .script à ne pas reproduire :**
1. `movej` avec `r=0` sur chaque point : le robot **s'arrête à chaque point**, ce qui donne un cordon
   irrégulier.
2. Horizontal Frames redécoupe la courbe à pas constant (≈ 3,3 mm) : **les sommets des bosses sont
   rognés** (4,4 à 5 mm au lieu de 5).
3. Aucune commande d'extrusion, d'approche ni de dégagement.

## 3. Choix techniques

- **Python dans le navigateur avec Pyodide**, chargé depuis un CDN. Le même package `trame/` tourne
  dans le navigateur et dans `pytest` (GitHub Actions). Pas de serveur.
- **Géométrie avec `shapely`** (disponible dans Pyodide). Tout le moteur travaille **en 2D sur des
  polylignes** ; la hauteur (Z) n'est ajoutée qu'à la fin.
- **Aperçu avec three.js** : vue de dessus et vue 3D, les bosses exagérées en option, et les couleurs
  par série.
- **Hébergement sur GitHub Pages**, avec un aperçu publié pour chaque pull request si possible, sinon
  sur la branche principale.
- **Imports** : `ezdxf` pour le DXF et `svgelements` pour le SVG, installés par micropip (**à vérifier
  dans Pyodide dès la première étape**).

## 4. Architecture

```
trame-beton/
  AGENTS.md                      règles pour tous les agents
  CLAUDE.md                      contient seulement : @AGENTS.md
  .github/
    copilot-instructions.md      renvoie à AGENTS.md
    CODEOWNERS                   enseignant obligatoire sur trame/, web/, config/, tests/
    ISSUE_TEMPLATE/idee-motif.md gabarit d'issue en français pour les étudiants
    workflows/tests.yml          pytest à chaque pull request
    workflows/pages.yml          publication de l'aperçu
  config/cellule.toml            TCP, vitesse, cordon, extrusion, calibration palette
  trame/
    parametres.py                classe Parametre (valeur, mini, maxi, unité, aide)
    outils.py                    fonctions simples pour les motifs (lignes parallèles, arcs, ondes…)
    contour.py                   import SVG/DXF, fermeture, mise à l'échelle dans la palette
    moteur/
      croisements.py             bosses et empilement (port de vagues_ghx.py)
      chemin.py                  enchaînement en un chemin continu le long du contour
    controles.py                 contrôles d'imprimabilité
    export/dxf.py, export/svg.py
    robot/
      urscript.py                génération du programme
      calibration.py             repère palette → repère robot
      atteignabilite.py          vérification de la portée de l'UR10e
      cinematique.py             directe + inverse analytique UR10e, choix de configuration
      alertes.py                 limites, singularités, collisions simplifiées
  web/robot/ur10e/               maillages officiels UR10e (licence BSD-3)
    app.py                       point d'entrée appelé par le web : motif + réglages → résultat JSON
  motifs/
    exemple/motif.py             les 3 séries de lignes du .ghx : modèle à copier
    groupe_1/ … groupe_4/        un dossier par groupe
  web/                           index.html, app.js (three.js, curseurs générés depuis PARAMETRES)
  tests/
  reference/
```

## 5. Le moteur (port de `vagues_ghx.py`)

On porte l'algorithme **fidèlement, pas simplifié**, en remplaçant RhinoCommon par shapely :

| RhinoCommon | Remplacement |
|---|---|
| `Intersection.CurveCurve` | `LineString.intersection` → points |
| `GetLength`, `PointAtLength` | `project` / `interpolate` |
| `Curve.Split` + test du milieu | découpe par le polygone du contour (`intersection`) |
| `Offset` (coins ronds) | `buffer(dist, join_style="round").exterior` |
| `Contains` | `Polygon.contains` / `covers` |
| `ChangeClosedCurveSeam` | rotation de la liste de points |

Toutes les options et tous les modes sont conservés : `weights`, `active`, `mode`, `amp`, `d`, `fuse`,
`res`, `link`, `lane`, `route`, `hop`. Les sorties `waves`, `path`, `jumps`, `hits` et le texte `info`
(avec son bilan CONTRÔLE) sont conservées aussi.

**Couches.** Elles suivent le même système que le .ghx. Chaque série est un niveau d'impression, et à
chaque croisement la série monte au-dessus de ce qu'elle recouvre : la hauteur de bosse vaut `amp` ×
le nombre de cordons empilés à cet endroit. 2 à 5 séries donnent 2 à 5 niveaux. `amp` vaut par défaut
la hauteur de couche du cordon (`config/cellule.toml`).

**Test de fidélité.** L'enseignant exporte depuis Grasshopper, en JSON ou CSV, le contour, les séries
et la sortie `path` pour 2 ou 3 réglages. Le port doit redonner le même chemin, à la tolérance près.
En attendant, `chemin_script_xyz.csv` sert de contrôle visuel.

## 6. Contrôles d'imprimabilité (`controles.py`)

Chaque contrôle renvoie une liste de points ou de segments fautifs et un message en français, qui
s'affichent dans l'aperçu :
- superpositions de segments et segments hors du contour (repris du bilan CONTRÔLE du script) ;
- lignes d'une même série trop proches (moins de 2 × la largeur du cordon) ;
- croisements trop rasants (angle inférieur à 20°) ;
- rayon de courbure trop petit ;
- nombre de sauts (le chemin doit être continu) ;
- sortie de la palette (marge) et points hors de portée du robot ;
- longueur totale, durée estimée et volume de béton estimé.

## 7. Positionnement de la palette (calibration)

Dans le .ghx, le dessin Rhino était placé directement dans le repère du robot : c'est pour ça que les
coordonnées vont de x = −965 à −230 mm. Dans l'application, les étudiants dessinent **sur la palette**,
avec le point (0, 0) sur un coin. Il faut donc indiquer une fois au robot où se trouve ce coin :
1. On amène la buse sur trois points de la palette : le coin origine, un point sur le grand côté et
   un point sur le petit côté.
2. On relève les trois positions sur le pendant.
3. On les saisit dans `config/cellule.toml`.

`calibration.py` en déduit le repère de la palette, ce qui corrige aussi un léger défaut de niveau.
On refait la calibration seulement si la palette ou le robot bouge.

## 8. Simulation robot (visible par les étudiants et l'enseignant)

Le bras est affiché dans l'aperçu : les étudiants voient la machine imprimer leur motif.

- **Modèles 3D** : maillages officiels de l'UR10e (dépôt `Universal_Robots_ROS2_Description`, licence
  BSD-3), avec ses paramètres de cinématique et ses limites articulaires. **Buse** : forme simplifiée
  (cylindre aux dimensions réelles, décalage du TCP repris du .ghx).
- **Cinématique** :
  - la directe est déjà validée sur `betonrobot.script` ;
  - l'inverse est analytique, avec 8 solutions et un choix de configuration continu d'un point à l'autre ;
  - test : recalculer les angles des 8 838 poses du .script et retrouver les mêmes.
- **Animation** : le bras suit le chemin avec un curseur de temps, et le cordon se dépose au fur et à
  mesure.
- **Alertes en rouge** :
  - point hors de portée ;
  - limite articulaire ;
  - singularités (poignet aligné, coude tendu, épaule) ;
  - collision simplifiée du bras et de la buse avec la palette et le socle (capsules).
- **Placement de la palette** : la palette n'est pas encore installée. Un mode enseignant permet de la
  déplacer dans la scène et affiche la zone atteignable, pour choisir un emplacement où toute la palette
  est imprimable. La hauteur relative robot / palette fait partie de ce réglage.
- **Limite** : l'aperçu montre où passe le bras, pas les accélérations réelles du contrôleur. La
  référence reste URSim (même logiciel que le robot).

## 9. Export URScript (`urscript.py`)

Robot sous **PolyScope 5** : on vérifie chaque fonction dans le manuel URScript 5.x.

- **Mouvements en poses cartésiennes** (`movel`/`movep` sur des poses) : le contrôleur calcule lui-même
  les angles avec sa propre calibration. Le calcul de l'application sert seulement à l'aperçu et aux
  alertes.
- En-tête : `set_tcp`, `set_payload` (**masse réelle de la buse à mesurer** : le .script déclare
  0,1 kg) et la pose de la palette.
- Mouvements **linéaires raccordés** : `movep` ou `movel` avec un rayon `r` réglable (1 à 2 mm) et une
  vitesse constante en m/s. **Garder les sommets des bosses** : on ne redécoupe pas à pas constant,
  on ajoute seulement des points intermédiaires si un segment est trop long.
- Approche au-dessus du premier point, descente, départ de l'extrusion, impression, arrêt de
  l'extrusion, dégagement.
- **Extrusion** : sortie à préciser (digitale ou analogique, numéro). En attendant, fonctions
  `extrusion_on()` / `extrusion_off()` paramétrées dans `cellule.toml`, désactivées par défaut.
- Poses exprimées dans le repère palette avec `pose_trans(palette, p[…])`, l'outil vertical vers le bas.
- Programme découpé en plusieurs fichiers si nécessaire pour le contrôleur (à tester).
- **Validation obligatoire dans URSim** avant tout passage sur le robot.

## 10. Étapes de construction avec Claude Code

Une étape = une session. On vérifie avant de passer à la suivante.

1. **Squelette** : arborescence, `pyproject.toml`, `pytest`, CI `tests.yml`, `CLAUDE.md` et
   `copilot-instructions.md` qui renvoient à `AGENTS.md`, `CODEOWNERS`.
2. **Pyodide** : page web minimale qui charge `trame/` avec shapely, `ezdxf` et `svgelements`, et
   affiche « OK ». Valide les choix techniques.
3. **Contour** : import SVG/DXF, prise du plus grand contour fermé, mise à l'échelle dans la palette
   avec une marge, tests sur 3 fichiers exemples.
4. **Moteur, croisements** : port de `events_on`, `process_events`, `wave_points` et de l'empilement.
   Tests unitaires sur des cas simples (deux lignes qui se croisent, trois séries).
5. **Moteur, chemin** : port de `chrono_chain`, des couloirs (`lane`) et du chemin final. Test de
   fidélité par rapport à Grasshopper.
6. **Motif exemple** : les 3 séries de lignes du .ghx, avec `PARAMETRES` et `outils.py`.
7. **Aperçu** : three.js, curseurs générés depuis `PARAMETRES` et les réglages du moteur, vues de
   dessus et 3D, couleurs par série.
8. **Contrôles** : `controles.py` et affichage des alertes dans l'aperçu.
9. **Exports DXF/SVG** : calque par série, calque des liaisons, repères de la palette.
10. **Export URScript** : calibration, approche, extrusion, `movep`. Comparaison dans URSim avec la
    trajectoire de `chemin_script_xyz.csv`.
11. **Robot dans la scène** : maillages UR10e, cinématique directe et inverse, test sur les poses du
    .script, animation le long du chemin.
12. **Alertes robot** : portée, limites, singularités, collisions simplifiées, et mode de placement de
    la palette avec la zone atteignable.
13. **Parcours étudiant** : gabarit d'issue, dossiers `groupe_1` à `groupe_4`, publication Pages, puis
    un test complet par l'enseignant en passant **uniquement par une issue assignée à Copilot**.

## 11. Questions ouvertes

- Commande de l'extrusion : sortie, type (digitale ou analogique), délai de démarrage et d'arrêt de
  la pompe.
- Largeur du cordon, hauteur de couche et vitesse : fixées pendant les essais.
- Emplacement et hauteur de la palette par rapport au robot : à choisir avec le mode de placement.
- Masse de la buse : à mesurer.
- Numéro exact de version de PolyScope 5.
