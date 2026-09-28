# Exemple : trois séries de lignes

Trois séries de lignes droites, imprimées l'une après l'autre :

1. **A** est imprimée en premier, à plat sur la bâche.
2. **B** passe par-dessus A : à chaque croisement, le cordon monte d'une couche.
3. **C** passe par-dessus A et B : il monte d'une couche sur A ou B, de deux couches
   là où il passe sur une bosse de B.

Les trois directions forment des losanges. Si deux directions sont presque pareilles
(moins de 20° d'écart), les croisements deviennent très rasants et les bosses se chevauchent.

## Réglages

- **espacement** : écart entre deux lignes d'une même série. Plus petit = trame plus serrée.
  En dessous de 2 fois la largeur du cordon, les lignes se touchent.
- **angle_a, angle_b, angle_c** : direction des lignes de chaque série, en degrés
  (0° = le long du grand côté de la palette, 90° = le long du petit côté).

## Pour faire ton propre motif

Copie ce dossier dans `motifs/groupe_N/` et décris dans une issue ce que tu veux changer :
des lignes ondulées, des cercles, une quatrième série…
