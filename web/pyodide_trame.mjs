// Chargement du package trame/ dans Pyodide.
// Partagé entre la page web (index.html) et le test Node (tests/pyodide/verifier.mjs).

export const VERSION_PYODIDE = "314.0.7";
export const URL_PYODIDE = `https://cdn.jsdelivr.net/pyodide/v${VERSION_PYODIDE}/full/`;

// Paquets fournis par Pyodide, puis paquets pur Python installés depuis PyPI.
const PAQUETS_PYODIDE = ["shapely", "micropip"];
const PAQUETS_PYPI = ["ezdxf", "svgelements"];

// pyodide : instance déjà chargée
// lireTexte(chemin) : renvoie le contenu d'un fichier du dépôt (chemin depuis la racine)
// annoncer(message) : affiche l'avancement
export async function preparer(pyodide, lireTexte, annoncer = () => {}) {
  annoncer("Chargement de shapely…");
  await pyodide.loadPackage(PAQUETS_PYODIDE);

  annoncer("Installation de ezdxf et svgelements…");
  const micropip = pyodide.pyimport("micropip");
  await micropip.install(PAQUETS_PYPI);

  annoncer("Copie du package trame/…");
  const fichiers = JSON.parse(await lireTexte("web/fichiers.json"));
  for (const chemin of fichiers) {
    const dossier = chemin.split("/").slice(0, -1).join("/");
    pyodide.FS.mkdirTree(dossier);
    pyodide.FS.writeFile(chemin, await lireTexte(chemin));
  }
  // les fichiers sont écrits dans le dossier courant de Pyodide, déjà dans sys.path
  return pyodide.pyimport("trame.app");
}
