// Vérifie que trame/ fonctionne dans Pyodide (même chargement que la page web).
// Lancer depuis la racine du dépôt :
//   python3 web/construire.py
//   npm install --no-save pyodide@314.0.7 && node tests/pyodide/verifier.mjs

import { readFile } from "node:fs/promises";
import { loadPyodide } from "pyodide";
import { preparer, VERSION_PYODIDE } from "../../web/pyodide_trame.mjs";

const pyodide = await loadPyodide();
if (pyodide.version !== VERSION_PYODIDE) {
  throw new Error(`Pyodide ${pyodide.version} installé, ${VERSION_PYODIDE} attendu`);
}
const { app } = await preparer(pyodide, (chemin) => readFile(chemin, "utf8"), console.log);
const resultat = JSON.parse(app.verifier());
console.log(resultat);
if (!resultat.ok || resultat.croisement[0] !== 50 || resultat.croisement[1] !== 50) {
  throw new Error("Résultat inattendu");
}

// les 4 contours exemples, lus et placés dans Pyodide (copiés par preparer)
const noms = ["rectangle.svg", "haricot.dxf", "grand.svg", "lignes.dxf"];
const messages = pyodide.runPython(`
from trame.contour import charger_contour
[charger_contour(open("contours/" + n).read(), n)["message"] for n in ${JSON.stringify(noms)}]
`).toJs();
console.log(messages);
if (!messages[1].includes("tournée")) throw new Error("Le haricot aurait dû être tourné");

// le calcul complet de l'aperçu : motif exemple sur le haricot
const debut = performance.now();
const r = JSON.parse(app.calculer("exemple", "{}", await readFile("contours/haricot.dxf", "utf8"), "haricot.dxf"));
console.log(`aperçu : ${r.path?.length} points, ${r.controle?.sauts} saut(s), ${((performance.now() - debut) / 1000).toFixed(2)} s`);
if (r.erreur) throw new Error(r.erreur);
if (r.controle.sauts !== 0) throw new Error("Le chemin devrait être continu");

// exports DXF et SVG du dernier calcul
for (const format of ["dxf", "svg"]) {
  const e = JSON.parse(app.exporter(format));
  if (e.erreur || e.texte.length < 1000) throw new Error(`Export ${format} raté : ${e.erreur}`);
  console.log(`export ${format} : ${Math.round(e.texte.length / 1024)} Ko`);
}

console.log("OK");
