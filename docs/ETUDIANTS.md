# Guide étudiant : faire évoluer le motif de ton groupe

Tu ne touches jamais au code toi-même. Tu décris ce que tu veux, **Copilot** modifie le
motif, et tu juges le résultat dans l'**aperçu**.

## 1. Regarder l'aperçu

Ouvre **https://etienne-mosnier.github.io/trame-beton/** (le premier chargement prend
quelques secondes). Dans la liste des motifs, ceux de ton groupe sont rangés ensemble.
Bouge les curseurs, tourne la vue 3D, clique sur « Lecture » pour voir le robot imprimer.

Chaque groupe peut avoir **plusieurs motifs** (plusieurs pistes à comparer). Le motif
« Exemple » (lignes droites qui se croisent) montre juste ce qu'est un motif : **ton générateur
peut être complètement différent** (spirale, cellules, courbes attirées par des points…).

## 2. Décrire une idée

1. Sur la page GitHub du projet, onglet **Issues** → **New issue** → **Idée de motif**.
2. Choisis ton groupe, puis ce que tu veux faire :
   - **créer un nouveau générateur** (page blanche) : donne-lui un nom court, en minuscules,
     sans accents (ex. `spirale`) ;
   - **créer une variante** d'un de tes motifs : nom + « à partir de … »
     (ex. « spirale_dense, à partir de spirale ») ;
   - **modifier un motif existant** : son nom (ex. `point_d_attraction`).
3. Décris ce que tu veux **voir**, avec tes mots, et comment les couches se superposent
   (ex. « une spirale depuis le centre de la forme, croisée par des rayons qui partent du
   même centre »). Chaque **série** est imprimée l'une après l'autre (2 à 5) et passe
   par-dessus les précédentes. Ajoute un croquis si tu peux. **Une idée par issue.**
4. Crée l'issue, puis à droite : **Assignees** → **Copilot**.

## 3. Attendre la pull request

Copilot travaille quelques minutes, puis ouvre une **pull request** (onglet *Pull requests*)
liée à ton issue. Il y décrit ce qu'il a changé et colle le bilan des contrôles.

Si un bouton **Approve and run workflows** apparaît, clique dessus : c'est ce qui lance les
tests et publie l'aperçu.

## 4. Juger le résultat

Un commentaire **« PR Preview »** apparaît dans la pull request avec un lien : c'est l'aperçu
**avec les changements de Copilot**. Ouvre-le, choisis ton motif et regarde.

- **Pas encore ça ?** Écris un commentaire dans la pull request en commençant par
  **@copilot** (ex. « @copilot les vagues sont trop hautes, divise leur hauteur par deux »).
  Copilot corrige et l'aperçu se met à jour.
- **C'est bon ?** Vérifie que les tests sont verts (✓) puis clique sur **Merge pull request**.
  Le motif rejoint l'aperçu principal quelques minutes plus tard.

## 5. Les alertes

Le bilan (dans l'aperçu et dans la pull request) signale ce qui pose problème pour le béton
ou pour le robot : lignes trop proches, croisements trop rasants, virages serrés… Une alerte
n'est pas forcément une erreur : **parlez-en avec les étudiants ingénieurs** de votre groupe.

## Règles

- Ne demande des changements que pour **ton groupe**, un motif à la fois.
- Si Copilot dit qu'il faudrait modifier autre chose que le dossier de ton groupe, c'est
  l'enseignant qui s'en occupe : mentionne-le dans l'issue.
