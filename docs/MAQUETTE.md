# Maquette sur le WASP 2040

Le WASP 2040 (imprimante delta, Marlin, plateau rond de 200 mm) imprime des **maquettes à
l'échelle du cordon** : la trame conçue en vraie grandeur est réduite dans le rapport
*cordon d'essai / cordon final*, en X, Y et Z (bosses, couches et pauses comprises).
Dans l'aperçu, section **Exports** : saisir le cordon d'essai (à peu près la buse), puis
**Maquette G-code**. Si la maquette ne tient pas sur le plateau, l'aperçu donne le cordon
d'essai le plus large possible.

## Ce que fait le G-code

- Origine au centre du plateau ; le centre de la palette va au centre du plateau.
- **L'extrusion est continue, réglée sur le boîtier externe** : le G-code ne commande que les
  déplacements (aucune valeur d'extrusion). La vitesse d'impression (`vitesse` dans
  `config/cellule.toml`, section `[wasp]`) doit être accordée avec le débit du boîtier.
- Comme le robot, la machine **s'arrête et attend un clic sur son écran** (`M0`) :
  1. au départ, tête à côté du dessin : lancer l'extrusion, puis cliquer ;
  2. à chaque pause : la tête est sortie du dessin sans passer au-dessus de l'argile ;
  3. à la fin, tête à côté du dessin : couper l'extrusion, puis cliquer.
- `M84 S0` en tête : les moteurs ne sont jamais relâchés pendant un arrêt (sur une delta, la
  tête tomberait ou perdrait sa position).

## Avant la première maquette

Lancer à vide `docs/wasp/essai_pause.gcode` (boîtier éteint, sans argile) et vérifier :
- que la pause attend bien le clic ;
- que la tête ne bouge pas pendant les 3 minutes de pause ;
- que le second carré est au même endroit que le premier.

## Réglages (`config/cellule.toml`, section `[wasp]`)

| Réglage | Rôle |
|---|---|
| `largeur_cordon_essai` | cordon de la maquette proposé dans l'aperçu (mm) |
| `diametre_plateau`, `marge` | la maquette reste dans ce cercle |
| `hauteur` | hauteur d'impression maximale |
| `vitesse` | vitesse d'impression (mm/s), à accorder avec le débit du boîtier |
| `vitesse_deplacement` | arrivée au départ et dégagement final (mm/s) |
| `hauteur_buse` | hauteur de la buse pour la 1re couche (0 = hauteur de couche d'essai) |
| `hauteur_approche` | la tête arrive au départ et repart à la fin à cette hauteur (mm) |
