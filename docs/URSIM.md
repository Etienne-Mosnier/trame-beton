# Tester le programme du robot dans URSim

**Obligatoire avant tout passage sur le vrai robot.** URSim est le simulateur officiel
d'Universal Robots : c'est le même logiciel (PolyScope) que sur le pendant du robot.

## 1. Récupérer le programme

Dans l'aperçu, section **Exports**, clique sur **Programme du robot (URScript)**.
Un fichier `trame_<motif>.script` est téléchargé.

Tant que la calibration de la palette n'est pas relevée, le programme utilise une
**calibration de simulation** et affiche un message d'avertissement au démarrage.

## 2. Installer URSim

- Télécharger **URSim e-Series 5.x** sur le site d'Universal Robots (rubrique *Download*,
  *Software*, *Offline Simulator*), de la même version que PolyScope sur le robot.
- URSim fonctionne sur un PC (machine virtuelle Linux fournie par Universal Robots).
  Sur un Mac récent (puce Apple), c'est lent ou impossible : un PC de l'école est plus simple.

## 3. Charger le programme

1. Copie le fichier `.script` sur une clé USB, ou dans le dossier `programs` de URSim.
2. Dans PolyScope : **Programme** → **Nouveau** → onglet **Avancé** → **Script**.
3. Choisis **Fichier**, puis ton fichier `.script`.
4. Lance le programme (bouton lecture), d'abord à vitesse réduite (curseur de vitesse en bas).

## 4. Ce qu'il faut vérifier

- Le programme démarre sans erreur de syntaxe.
- Le robot va au-dessus du premier point, descend lentement, puis suit tout le chemin
  **sans arrêt de protection** (*protective stop*) ni message « hors de portée ».
- Le mouvement est régulier (pas d'arrêt à chaque point).
- À la fin, la buse remonte de 5 cm.
- Note la durée réelle et compare-la à celle annoncée dans l'aperçu.

Si quelque chose se passe mal, copie le message d'erreur exact de PolyScope (ou une photo
de l'écran) dans une issue : c'est ce qui permet de corriger le programme.
