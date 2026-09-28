// Aperçu de la trame : curseurs générés depuis PARAMETRES, calcul en Python (Pyodide),
// dessin avec three.js. Unités : mm, z vers le haut.
// Repère de la scène : celui du robot. La palette (avec tout ce qu'elle porte) est un objet
// que l'on sélectionne d'un clic et que l'on déplace ou tourne avec un gizmo.

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { TransformControls } from "three/addons/controls/TransformControls.js";
import { Line2 } from "three/addons/lines/Line2.js";
import { LineGeometry } from "three/addons/lines/LineGeometry.js";
import { LineMaterial } from "three/addons/lines/LineMaterial.js";
import { preparer, URL_PYODIDE } from "./pyodide_trame.mjs";
import { creerBuse, creerRobot } from "./robot.js";

// une couleur par série, dans l'ordre d'impression
const COULEURS = ["#6b7280", "#2563eb", "#16a34a", "#9333ea", "#d97706"]; // le rouge est gardé pour les problèmes
const NOMS_SERIES = ["A", "B", "C", "D", "E"];
const LARGEUR_CORDON = 4; // mm, pour le dessin seulement

const $ = (id) => document.getElementById(id);
const etat = $("etat");

// ---------------------------------------------------------------------------
// Scène three.js
// ---------------------------------------------------------------------------

THREE.Object3D.DEFAULT_UP.set(0, 0, 1);
const scene = new THREE.Scene();
scene.background = new THREE.Color("#f4f1ea");
const camera = new THREE.PerspectiveCamera(35, 1, 1, 20000);
const rendu = new THREE.WebGLRenderer({ antialias: true });
rendu.setPixelRatio(window.devicePixelRatio);
$("scene").appendChild(rendu.domElement);
const controles = new OrbitControls(camera, rendu.domElement);

scene.add(new THREE.HemisphereLight("#ffffff", "#b9b2a4", 2.5));
const soleil = new THREE.DirectionalLight("#ffffff", 1.5);
soleil.position.set(300, -600, 1200);
scene.add(soleil);

// La palette : un pivot à son centre (déplacé par le gizmo), et son contenu en coordonnées
// palette (origine au coin). Tout ce qui est dessiné sur la palette va dans « contenuPalette ».
const paletteMobile = new THREE.Group();
const contenuPalette = new THREE.Group();
paletteMobile.add(contenuPalette);
scene.add(paletteMobile);

// groupes redessinés à chaque calcul, sur la palette
const groupePalette = new THREE.Group();
const groupeTrame = new THREE.Group();
const groupeAlertes = new THREE.Group(); // endroits à problème, en rouge
const groupeCordon = new THREE.Group();  // cordon déposé pendant l'animation du robot
const groupeAlertesRobot = new THREE.Group(); // alertes robot, en rouge
contenuPalette.add(groupePalette, groupeTrame, groupeAlertes, groupeCordon, groupeAlertesRobot);
// groupes fixes par rapport au robot
const groupeZone = new THREE.Group();    // partie de la palette hors de portée (mode placement)
const groupePortee = new THREE.Group();  // portée du robot, ses axes et la boussole
scene.add(groupeZone, groupePortee);

// gizmos de la palette : l'un déplace à plat (flèches), l'autre tourne autour de la verticale
const gizmoDeplacer = new TransformControls(camera, rendu.domElement);
gizmoDeplacer.setMode("translate");
gizmoDeplacer.showZ = false;
gizmoDeplacer.setTranslationSnap(10);
gizmoDeplacer.setSize(1.6);
const gizmoTourner = new TransformControls(camera, rendu.domElement);
gizmoTourner.setMode("rotate");
gizmoTourner.showX = gizmoTourner.showY = false;
gizmoTourner.setRotationSnap(THREE.MathUtils.degToRad(5));
gizmoTourner.setSize(1.6);
const gizmos = [gizmoDeplacer, gizmoTourner];
for (const g of gizmos) scene.add(g.getHelper());
const materiaux = [];

let palette = [1200, 800];

// place la palette dans le repère du robot (repère de la calibration en cours)
let repereCourant = null;
function positionnerPalette() {
  const [lx, ly] = palette;
  contenuPalette.position.set(-lx / 2, -ly / 2, 0);
  const rep = repereCourant;
  if (!rep) {
    paletteMobile.position.set(lx / 2, ly / 2, 0);
    paletteMobile.quaternion.identity();
    return;
  }
  const [x, y, z] = [rep.x, rep.y, rep.z].map((v) => new THREE.Vector3(...v));
  const centre = new THREE.Vector3(...rep.origine).addScaledVector(x, lx / 2).addScaledVector(y, ly / 2);
  paletteMobile.position.copy(centre);
  paletteMobile.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(x, y, z));
}

function vueDessus() {
  const [lx, ly] = palette;
  const c = paletteMobile.position;
  controles.target.copy(c);
  camera.position.set(c.x, c.y - 1, c.z + Math.max(lx, ly) * 2.6);
  controles.update();
  activer("vue-dessus");
}

function vue3d() {
  const [lx, ly] = palette;
  const c = paletteMobile.position;
  if (repereCourant) {
    // le robot (à l'origine) et la palette dans le cadre, vus de derrière le robot
    const milieu = new THREE.Vector3(c.x / 2, c.y / 2, 200);
    const recul = new THREE.Vector3(-c.x, -c.y, 0).normalize();
    const cote = new THREE.Vector3(-recul.y, recul.x, 0);
    controles.target.copy(milieu);
    camera.position.copy(milieu).addScaledVector(recul, 2600).addScaledVector(cote, 1400).setZ(2600);
    controles.update();
    activer("vue-3d");
    return;
  }
  controles.target.copy(c);
  camera.position.set(c.x + 250, c.y - ly * 1.75, Math.max(lx, ly) * 1.05);
  controles.update();
  activer("vue-3d");
}

function activer(id) {
  for (const b of ["vue-dessus", "vue-3d"]) $(b).classList.toggle("actif", b === id);
}

function redimensionner() {
  const zone = $("scene");
  const l = zone.clientWidth, h = zone.clientHeight;
  rendu.setSize(l, h);
  camera.aspect = l / h;
  camera.updateProjectionMatrix();
  for (const m of materiaux) m.resolution.set(l, h);
}

let horloge = performance.now();
function boucle() {
  const maintenant = performance.now();
  if (robot.lecture && robot.donnees) {
    const fin = robot.donnees.temps.at(-1);
    robot.t = Math.min(robot.t + ((maintenant - horloge) / 1000) * Number($("vitesse-lecture").value), fin);
    poserRobot(robot.t);
    if (robot.t >= fin) arreterLecture();
  }
  horloge = maintenant;
  controles.update();
  rendu.render(scene, camera);
  requestAnimationFrame(boucle);
}

function vider(groupe) {
  for (const objet of [...groupe.children]) {
    groupe.remove(objet);
    objet.geometry?.dispose();
    objet.material?.dispose();
  }
}

// polyligne épaisse (épaisseur en mm, comme un cordon vu de dessus)
function trait(points, couleur, epaisseur, pointilles = false) {
  const geometrie = new LineGeometry();
  geometrie.setPositions(points.flatMap((p) => [p[0], p[1], p[2] ?? 0]));
  const materiau = new LineMaterial({
    color: couleur, linewidth: epaisseur, worldUnits: true,
    dashed: pointilles, dashSize: 12, gapSize: 8,
  });
  materiau.resolution.set(rendu.domElement.width, rendu.domElement.height);
  materiaux.push(materiau);
  const ligne = new Line2(geometrie, materiau);
  if (pointilles) ligne.computeLineDistances();
  return ligne;
}

function dessinerPalette(contour) {
  vider(groupePalette);
  const [lx, ly] = palette;
  // plateau de la palette (bois) et bâche
  const plateau = new THREE.Mesh(
    new THREE.BoxGeometry(lx, ly, 22),
    new THREE.MeshStandardMaterial({ color: "#c8a878", roughness: 0.9 }),
  );
  plateau.position.set(lx / 2, ly / 2, -13);     // dessus à -2 mm, sous la bâche
  const bache = new THREE.Mesh(
    new THREE.PlaneGeometry(lx, ly),
    new THREE.MeshStandardMaterial({ color: "#e9edf0", roughness: 1 }),
  );
  bache.position.set(lx / 2, ly / 2, -0.4);
  groupePalette.add(plateau, bache);
  groupePalette.add(trait(contour.map((p) => [p[0], p[1], 0.2]), "#1f2328", 1.5, true));
}

function dessinerTrame(resultat, exageration) {
  vider(groupeTrame);
  materiaux.length = 0;
  resultat.waves.forEach((serie, i) => {
    for (const vague of serie) {
      if (vague.length < 2) continue;
      const points = vague.map((p) => [p[0], p[1], p[2] * exageration + LARGEUR_CORDON / 4]);
      groupeTrame.add(trait(points, COULEURS[i % COULEURS.length], LARGEUR_CORDON));
    }
  });
  for (const saut of resultat.jumps) {
    groupeTrame.add(trait(saut.map((p) => [p[0], p[1], p[2] * exageration + 2]), "#000000", 2, true));
  }
  dessinerAlertes(resultat, exageration);
  redimensionner();
}

// les endroits signalés par les contrôles : anneaux et traits rouges, un peu au-dessus
function dessinerAlertes(resultat, exageration) {
  marquer(groupeAlertes, resultat.controles, exageration);
}

function marquer(groupe, liste, exageration) {
  vider(groupe);
  if (!$("montrer-alertes").checked) return;
  const rouge = "#e11d48";
  for (const c of liste) {
    if (c.statut === "ok") continue;
    for (const s of c.segments || []) {
      groupe.add(trait(s.map((p) => [p[0], p[1], (p[2] ?? 0) * exageration + 3]), rouge, 6));
    }
    for (const p of c.points) {
      const anneau = new THREE.Mesh(
        new THREE.RingGeometry(9, 13, 24),
        new THREE.MeshBasicMaterial({ color: rouge, side: THREE.DoubleSide }),
      );
      anneau.position.set(p[0], p[1], 4);
      groupe.add(anneau);
    }
  }
}

// ---------------------------------------------------------------------------
// Robot : bras UR10e animé le long du chemin
// ---------------------------------------------------------------------------

const robot = { modele: null, racine: null, donnees: null, lecture: false, t: Infinity, lignes: [] };

// charge le bras une fois (maillages officiels, quelques secondes)
async function chargerRobot() {
  try {
    // deux essais : une coupure réseau passagère ne doit pas priver la page du robot
    robot.modele = await creerRobot("robot/ur10e").catch(() => creerRobot("robot/ur10e"));
  } catch (erreur) {
    $("message-robot").textContent = "Le robot n'a pas pu être chargé (" + erreur.message + "). Recharge la page.";
    console.error(erreur);
    return;
  }
  // matériaux du bras (pour le teinter en rouge pendant une alerte)
  robot.materiaux = new Set();
  robot.modele.groupe.traverse((o) => {
    for (const m of [].concat(o.material || [])) robot.materiaux.add(m);
  });
  robot.racine = new THREE.Group();
  robot.racine.scale.setScalar(1000);          // le bras est en mètres, la scène en mm
  robot.racine.add(robot.modele.groupe);
  scene.add(robot.racine);
  calculerRobot();
}

// angles du bras le long du chemin (calcul Python) et cordon à déposer
function calculerRobot() {
  if (!robot.modele || !app || !dernierResultat) return;
  const d = JSON.parse(app.robot());
  if (d.erreur) { $("message-robot").textContent = d.erreur; return; }
  robot.donnees = d;
  repereCourant = d.repere;
  positionnerPalette();
  // le cordon du robot remplace la trame dessinée en attendant
  groupeTrame.visible = false;
  groupeCordon.visible = true;
  robot.modele.tool0.clear();
  robot.modele.tool0.add(creerBuse(d.tcp));

  // cordon : une ligne par série, sur la plage de points de cette série (sans approche/dégagement)
  vider(groupeCordon);
  robot.lignes = [];
  const exageration = Number($("exageration").value);
  let debut = 1, serie = d.series[1];
  for (let k = 2; k <= d.points.length - 1; k++) {
    if (k === d.points.length - 1 || d.series[k] !== serie) {
      const points = d.points.slice(debut, k).map((q) => [q[0], q[1], q[2] * exageration + LARGEUR_CORDON / 4]);
      if (points.length > 1) {
        const ligne = trait(points, COULEURS[serie % COULEURS.length], LARGEUR_CORDON);
        groupeCordon.add(ligne);
        robot.lignes.push({ ligne, debut, fin: k - 1 });
      }
      debut = k - 1;       // la série suivante repart du dernier point
      serie = d.series[k];
    }
  }
  // alertes robot : liste, marques rouges, points à signaler pendant l'animation
  const symbole = { ok: "✓", alerte: "⚠", erreur: "✕" };
  $("alertes-robot").innerHTML = d.alertes.map((a) => `
    <div class="controle ${a.statut}">
      <p><span class="symbole">${symbole[a.statut]}</span> ${a.titre}</p>
      ${a.statut === "ok" ? "" : `<p class="petit">${a.message}</p>`}
    </div>`).join("");
  marquer(groupeAlertesRobot, d.alertes, exageration);
  robot.enAlerte = new Set(d.alertes.filter((a) => a.statut !== "ok").flatMap((a) => a.indices));

  const fin = d.temps.at(-1);
  $("temps").max = fin;
  $("temps").step = fin / 1000;
  $("message-robot").textContent = d.simulation
    ? "Palette placée selon la calibration de simulation (pas encore relevée sur le robot)." : "";
  robot.t = Math.min(robot.t, fin);
  poserRobot(robot.t);
}

// place le bras au temps t (s) et montre le cordon déjà déposé
function poserRobot(t) {
  const d = robot.donnees;
  if (!d) return;
  const temps = d.temps;
  let bas = 0, haut = temps.length - 1;
  while (haut - bas > 1) { const m = (bas + haut) >> 1; if (temps[m] <= t) bas = m; else haut = m; }
  const u = temps[haut] > temps[bas] ? Math.min(Math.max((t - temps[bas]) / (temps[haut] - temps[bas]), 0), 1) : 0;
  const q0 = d.angles[bas], q1 = d.angles[haut];
  robot.modele.articulations.forEach((a, i) => (a.rotation.z = q0[i] + (q1[i] - q0[i]) * u));
  // bras teinté en rouge quand la pose actuelle déclenche une alerte
  const rouge = robot.enAlerte?.has(bas) && $("montrer-alertes").checked;
  for (const m of robot.materiaux) m.emissive?.set(rouge ? "#b00020" : "#000000");
  for (const { ligne, debut, fin } of robot.lignes) {
    ligne.geometry.instanceCount = Math.max(0, Math.min(bas, fin) - debut);
  }
  $("temps").value = t;
  const s = Math.round(t);
  $("valeur-temps").textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function arreterLecture() {
  robot.lecture = false;
  $("lecture").textContent = "▶ Lecture";
}

// texte toujours face à la caméra
function etiquette(texte, couleur, taille = 60) {
  const toile = document.createElement("canvas");
  const c = toile.getContext("2d");
  const police = "bold 40px system-ui, sans-serif";
  c.font = police;
  toile.width = Math.ceil(c.measureText(texte).width) + 16;   // support à la taille du texte
  toile.height = 64;
  c.font = police;
  c.fillStyle = couleur;
  c.textAlign = "center";
  c.textBaseline = "middle";
  c.fillText(texte, toile.width / 2, 32);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(toile), depthTest: false }));
  sprite.scale.set((taille * toile.width) / toile.height, taille, 1);
  return sprite;
}

// forme(s) plate(s) à la hauteur z : [[extérieur, trou…], …] en points (x, y)
function surfaces(formes, couleur, opacite, z) {
  const groupe = new THREE.Group();
  const materiau = new THREE.MeshBasicMaterial({
    color: couleur, transparent: true, opacity: opacite, depthWrite: false, side: THREE.DoubleSide });
  for (const [exterieur, ...trous] of formes) {
    const forme = new THREE.Shape(exterieur.map(([x, y]) => new THREE.Vector2(x, y)));
    for (const t of trous) forme.holes.push(new THREE.Path(t.map(([x, y]) => new THREE.Vector2(x, y))));
    const m = new THREE.Mesh(new THREE.ShapeGeometry(forme), materiau);
    m.position.z = z;
    groupe.add(m);
    for (const anneau of [exterieur, ...trous]) groupe.add(trait(anneau.map(([x, y]) => [x, y, z + 0.5]), couleur, 4));
  }
  return groupe;
}

// zone d'impression du robot (anneau vert), axes X/Y du robot, boussole (repère du robot)
function dessinerPortee(p) {
  vider(groupePortee);
  if (!p) return;
  const z = p.z - 30;   // sous la palette : elle cache la zone qu'elle recouvre
  groupePortee.add(surfaces(p.zone, "#16a34a", 0.09, z));

  // légende de l'anneau : où la buse peut imprimer
  const m = (v) => (v / 1000).toFixed(2).replace(".", ",");
  const texte = etiquette(`zone d'impression : ${m(p.rayon_int)} à ${m(p.rayon_ext)} m`, "#15803d", 70);
  // sur le côté de l'anneau (à 90° de la direction de la palette), pour ne pas la cacher
  const versPalette = new THREE.Vector2(paletteMobile.position.x, paletteMobile.position.y).normalize();
  texte.position.set(p.centre[0] + versPalette.y * p.rayon_ext, p.centre[1] - versPalette.x * p.rayon_ext, 40);
  $("legende-portee").textContent = `Anneau vert : zone où la buse peut imprimer, de ${m(p.rayon_int)} à ` +
    `${m(p.rayon_ext)} m d'un centre décalé de ${Math.round(Math.hypot(...p.centre) / 10)} cm par rapport au ` +
    `pied du robot (la buse est déportée sur le côté).`;
  groupePortee.add(texte);

  // axes du robot (comme sur le pendant) : X rouge, Y vert, 40 cm
  const fleche = (v, couleur, nom) => {
    groupePortee.add(new THREE.ArrowHelper(new THREE.Vector3(...v, 0), new THREE.Vector3(0, 0, 5), 400, couleur, 60, 35));
    const e = etiquette(nom, couleur, 90);
    e.position.set(v[0] * 560, v[1] * 560, 30);
    groupePortee.add(e);
  };
  fleche([1, 0], "#dc2626", "X robot");
  fleche([0, 1], "#16a34a", "Y robot");

  // boussole : N et S, au-delà de la zone d'impression
  const [nx, ny] = p.nord;
  const r = p.rayon_ext + Math.hypot(...p.centre) + 250;
  groupePortee.add(trait([[-nx * r, -ny * r, z + 1], [nx * r, ny * r, z + 1]], "#1f2328", 3, true));
  const n = etiquette("N", "#1f2328", 160);
  n.position.set(nx * (r + 60), ny * (r + 60), 30);
  const s = etiquette("S", "#6b7280", 120);
  s.position.set(-nx * (r + 60), -ny * (r + 60), 30);
  groupePortee.add(n, s);
}

// Placement de la palette : zone d'impression du robot, partie de la palette hors de portée.
// reglages = null : calibration en cours (simulation) ; sinon {x, y, z, rotation} du gizmo.
function placer(reglages) {
  if (!app) return;
  const r = JSON.parse(app.placement(reglages ? JSON.stringify(reglages) : ""));
  repereCourant = r.repere;
  positionnerPalette();
  dessinerPortee(r.portee);
  // partie de la palette hors de portée, en rouge, juste au-dessus de la bâche
  vider(groupeZone);
  groupeZone.add(surfaces(r.portee.hors_palette, "#e11d48", 0.35, r.portee.z + 1));
  groupeZone.visible = true;
  $("resultat-placement").textContent = `${r.atteignable} % de la palette est dans la zone d'impression.`;
  const c = r.calibration;
  $("calibration-placement").textContent = reglages
    ? `Palette déplacée. À recopier dans config/cellule.toml, [calibration_simulation] :\n` +
      `origine = [${c.origine.join(", ")}]\ngrand_cote = [${c.grand_cote.join(", ")}]\npetit_cote = [${c.petit_cote.join(", ")}]`
    : "";
  calculerRobot();
}

// fin d'un déplacement au gizmo : position du coin (0, 0) et rotation -> placement
function placerDepuisGizmo() {
  const [lx, ly] = palette;
  const rotation = Math.round(THREE.MathUtils.radToDeg(new THREE.Euler().setFromQuaternion(paletteMobile.quaternion).z));
  const coin = new THREE.Vector3(-lx / 2, -ly / 2, 0).applyQuaternion(paletteMobile.quaternion).add(paletteMobile.position);
  placer({ x: Math.round(coin.x), y: Math.round(coin.y), z: Math.round(repereCourant.origine[2] * 10) / 10, rotation });
}

// un clic sur la palette montre le gizmo ; un clic ailleurs le cache
const rayon = new THREE.Raycaster();
let appui = null;
function selectionner(e) {
  if (!appui || Math.hypot(e.clientX - appui[0], e.clientY - appui[1]) > 5) return;   // c'était un glisser
  if (gizmos.some((g) => g.dragging || g.axis)) return;                                // clic sur le gizmo
  const cadre = rendu.domElement.getBoundingClientRect();
  const souris = new THREE.Vector2(((e.clientX - cadre.left) / cadre.width) * 2 - 1,
                                   -((e.clientY - cadre.top) / cadre.height) * 2 + 1);
  rayon.setFromCamera(souris, camera);
  const surPalette = rayon.intersectObjects(groupePalette.children, true).length > 0;
  for (const g of gizmos) {
    if (surPalette) g.attach(paletteMobile); else g.detach();
  }
}

// ---------------------------------------------------------------------------
// Panneau : curseurs, choix du motif et du contour
// ---------------------------------------------------------------------------

let app = null;
let motifs = [];
let contour = null; // { nom, texte }
let dernierResultat = null;
let dejaCadre = false; // la vue 3D est cadrée au premier calcul seulement
const reglages = { motif: {}, moteur: {} };

function curseur(conteneur, nom, p, cible) {
  const bloc = document.createElement("div");
  bloc.className = "reglage";
  const unite = p.unite ? " " + p.unite : "";
  bloc.innerHTML = `
    <div class="ligne"><span>${nom.replaceAll("_", " ")}</span><output></output></div>
    <input type="range" min="${p.mini}" max="${p.maxi}" step="${p.pas}" value="${p.valeur}">
    <p class="aide">${p.aide}</p>`;
  const entree = bloc.querySelector("input");
  const sortie = bloc.querySelector("output");
  const afficher = () => (sortie.textContent = entree.value + unite);
  afficher();
  cible[nom] = Number(p.valeur);
  entree.addEventListener("input", afficher);
  // on recalcule quand on relâche le curseur
  entree.addEventListener("change", () => {
    cible[nom] = Number(entree.value);
    calculer();
  });
  conteneur.appendChild(bloc);
}

// petit convertisseur Markdown -> HTML (titres, listes, gras, code)
function markdown(texte) {
  const enLigne = (t) => t
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`(.+?)`/g, "<code>$1</code>");
  let html = "", liste = null;
  const fermer = () => { if (liste) { html += `</${liste}>`; liste = null; } };
  for (const ligne of texte.split("\n")) {
    let m;
    if ((m = ligne.match(/^(#{1,3}) (.*)/))) { fermer(); html += `<h${m[1].length + 2}>${enLigne(m[2])}</h${m[1].length + 2}>`; }
    else if ((m = ligne.match(/^\s*(-|\d+\.) (.*)/))) {
      const type = m[1] === "-" ? "ul" : "ol";
      if (liste !== type) { fermer(); html += `<${type}>`; liste = type; }
      html += `<li>${enLigne(m[2])}</li>`;
    } else if (ligne.trim() === "") { fermer(); }
    else if (liste) { html = html.replace(/<\/li>$/, " " + enLigne(ligne.trim()) + "</li>"); }
    else { html += `<p>${enLigne(ligne)}</p>`; }
  }
  fermer();
  return html;
}

function choisirMotif(id) {
  const motif = motifs.find((m) => m.id === id);
  const conteneur = $("reglages-motif");
  conteneur.innerHTML = "";
  reglages.motif = {};
  if (motif.erreur) conteneur.innerHTML = `<p class="erreur">${motif.erreur}</p>`;
  for (const [nom, p] of Object.entries(motif.parametres)) curseur(conteneur, nom, p, reglages.motif);
  $("aide-motif").hidden = !motif.aide;
  $("aide-motif").querySelector("div").innerHTML = markdown(motif.aide);
}

function afficherBilan(r) {
  const minutes = r.duree != null ? Math.round(r.duree / 60) : "?";
  const symbole = { ok: "✓", alerte: "⚠", erreur: "✕" };
  const provisoire = (nom) => r.provisoires.includes(nom) ? " (provisoire)" : "";
  $("bilan").innerHTML = `
    <p>Longueur de cordon : <strong>${(r.longueur / 1000).toFixed(1)} m</strong></p>
    <p>Durée d'impression : environ <strong>${minutes} min</strong></p>
    <p>Béton : environ <strong>${r.volume} L</strong></p>
    ${r.controles.map((c) => `
      <div class="controle ${c.statut}">
        <p><span class="symbole">${symbole[c.statut]}</span> ${c.titre}</p>
        ${c.statut === "ok" ? "" : `<p class="petit">${c.message}</p>`}
      </div>`).join("")}
    <p class="petit">Cordon de ${r.beton.largeur_cordon} mm${provisoire("largeur_cordon")},
      virage le plus serré ${r.beton.rayon_courbure_min} mm${provisoire("rayon_courbure_min")}.
      Les valeurs provisoires seront fixées pendant les essais.</p>`;
  $("info").textContent = r.info;
  $("message-contour").textContent = r.message_contour;
  $("legende").innerHTML = r.waves.map((_, i) => {
    const role = i === 0 ? "imprimée en premier" : `passe par-dessus ${NOMS_SERIES.slice(0, i).join(", ")}`;
    return `<div><span class="pastille" style="background:${COULEURS[i % COULEURS.length]}"></span>Série ${NOMS_SERIES[i]} : ${role}</div>`;
  }).join("");
}

function calculer() {
  if (!app || !contour) return;
  etat.textContent = "Calcul…";
  // on laisse le navigateur afficher « Calcul… » avant de bloquer pendant le calcul
  setTimeout(() => {
    const debut = performance.now();
    const r = JSON.parse(app.calculer($("choix-motif").value, JSON.stringify(reglages),
                                      contour.texte, contour.nom));
    if (r.erreur) {
      etat.textContent = "";
      $("bilan").innerHTML = `<p class="erreur">${r.erreur}</p>`;
      $("info").textContent = r.details || "";
      return;
    }
    dernierResultat = r;
    palette = r.palette;
    positionnerPalette();
    dessinerPalette(r.contour);
    dessinerTrame(r, Number($("exageration").value));
    afficherBilan(r);
    if (!dejaCadre) { placer(null); vue3d(); dejaCadre = true; }
    // la nouvelle trame tout de suite ; le robot (plus long) juste après
    groupeTrame.visible = true;
    groupeCordon.visible = false;
    etat.textContent = "";
    setTimeout(calculerRobot, 30);
    console.log(`calcul : ${((performance.now() - debut) / 1000).toFixed(2)} s`);
  }, 20);
}

// télécharge le fichier DXF ou SVG du dernier calcul
function telecharger(format) {
  if (!app) return;
  const r = JSON.parse(app.exporter(format));
  if (r.erreur) { alert(r.erreur); return; }
  const type = { svg: "image/svg+xml", dxf: "application/dxf", script: "text/plain" }[format];
  const lien = document.createElement("a");
  lien.href = URL.createObjectURL(new Blob([r.texte], { type }));
  lien.download = r.nom;
  lien.click();
  URL.revokeObjectURL(lien.href);
}

async function lireTexte(chemin) {
  const reponse = await fetch("../" + chemin);
  if (!reponse.ok) throw new Error(`Fichier introuvable : ${chemin}`);
  return reponse.text();
}

// ---------------------------------------------------------------------------
// Démarrage
// ---------------------------------------------------------------------------

async function demarrer() {
  redimensionner();
  window.addEventListener("resize", redimensionner);
  boucle();
  $("vue-dessus").onclick = vueDessus;
  $("vue-3d").onclick = vue3d;
  $("lecture").onclick = () => {
    if (!robot.donnees) return;
    if (robot.lecture) { arreterLecture(); return; }
    if (robot.t >= robot.donnees.temps.at(-1)) robot.t = 0;
    robot.lecture = true;
    $("lecture").textContent = "⏸ Pause";
  };
  $("temps").addEventListener("input", (e) => { arreterLecture(); robot.t = Number(e.target.value); poserRobot(robot.t); });
  // pendant qu'on tire un gizmo, la vue ne tourne pas ; au lâcher, tout est recalculé
  for (const g of gizmos) {
    g.addEventListener("dragging-changed", (e) => {
      controles.enabled = !e.value;
      if (e.value) groupeZone.visible = false;
      else placerDepuisGizmo();
    });
  }
  rendu.domElement.addEventListener("pointerdown", (e) => (appui = [e.clientX, e.clientY]));
  rendu.domElement.addEventListener("pointerup", selectionner);
  $("export-dxf").onclick = () => telecharger("dxf");
  $("export-svg").onclick = () => telecharger("svg");
  $("export-script").onclick = () => telecharger("script");
  $("montrer-alertes").addEventListener("change", () => {
    if (dernierResultat) dessinerAlertes(dernierResultat, Number($("exageration").value));
    if (robot.donnees) marquer(groupeAlertesRobot, robot.donnees.alertes, Number($("exageration").value));
  });
  $("exageration").addEventListener("input", (e) => {
    $("valeur-exageration").textContent = "× " + e.target.value;
    if (dernierResultat) dessinerTrame(dernierResultat, Number(e.target.value));
    if (robot.donnees) calculerRobot();
  });

  try {
    const { loadPyodide } = await import(URL_PYODIDE + "pyodide.mjs");
    const pyodide = await loadPyodide({ indexURL: URL_PYODIDE });
    const pret = await preparer(pyodide, lireTexte, (m) => (etat.textContent = m));
    app = pret.app;

    // motifs
    motifs = JSON.parse(app.liste_motifs());
    $("choix-motif").innerHTML = motifs.map((m) => `<option value="${m.id}">${m.nom}</option>`).join("");
    $("choix-motif").onchange = (e) => { choisirMotif(e.target.value); calculer(); };
    choisirMotif(motifs[0].id);

    // réglages du moteur
    for (const [nom, p] of Object.entries(JSON.parse(app.reglages_moteur()))) {
      curseur($("reglages-moteur"), nom, p, reglages.moteur);
    }

    // contours exemples
    const exemples = pret.fichiers.filter((f) => f.startsWith("contours/"));
    $("choix-contour").innerHTML = exemples
      .map((f) => `<option value="${f}">${f.replace("contours/", "")}</option>`).join("");
    const parDefaut = exemples.find((f) => f.includes("haricot")) || exemples[0];
    $("choix-contour").value = parDefaut;
    const choisirExemple = async (chemin) => {
      contour = { nom: chemin.split("/").pop(), texte: await lireTexte(chemin) };
      calculer();
    };
    $("choix-contour").onchange = (e) => {
      if (e.target.value !== "importe") choisirExemple(e.target.value);
    };
    $("fichier-contour").onchange = async (e) => {
      const fichier = e.target.files[0];
      if (!fichier) return;
      contour = { nom: fichier.name, texte: await fichier.text() };
      $("choix-contour").querySelector('option[value="importe"]')?.remove();
      const option = new Option("importé : " + fichier.name, "importe", true, true);
      $("choix-contour").add(option);
      calculer();
    };
    await choisirExemple(parDefaut);
    chargerRobot();
  } catch (erreur) {
    etat.innerHTML = `<span class="erreur">Erreur : ${erreur.message}</span>`;
    console.error(erreur);
  }
}

demarrer();
