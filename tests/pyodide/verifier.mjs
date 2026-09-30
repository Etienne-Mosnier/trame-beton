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

// exports DXF, SVG et programme du robot du dernier calcul
for (const format of ["dxf", "svg", "script"]) {
  const e = JSON.parse(app.exporter(format));
  if (e.erreur || e.texte.length < 1000) throw new Error(`Export ${format} raté : ${e.erreur}`);
  console.log(`export ${format} : ${Math.round(e.texte.length / 1024)} Ko`);
}

// mouvement du bras (cinématique inverse le long du chemin)
const debutRobot = performance.now();
const bras = JSON.parse(app.robot());
if (bras.erreur) throw new Error(bras.erreur);
const zone = JSON.parse(app.placement(""));
console.log(`placement : ${zone.atteignable} % de la palette atteignable`);
console.log(`robot : ${bras.angles.length} poses, ${bras.hors_portee.length} hors de portée, ${((performance.now() - debutRobot) / 1000).toFixed(2)} s`);

// maquette G-code à l'échelle 1:4
const rc = JSON.parse(app.calculer("exemple", JSON.stringify({ moteur: { largeur_cordon: 20 } }), await readFile("contours/haricot.dxf", "utf8"), "haricot.dxf"));
if (rc.erreur) throw new Error(rc.erreur);
const g = JSON.parse(app.exporter("gcode", JSON.stringify({ largeur_essai: 5 })));
if (g.erreur) throw new Error(g.erreur);
console.log(`G-code : ${Math.round(g.texte.length / 1024)} Ko`);

console.log("OK");
