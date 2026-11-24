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

// les dessins d'exemple : calques lus dans Pyodide (copiés par preparer)
for (const [nom, attendus] of [["vagues.svg", 2], ["spirales.dxf", 3]]) {
  const c = JSON.parse(app.lire_calques(await readFile("dessins/" + nom, "utf8"), nom));
  if (c.erreur || c.calques.length !== attendus) throw new Error(`Calques de ${nom} mal lus : ${c.erreur}`);
  console.log(`${nom} : ${c.calques.map((k) => k.nom).join(", ")}`);
}

// le calcul complet de l'aperçu : dessin d'exemple, ordre des calques choisi
const debut = performance.now();
const texte = await readFile("dessins/spirales.dxf", "utf8");
const r = JSON.parse(app.calculer(JSON.stringify({ calques: ["3 vagues", "1 spirale", "2 boucles"] }), texte, "spirales.dxf"));
if (r.erreur) throw new Error(r.erreur);
console.log(`aperçu : ${r.path.length} points, ${r.calques.join(" > ")}, ${((performance.now() - debut) / 1000).toFixed(2)} s`);
if (r.calques[0] !== "3 vagues" || r.jumps.length !== 0) throw new Error("Ordre des calques ou chemin inattendu");

// pauses : trajet à vide entre les lignes déjà imprimées (le plus long à calculer)
const debutPause = performance.now();
const rp = JSON.parse(app.calculer(JSON.stringify({ pauses: ["1 spirale", "2 boucles"], moteur: { couches: 2 } }), texte, "spirales.dxf"));
if (rp.erreur) throw new Error(rp.erreur);
console.log(`pauses : ${rp.pauses.length}, ${((performance.now() - debutPause) / 1000).toFixed(2)} s`);
if (rp.pauses.length !== 4) throw new Error("4 pauses attendues (2 par couche)");
const sp = JSON.parse(app.exporter("script"));
if (sp.erreur || !sp.texte.includes("trame-beton : pause 4")) throw new Error(`Programme avec pauses raté : ${sp.erreur}`);

// exports DXF, SVG et programme du robot du dernier calcul (sans pause)
JSON.parse(app.calculer(JSON.stringify({ calques: ["3 vagues", "1 spirale", "2 boucles"] }), texte, "spirales.dxf"));
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

// maquette G-code (WASP 2040) au 1:6,67, avec une pause
const rc = JSON.parse(app.calculer(JSON.stringify({ pauses: ["1 spirale"] }), texte, "spirales.dxf"));
if (rc.erreur) throw new Error(rc.erreur);
const g = JSON.parse(app.exporter("gcode", JSON.stringify({ largeur_essai: 1.5 })));
if (g.erreur) throw new Error(g.erreur);
if ((g.texte.match(/\nM0 /g) || []).length !== 3) throw new Error("3 arrêts M0 attendus (départ, pause, fin)");
console.log(`G-code : ${Math.round(g.texte.length / 1024)} Ko`);

console.log("OK");
