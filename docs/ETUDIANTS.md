# Guide étudiant : faire évoluer le motif de ton groupe

Tu ne touches jamais au code toi-même. Tu décris ce que tu veux, **Copilot** modifie le
motif, et tu juges le résultat dans l'**aperçu**.

## 1. Regarder l'aperçu

Ouvre **https://etienne-mosnier.github.io/trame-beton/** (le premier chargement prend
quelques secondes). Choisis le motif de ton groupe, bouge les curseurs, tourne la vue 3D,
coche « Montrer le robot qui imprime » pour voir la machine au travail.

## 2. Décrire une idée

1. Sur la page GitHub du projet, onglet **Issues** → **New issue** → **Idée de motif**.
2. Choisis ton groupe et décris ce que tu veux **voir**, avec tes mots
   (ex. « les lignes de B deviennent des vagues, plus serrées au centre »).
   Ajoute un croquis si tu peux. **Une idée par issue.**
3. Crée l'issue, puis à droite : **Assignees** → **Copilot**.

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

- Ne demande des changements que pour **ton groupe**.
- Si Copilot dit qu'il faudrait modifier autre chose que le dossier de ton groupe, c'est
  l'enseignant qui s'en occupe : mentionne-le dans l'issue.
