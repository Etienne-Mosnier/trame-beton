; ======================================================================
; ESSAI DE PAUSE - WASP 2040 (Marlin) - A LANCER A VIDE, SANS ARGILE
; ======================================================================
; L'extrusion est geree par le boitier externe : le laisser ETEINT.
; Ce fichier ne fait que bouger la tete. Duree : environ 5 minutes,
; dont 3 minutes de pause.
;
; Ce que l'on doit voir :
;  1. la tete monte en haut (origine), puis descend au centre,
;     a 50 mm au-dessus du plateau ;
;  2. elle trace un carre de 40 mm en l'air ;
;  3. elle s'arrete, l'ecran affiche "Pause : cliquer pour reprendre".
;     ATTENDRE 3 MINUTES SANS TOUCHER : la tete ne doit ni bouger
;     ni descendre (les moteurs doivent rester tenus) ;
;  4. cliquer sur le bouton de l'ecran ;
;  5. elle retrace le meme carre, au meme endroit et a la meme hauteur ;
;  6. elle remonte en haut.
;
; A noter pour la suite :
;  - la pause a-t-elle attendu le clic ?          (sinon : M0 non pris en charge)
;  - la tete a-t-elle bouge pendant les 3 min ?   (sinon : moteurs relaches)
;  - le 2e carre est-il au meme endroit ?         (sinon : position perdue)
; ======================================================================

G21                 ; unites en mm
G90                 ; deplacements en absolu
M84 S0              ; ne jamais relacher les moteurs pendant une pause longue

M117 Essai pause WASP
G28                 ; origine : la tete monte en haut
G0 Z100 F3000       ; descente au centre
G0 X0 Y0 Z50 F1500  ; 50 mm au-dessus du plateau

; --- premier carre ---
G1 X20 Y20 F1200
G1 X-20 Y20
G1 X-20 Y-20
G1 X20 Y-20
G1 X20 Y20

; --- pause : on attend le clic ---
M400                ; attendre la fin des mouvements
M117 Pause : cliquer pour reprendre
M0 Pause : cliquer pour reprendre

; --- second carre, au meme endroit ---
M117 Reprise
G1 X-20 Y20 F1200
G1 X-20 Y-20
G1 X20 Y-20
G1 X20 Y20

; --- fin ---
G0 Z100 F1500
G28                 ; retour en haut
M117 Essai termine
