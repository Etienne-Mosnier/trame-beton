# Règles pour les agents (Claude Code, GitHub Copilot)

Ce fichier est lu par tous les agents qui travaillent sur ce dépôt. `CLAUDE.md` et
`.github/copilot-instructions.md` renvoient ici : **les règles ne s'écrivent qu'ici.**

## Le projet

Application web de création de **trames imprimées en béton** par un bras UR10e.
La trame est imprimée à plat sur une bâche posée sur une palette EPAL (1200 × 800 mm).
La bâche est ensuite soulevée en certains points pour donner du volume à la trame.

Les utilisateurs sont des **étudiants designers qui ne savent pas coder**. Ils décrivent
ce qu'ils veulent en français, dans des issues GitHub, et jugent le résultat dans l'aperçu
web. Ils ne lisent pas le code. Tout ce que tu écris doit donc être **simple, court, commenté
en français et facile à copier**.

## Comment l'application fonctionne

```
contour (SVG/DXF, mis à l'échelle de la palette)
   └─> MOTIF d'un groupe  ──> séries de courbes à plat (A, B, C…)
          └─> MOTEUR de croisements ──> un seul chemin continu, avec bosses d'empilement
                 └─> CONTRÔLES (imprimabilité) ──> APERÇU web
                 └─> EXPORTS : DXF/SVG (ingénieurs), URScript (robot)
```

- Un **motif** ne fait qu'une chose : renvoyer des **séries de courbes 2D** (en mm, dans le
  repère de la palette). Il ne s'occupe ni des croisements, ni des bosses, ni du robot.
- L'**ordre des séries est l'ordre d'impression** : la série B passe par-dessus A, la série C
  par-dessus A et B, etc. Aux croisements, le moteur fait monter la série d'une bosse au-dessus
  de ce qu'elle recouvre (empilement). 2 à 5 séries = 2 à 5 niveaux de cordon.

## Ce que tu as le droit de modifier

| Dossier | Qui | Règle |
|---|---|---|
| `motifs/<groupe>/<motif>/` | étudiants + agent | **seule zone de travail des étudiants** |
| `motifs/exemple/` | enseignant | exemple de référence (la forme d'un motif, pas une base), ne pas modifier |
| `trame/moteur/`, `trame/robot/`, `trame/contour.py`, `trame/export/` | enseignant | **ne jamais modifier** dans une issue d'étudiant |
| `web/` | enseignant | ne pas modifier, sauf demande explicite de l'enseignant |
| `config/cellule.toml` | enseignant | **ne jamais modifier** (réglages physiques du robot) |
| `tests/` | enseignant | ne pas supprimer ni affaiblir un test pour le faire passer |

Si une demande d'étudiant ne peut être satisfaite qu'en modifiant une zone interdite :
**ne la modifie pas**. Explique dans la pull request ce qu'il faudrait changer, en français
simple, et mentionne l'enseignant.

## Écrire un motif

Un motif = un dossier. Chaque groupe peut en avoir plusieurs : `motifs/groupe_1/spirale/`,
`motifs/groupe_1/vagues/`… Nom de dossier court, en minuscules, sans accents ni espaces
(lettres, chiffres, `_`).

`motifs/exemple/` (trois séries de lignes droites qui se croisent) montre **la forme** d'un fichier
de motif. **Ce n'est pas une base** : un nouveau générateur ne reprend pas ses lignes droites,
il construit la géométrie que l'étudiant décrit. Seule la forme du fichier est imposée :

```python
NOM = "Nom lisible du motif"
PARAMETRES = {
    "espacement": Parametre(50, mini=20, maxi=150, unite="mm", aide="Écart entre deux lignes"),
    "forme": Choix("vagues", ["vagues", "zigzag"], aide="Forme des lignes de la série B"),
    "inverser": Case(False, aide="Inverser le sens des vagues"),
    "centre": Point(600, 400, aide="Centre des cercles"),
    "attractions": Points([(400, 400)], mini=0, maxi=8, aide="Points qui attirent les lignes"),
    "series": Liste([{"angle": 160, "espacement": 50}, {"angle": 29, "espacement": 50}],
                    mini=2, maxi=5, element="Série",
                    champs={"angle": Parametre(90, mini=0, maxi=180, unite="°", aide="Direction"),
                            "espacement": Parametre(50, mini=20, maxi=150, unite="mm", aide="Écart")},
                    aide="Une ligne par série"),
    ...
}

def series(contour, p):
    """Renvoie une liste de séries ; chaque série est une liste de courbes (LineString shapely)."""
```

Règles :
- **Un motif = un dossier avec un fichier `motif.py`**, plus un `aide.md` qui explique le motif.
- `NOM` : le nom affiché dans l'aperçu, court et parlant (ex. « Vagues serrées au centre »).
- Seulement `math`, `shapely`, les types de `trame/parametres.py` et les fonctions de
  `trame/outils.py`. Aucune autre dépendance. Tu peux écrire tes propres fonctions dans `motif.py`.
- Pas de classes, pas de métaprogrammation, pas d'astuce : des fonctions courtes et des boucles.
- Noms de variables et commentaires **en français**. Chaque paramètre a une `aide` compréhensible
  par un designer.
- Tout paramètre qu'un étudiant voudrait régler dans l'aperçu doit être dans `PARAMETRES`,
  jamais écrit en dur dans le code.
- **Tout ce que l'étudiant veut régler passe par ces 6 types** (`from trame.parametres import …`) ;
  l'aperçu sait tous les afficher. **Tu n'as jamais besoin de modifier `web/` pour un motif.**

  | Type | Dans l'aperçu | Valeur dans `p["nom"]` |
  |---|---|---|
  | `Parametre(valeur, mini, maxi, unite, aide)` | un curseur | un nombre |
  | `Choix(valeur, [options], aide)` | une liste déroulante | le texte choisi |
  | `Case(valeur, aide)` | une case oui / non | `True` / `False` |
  | `Point(x, y, aide)` | une poignée (boule noire) à déplacer sur la palette | `(x, y)` en mm |
  | `Points([(x, y), …], mini, maxi, aide)` | des poignées que l'on **ajoute** (double-clic sur la palette), **déplace** (clic) et **supprime** (double-clic sur le point) | liste de `(x, y)` en mm |
  | `Liste([v, …], mini, maxi, bornes, unite, element, aide)` | un curseur par élément, **+ Ajouter** / **×** pour retirer | liste de nombres |
  | `Liste([{…}, …], mini, maxi, element, champs={nom: Parametre(…)}, aide)` | une ligne par élément, ses curseurs côte à côte, **+ Ajouter** / **×** | liste de dictionnaires |

  Pour des séries que l'on ajoute ou retire, chacune avec ses propres réglages, utilise une
  `Liste` avec `element="Série"` et des `champs` (ex. angle et espacement) : voir `motifs/exemple/`.

  Points en mm, repère palette (origine au coin, x le long du grand côté). Pour des points
  d'attraction, centres, départs… utilise `Point` ou `Points`, jamais deux curseurs x et y.
  Avec `Points` et `mini=0`, le motif doit marcher aussi sans aucun point.
- Unités : **millimètres** et **degrés**, partout.
- Place la géométrie **par rapport au contour** (`outils.centre(contour)`, `contour.bounds`…),
  pas avec des coordonnées fixes : la forme peut être réduite ou tournée pour tenir sur la palette.
- Les courbes peuvent dépasser du contour : le moteur les découpe.

## Traiter une issue « Idée de motif »

1. Le groupe et le motif sont indiqués dans l'issue : modifie **uniquement** le dossier
   `motifs/<groupe>/<motif>/` (le créer si c'est un nouveau motif). Ne touche jamais aux autres
   motifs, même du même groupe.
2. Selon « Que veux-tu faire ? » :
   - **Nouveau générateur (page blanche)** : écris `motif.py` à partir de zéro, avec la forme
     ci-dessus. Invente la géométrie décrite (spirale, cellules, rayons, courbes attirées,
     tracés récursifs…) avec `math`, `shapely`, `trame/outils.py` ou tes propres fonctions.
     Ne copie pas les lignes de l'exemple. Décide avec l'étudiant ce que sont les séries
     (l'ordre d'impression, 2 à 5) : c'est ce qui crée les croisements et les bosses.
   - **Variante** : copie le motif indiqué comme départ, puis modifie la copie.
   - **Modifier** : pars de la version **actuelle** du motif et garde ce qui marche déjà.
3. Tout ce que l'étudiant veut pouvoir régler devient un `Parametre` avec une `aide`.
4. Mets à jour `aide.md` : ce que l'on voit, ce que fait chaque réglage, ce qu'il faut éviter.
5. Lance `pytest` et `python -m trame.bilan <groupe>/<motif>` ; colle le bilan dans la pull request.
6. L'aperçu de la pull request est publié automatiquement : un lien apparaît en commentaire.
   Rappelle à l'étudiant de l'ouvrir pour juger le résultat.

## Une seule ligne continue (règle du projet)

Quoi qu'il arrive, la buse imprime **une seule polyligne continue**. Le moteur enchaîne les
courbes de chaque série selon leur nature :
- **courbes ouvertes qui traversent la forme** (lignes, vagues, rayons…) : reliées en
  **zigzag**, une fois d'un côté, une fois de l'autre, le long du bord ;
- **courbes fermées emboîtées** (cercles concentriques, `outils.contours_decales`…) : fondues
  en **une spirale**, du centre vers l'extérieur.

Donc, dans une série : fais traverser les courbes ouvertes d'un bord à l'autre (elles peuvent
dépasser, le moteur les coupe), ou emboîte les courbes fermées les unes dans les autres. Une
courbe ouverte qui s'arrête au milieu de la forme, ou des courbes fermées côte à côte, sont
raccordées en ligne droite : le contrôle « Une seule ligne : zigzag ou spirale » le signale.
Le test de chaque motif exige un chemin sans aucun saut.

## Contraintes du béton (à respecter dans les motifs)

Les valeurs exactes sont dans `config/cellule.toml` et seront ajustées pendant les essais.
- Deux lignes d'une même série ne doivent pas être plus proches que **2 × la largeur du cordon**.
- Éviter les virages plus serrés que le **rayon de courbure minimal**.
- Éviter les croisements très rasants (angle < 20° entre deux séries) : les bosses se chevauchent.
- Le chemin doit rester **continu** : pas de sauts. Le moteur relie les courbes le long du contour.

Les contrôles automatiques (`trame/controles.py`) signalent ces problèmes dans l'aperçu et dans
les tests. **Un avertissement n'est pas un bug à masquer** : il se discute avec les étudiants
ingénieurs du groupe.

## Pull requests

- Une pull request = une idée. Titre en français.
- Décris le résultat **visuellement** (« les lignes forment maintenant des losanges plus serrés
  au centre »), pas le code.
- Les tests doivent passer (`pytest`). Si un contrôle d'imprimabilité échoue, dis-le clairement.
- Colle dans la pull request le bilan des contrôles du motif :
  `python -m trame.bilan <groupe>/<motif>` (contour haricot) ou
  `python -m trame.bilan <groupe>/<motif> rectangle.svg`.
- Ne touche jamais aux fichiers d'un autre groupe.
