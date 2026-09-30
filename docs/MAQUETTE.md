# Maquette céramique sur la machine cartésienne (Klipper)

La machine cartésienne (700 × 700 × 700 mm) imprime des **maquettes à l'échelle du cordon** :
la trame conçue en vraie grandeur est réduite dans le rapport *cordon d'essai / cordon final*.
Dans l'aperçu, section **Exports** : saisir le cordon d'essai, puis **Maquette G-code**.

## Le système d'extrusion

```
piston Ø 75 mm (NEMA 23, vis au pas de 2 mm, réduction 50)  ->  tube PTFE Ø 10 mm
      ->  tête malaxeuse sur X (vis sans fin, NEMA 17)
```

Dans Klipper (`printer.cfg`, carte MKS Robin Nano V3) :
- **le piston est l'extrudeur** `[extruder]` : c'est lui qui suit l'axe E du G-code ;
- **la tête malaxeuse** `[extruder_stepper malaxeur]` est synchronisée sur le piston, dans le
  rapport k (macro `SET_RATIO_K`).

Le G-code compte **E dans l'unité de Klipper** : millimètres d'un « filament » de
`filament_diameter` (4 mm), soit 12,57 mm³ de céramique par mm de E :

> E = longueur du segment × largeur × hauteur du cordon d'essai ÷ 12,57 mm²

`diametre_filament` dans `config/cellule.toml` doit rester **égal** à `filament_diameter` de
`printer.cfg`. Le G-code commence par `SYNC_EXTRUDER_MOTION EXTRUDER=malaxeur MOTION_QUEUE=extruder` :
les macros `MALAXEUR_AVANCE` désynchronisent la tête, cette ligne la resynchronise avant d'imprimer.

## Calibration

1. **Piston** : avec la formule de `printer.cfg`, `rotation_distance = D² × p / (r × df²)
   = 75² × 2 / (50 × 4²) = 14,0625`. Vérifier : `G1 E100 F60` doit pousser
   100 × 12,57 = 1 257 mm³ (le piston avance de 0,28 mm).
2. **Tête malaxeuse** : régler k (`SET_RATIO_K`) pour qu'elle évacue ce que le piston apporte,
   sans reflux ni rotation à vide.
3. **Débit** : peser la céramique sortie pour `G1 E100 F60` et corriger avec
   `multiplicateur_extrusion` dans `config/cellule.toml`.
4. **Débit maximal** : augmenter progressivement la vitesse de E jusqu'à ce qu'un moteur
   décroche ; garder une marge et reporter la valeur (mm³/s) dans `debit_volumique_max`.

## Avant chaque impression

- Premier essai **à vide** (sans céramique) et à vitesse réduite.
- Mettre la céramique sous pression avant de lancer (ou régler `amorce` dans `config/cellule.toml`).
