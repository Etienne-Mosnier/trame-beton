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
| `motifs/<groupe>/` | étudiants + agent | **seule zone de travail des étudiants** |
| `motifs/exemple/` | enseignant | modèle à copier, ne pas modifier |
| `trame/moteur/`, `trame/robot/`, `trame/contour.py`, `trame/export/` | enseignant | **ne jamais modifier** dans une issue d'étudiant |
| `web/` | enseignant | ne pas modifier, sauf demande explicite de l'enseignant |
| `config/cellule.toml` | enseignant | **ne jamais modifier** (réglages physiques du robot) |
| `tests/` | enseignant | ne pas supprimer ni affaiblir un test pour le faire passer |

Si une demande d'étudiant ne peut être satisfaite qu'en modifiant une zone interdite :
**ne la modifie pas**. Explique dans la pull request ce qu'il faudrait changer, en français
simple, et mentionne l'enseignant.

## Écrire un motif

Copie `motifs/exemple/motif.py` et garde exactement la même forme :

```python
NOM = "Nom lisible du motif"
PARAMETRES = {
    "espacement": Parametre(50, mini=20, maxi=150, unite="mm", aide="Écart entre deux lignes"),
    ...
}

def series(contour, p):
    """Renvoie une liste de séries ; chaque série est une liste de courbes (LineString shapely)."""
```

Règles :
- **Un motif = un fichier `motif.py`**, plus éventuellement un `aide.md` qui explique le motif.
- Seulement `math`, `shapely`, `Parametre` (de `trame/parametres.py`) et les fonctions de
  `trame/outils.py`. Aucune autre dépendance.
- Pas de classes, pas de métaprogrammation, pas d'astuce : des fonctions courtes et des boucles.
- Noms de variables et commentaires **en français**. Chaque paramètre a une `aide` compréhensible
  par un designer.
- Tout paramètre qu'un étudiant voudrait régler dans l'aperçu doit être dans `PARAMETRES`,
  jamais écrit en dur dans le code.
- Unités : **millimètres** et **degrés**, partout.
- Les courbes peuvent dépasser du contour : le moteur les découpe.

## Traiter une issue « Idée de motif »

1. Le groupe est indiqué dans l'issue : modifie **uniquement** `motifs/<groupe>/motif.py` et
   `motifs/<groupe>/aide.md`.
2. Pars du motif **actuel** du groupe, pas de l'exemple : garde ce qui marche déjà.
3. Tout ce que l'étudiant veut pouvoir régler devient un `Parametre` avec une `aide`.
4. Mets à jour `aide.md` : ce que l'on voit, ce que fait chaque réglage, ce qu'il faut éviter.
5. Lance `pytest` et `python -m trame.bilan <groupe>` ; colle le bilan dans la pull request.
6. L'aperçu de la pull request est publié automatiquement : un lien apparaît en commentaire.
   Rappelle à l'étudiant de l'ouvrir pour juger le résultat.

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
  `python -m trame.bilan <groupe>` (contour haricot) ou `python -m trame.bilan <groupe> rectangle.svg`.
- Ne touche jamais aux fichiers d'un autre groupe.
