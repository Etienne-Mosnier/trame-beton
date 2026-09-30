# Maquette céramique sur la machine cartésienne (Klipper)

La machine cartésienne (700 × 700 × 700 mm) imprime des **maquettes à l'échelle du cordon** :
la trame conçue en vraie grandeur est réduite dans le rapport *cordon d'essai / cordon final*.
Dans l'aperçu, section **Exports** : saisir le cordon d'essai, puis **Maquette G-code**.

## Le système d'extrusion

```
piston (NEMA 23 + vis)  ->  tube PTFE Ø intérieur 10 mm  ->  tête malaxeuse sur X (vis sans fin, NEMA 17)
```

Le G-code compte l'axe **E en millimètres de céramique dans le tube de 10 mm** :

> E = longueur du segment × largeur × hauteur du cordon d'essai ÷ section du tube (78,5 mm²)

Les deux moteurs doivent donc pousser, ensemble, **78,5 mm³ de céramique pour 1 mm de E**.

## Réglage de Klipper (printer.cfg)

La tête malaxeuse est l'extrudeur ; le piston est un moteur « synchronisé » qui suit l'axe E.
Les valeurs entre `<…>` dépendent de la machine : **à compléter et à calibrer**.

```ini
[extruder]                       # tête malaxeuse (NEMA 17, vis sans fin)
step_pin: <…>
dir_pin: <…>
enable_pin: <…>
microsteps: 16
rotation_distance: <à calibrer>  # voir plus bas
nozzle_diameter: <diamètre de la buse, mm>
filament_diameter: 10.0          # tube PTFE : E compté en mm de matière dans le tube
max_extrude_cross_section: <au moins la valeur écrite en tête du G-code>
max_extrude_only_distance: 200   # pour l'amorce et les essais d'extrusion
# pas de chauffe : déclarer un capteur factice ou min_extrude_temp: 0 selon la carte

[extruder_stepper piston]        # piston (NEMA 23 + vis)
extruder: extruder               # suit l'axe E de la tête
step_pin: <…>
dir_pin: <…>
enable_pin: <…>
microsteps: 16
rotation_distance: <à calibrer>  # voir plus bas
```

## Calibration (à faire une fois, puis à chaque changement de pâte)

1. **Piston** : il doit avancer de façon à pousser 78,5 mm³ par mm de E, c'est-à-dire avancer de
   `78,5 ÷ section du cylindre du piston` mm par mm de E. On en déduit sa `rotation_distance`
   (pas de la vis × rapport de réduction ÷ ce facteur). Vérifier en commandant `G1 E50 F60`
   et en mesurant l'avance réelle du piston.
2. **Tête malaxeuse** : régler sa `rotation_distance` pour qu'elle évacue ce que le piston
   apporte, sans que la pression monte (la céramique reflue) ni que la tête tourne à vide.
3. **Débit** : peser la céramique sortie pour `G1 E100 F60` : on doit obtenir 7 850 mm³
   (7,85 cm³ × densité de la pâte). Corriger avec `multiplicateur_extrusion` dans
   `config/cellule.toml`.
4. **Débit maximal** : augmenter progressivement la vitesse de E jusqu'à ce que la tête ou le
   piston décroche ; garder une marge et reporter la valeur (en mm³/s) dans
   `debit_volumique_max` : la vitesse de la maquette s'en déduit automatiquement.

## Avant chaque impression

- Premier essai **à vide** (sans céramique) et à vitesse réduite.
- Mettre la céramique sous pression avant de lancer (ou régler `amorce` dans `config/cellule.toml`).
