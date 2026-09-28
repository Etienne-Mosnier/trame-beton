// Vérifie que trame/ fonctionne dans Pyodide (même chargement que la page web).
// Lancer depuis la racine du dépôt :
//   npm install --no-save pyodide@314.0.7 && node tests/pyodide/verifier.mjs

import { readFile } from "node:fs/promises";
import { loadPyodide } from "pyodide";
import { preparer, VERSION_PYODIDE } from "../../web/pyodide_trame.mjs";

const pyodide = await loadPyodide();
if (pyodide.version !== VERSION_PYODIDE) {
  throw new Error(`Pyodide ${pyodide.version} installé, ${VERSION_PYODIDE} attendu`);
}
const app = await preparer(pyodide, (chemin) => readFile(chemin, "utf8"), console.log);
const resultat = JSON.parse(app.verifier());
console.log(resultat);
if (!resultat.ok || resultat.croisement[0] !== 50 || resultat.croisement[1] !== 50) {
  throw new Error("Résultat inattendu");
}

// les 4 contours exemples, lus et placés dans Pyodide
const noms = ["rectangle.svg", "haricot.dxf", "grand.svg", "lignes.dxf"];
for (const nom of noms) {
  pyodide.FS.writeFile(nom, await readFile(`tests/contours/${nom}`, "utf8"));
}
const messages = pyodide.runPython(`
from trame.contour import charger_contour
[charger_contour(open(n).read(), n)["message"] for n in ${JSON.stringify(noms)}]
`).toJs();
console.log(messages);
if (!messages[1].includes("tournée")) throw new Error("Le haricot aurait dû être tourné");

// le moteur complet sur le haricot : 3 séries, comme le .ghx
const debut = performance.now();
const bilan = pyodide.runPython(`
import math
from trame.contour import charger_contour
from trame.moteur.chemin import calculer_chemin
forme = charger_contour(open("haricot.dxf").read(), "haricot.dxf")["contour"]
cx, cy = forme.centroid.x, forme.centroid.y
def lignes(angle):
    a = math.radians(angle); ux, uy = math.cos(a), math.sin(a)
    return [[(cx - uy*50*k - 2000*ux, cy + ux*50*k - 2000*uy),
             (cx - uy*50*k + 2000*ux, cy + ux*50*k + 2000*uy)] for k in range(-20, 21)]
r = calculer_chemin([lignes(160), lignes(29), lignes(135)], forme, active=[1, 2])
r["controle"]["sauts"], len(r["path"])
`).toJs();
console.log(`moteur : ${bilan[1]} points, ${bilan[0]} saut(s), ${((performance.now() - debut) / 1000).toFixed(2)} s`);
if (bilan[0] !== 0) throw new Error("Le chemin devrait être continu");

console.log("OK");
