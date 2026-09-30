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
import { preparer, URL_PYODIDE } from "./pyodide_trame.mjs?v=d75181303827";
import { creerBuse, creerRobot } from "./robot.js?v=d75181303827";

// une couleur par série, dans l'ordre d'impression
// noir, orange, orange brûlé, orange clair, gris : le rouge est gardé pour les problèmes
const COULEURS = ["#111111", "#f97316", "#9a3412", "#fdba74", "#737373"];
const NOMS_SERIES = ["A", "B", "C", "D", "E"];
const LARGEUR_CORDON = 4; // mm, pour le dessin seulement

const $ = (id) => document.getElementById(id);
const etat = $("etat");

// ---------------------------------------------------------------------------
// Scène three.js
// ---------------------------------------------------------------------------

THREE.Object3D.DEFAULT_UP.set(0, 0, 1);
const scene = new THREE.Scene();
scene.background = new THREE.Color("#ffffff");
const camera = new THREE.PerspectiveCamera(35, 1, 1, 20000);
const rendu = new THREE.WebGLRenderer({ antialias: true });
rendu.setPixelRatio(window.devicePixelRatio);
$("scene").appendChild(rendu.domElement);
const controles = new OrbitControls(camera, rendu.domElement);

scene.add(new THREE.HemisphereLight("#ffffff", "#d6d3d1", 2.5));
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
const groupePoints = new THREE.Group();  // poignées des paramètres « Point » du motif
contenuPalette.add(groupePalette, groupeTrame, groupeAlertes, groupeCordon, groupeAlertesRobot, groupePoints);
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
    new THREE.MeshStandardMaterial({ color: "#fdba74", roughness: 0.9 }),
  );
  plateau.position.set(lx / 2, ly / 2, -13);     // dessus à -2 mm, sous la bâche
  const bache = new THREE.Mesh(
    new THREE.PlaneGeometry(lx, ly),
    new THREE.MeshStandardMaterial({ color: "#fafaf9", roughness: 1 }),
  );
  bache.position.set(lx / 2, ly / 2, -0.4);
  groupePalette.add(plateau, bache);
  groupePalette.add(trait(contour.map((p) => [p[0], p[1], 0.2]), "#111111", 1.5, true));
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
    robot.modele = await creerRobot("robot/ur10e");
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
  robot.racine.visible = avecRobot();
  scene.add(robot.racine);
  calculerRobot();
}

// angles du bras le long du chemin (calcul Python) et cordon à déposer
function calculerRobot() {
  if (!avecRobot() || !robot.modele || !app || !dernierResultat) return;
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
  // si l'animation était à la fin (ou pas lancée), on montre la nouvelle trame entière
  if (!robot.lecture && (robot.finPrecedente === undefined || robot.t >= robot.finPrecedente)) robot.t = fin;
  robot.t = Math.min(robot.t, fin);
  robot.finPrecedente = fin;
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
  const police = "700 40px 'Bricolage Grotesque', system-ui, sans-serif";
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
  groupePortee.add(surfaces(p.zone, "#f97316", 0.10, z));

  // légende de l'anneau : où la buse peut imprimer
  const m = (v) => (v / 1000).toFixed(2).replace(".", ",");
  const texte = etiquette(`zone d'impression : ${m(p.rayon_int)} à ${m(p.rayon_ext)} m`, "#c2410c", 42);
  // sur le côté de l'anneau (à 90° de la direction de la palette), pour ne pas la cacher
  const versPalette = new THREE.Vector2(paletteMobile.position.x, paletteMobile.position.y).normalize();
  texte.position.set(p.centre[0] + versPalette.y * p.rayon_ext, p.centre[1] - versPalette.x * p.rayon_ext, 40);
  $("legende-portee").textContent = `Anneau orange : zone où la buse peut imprimer, de ${m(p.rayon_int)} à ` +
    `${m(p.rayon_ext)} m d'un centre décalé de ${Math.round(Math.hypot(...p.centre) / 10)} cm par rapport au ` +
    `pied du robot (la buse est déportée sur le côté).`;
  groupePortee.add(texte);

  // axes du robot (comme sur le pendant) : X rouge, Y vert, 40 cm
  const fleche = (v, couleur, nom) => {
    groupePortee.add(new THREE.ArrowHelper(new THREE.Vector3(...v, 0), new THREE.Vector3(0, 0, 5), 400, couleur, 60, 35));
    const e = etiquette(nom, couleur, 54);
    e.position.set(v[0] * 560, v[1] * 560, 30);
    groupePortee.add(e);
  };
  fleche([1, 0], "#111111", "X robot");
  fleche([0, 1], "#f97316", "Y robot");

  // boussole : N et S, au-delà de la zone d'impression
  const [nx, ny] = p.nord;
  const r = p.rayon_ext + Math.hypot(...p.centre) + 250;
  groupePortee.add(trait([[-nx * r, -ny * r, z + 1], [nx * r, ny * r, z + 1]], "#111111", 3, true));
  const n = etiquette("N", "#111111", 96);
  n.position.set(nx * (r + 60), ny * (r + 60), 30);
  const s = etiquette("S", "#737373", 72);
  s.position.set(-nx * (r + 60), -ny * (r + 60), 30);
  groupePortee.add(n, s);
}

// Placement de la palette : zone d'impression du robot, partie de la palette hors de portée.
// reglages = null : calibration en cours (simulation) ; sinon {x, y, z, rotation} du gizmo.
function placer(reglages) {
  if (!app || !avecRobot()) return;
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

// maquette G-code : rapport d'échelle et taille, d'après la largeur du cordon d'essai
function majMaquette() {
  if (!app || !dernierResultat) return;
  const m = JSON.parse(app.maquette(Number($("largeur-essai").value)));
  $("info-maquette").textContent = m.erreur ? m.erreur
    : `Échelle 1:${String(m.rapport).replace(".", ",")} : trame de ${m.taille[0]} × ${m.taille[1]} mm, ` +
      `couche de ${String(m.hauteur_couche).replace(".", ",")} mm. Vitesse automatique ` +
      `${String(m.vitesse).replace(".", ",")} mm/s (d'après le débit de l'extrudeur), ` +
      `environ ${Math.max(1, Math.round(m.duree / 60))} min.` +
      (m.tient ? "" : " ⚠ Trop grand pour le plateau de 700 × 700 : prends un cordon d'essai plus fin.");
  $("export-gcode").disabled = !!m.erreur || !m.tient;
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
  // une poignée de point : seulement les flèches (un point ne se tourne pas)
  const poignee = poigneeSous(e);
  if (poignee) {
    gizmoTourner.detach();
    gizmoDeplacer.attach(poignee);
    pointSelectionne = { nom: poignee.userData.nomParametre, index: poignee.userData.index };
    return;
  }
  pointSelectionne = null;
  const surPalette = avecRobot() && rayon.intersectObjects(groupePalette.children, true).length > 0;
  for (const g of gizmos) {
    if (surPalette) g.attach(paletteMobile); else g.detach();
  }
}

// Points des motifs (paramètres « Point » et « Points ») : des poignées orange sur la palette.
// Clic : déplacer (flèches) ; double-clic sur la palette : ajouter ; double-clic sur un point
// ou touche Suppr : supprimer.
let pointSelectionne = null;   // { nom, index } de la poignée sélectionnée

// rayon souris -> scène, pour un événement de la souris
function viser(e) {
  const cadre = rendu.domElement.getBoundingClientRect();
  rayon.setFromCamera(new THREE.Vector2(((e.clientX - cadre.left) / cadre.width) * 2 - 1,
                                        -((e.clientY - cadre.top) / cadre.height) * 2 + 1), camera);
}

// la poignée sous la souris, s'il y en a une
function poigneeSous(e) {
  viser(e);
  const touche = rayon.intersectObjects(groupePoints.children, true)[0];
  if (!touche) return null;
  let poignee = touche.object;
  while (!poignee.userData.nomParametre) poignee = poignee.parent;
  return poignee;
}

function creerPoignee(nom, index, [x, y]) {
  const poignee = new THREE.Group();
  poignee.position.set(x, y, 0);
  poignee.userData = { nomParametre: nom, index };
  // toujours au premier plan : visible même sous le bras du robot
  const boule = new THREE.Mesh(new THREE.SphereGeometry(26, 24, 16),
                               new THREE.MeshBasicMaterial({ color: "#111111", depthTest: false }));
  boule.position.z = 26;
  boule.renderOrder = 10;
  const cerne = new THREE.Mesh(new THREE.RingGeometry(26, 32, 32),
                               new THREE.MeshBasicMaterial({ color: "#f97316", depthTest: false }));
  cerne.position.z = 26;
  cerne.renderOrder = 9;
  poignee.add(cerne);
  const texte = nom.replaceAll("_", " ") + (index === null ? "" : " " + (index + 1));
  const nomAffiche = etiquette(texte, "#111111", 24);
  nomAffiche.position.z = 70;
  poignee.add(boule, nomAffiche);
  return poignee;
}

// (re)dessine toutes les poignées à partir des réglages ; garde la sélection
function dessinerPoints() {
  vider(groupePoints);
  if (gizmoDeplacer.object?.userData.nomParametre) gizmoDeplacer.detach();
  for (const [nom, p] of Object.entries(motifCourant?.parametres || {})) {
    if (p.type === "point") groupePoints.add(creerPoignee(nom, null, reglages.motif[nom]));
    if (p.type === "points") reglages.motif[nom].forEach((xy, i) => groupePoints.add(creerPoignee(nom, i, xy)));
    majTextePoints(nom);
  }
  const choisie = pointSelectionne && groupePoints.children.find((g) =>
    g.userData.nomParametre === pointSelectionne.nom && g.userData.index === pointSelectionne.index);
  if (choisie) { gizmoTourner.detach(); gizmoDeplacer.attach(choisie); }
}

function majTextePoints(nom) {
  const sortie = document.querySelector(`[data-point="${nom}"] output`);
  const v = reglages.motif[nom];
  if (!sortie) return;
  sortie.textContent = motifCourant.parametres[nom].type === "point"
    ? `${Math.round(v[0])}, ${Math.round(v[1])} mm` : `${v.length} point${v.length > 1 ? "s" : ""}`;
}

// fin du déplacement d'une poignée : nouvelle position (sur la palette), puis recalcul
function deplacerPoint(poignee) {
  const [lx, ly] = palette;
  const x = Math.round(Math.min(Math.max(poignee.position.x, 0), lx));
  const y = Math.round(Math.min(Math.max(poignee.position.y, 0), ly));
  poignee.position.set(x, y, 0);
  const { nomParametre: nom, index } = poignee.userData;
  if (index === null) reglages.motif[nom] = [x, y];
  else reglages.motif[nom][index] = [x, y];
  majTextePoints(nom);
  calculer();
}

// double-clic : sur un point de liste -> le supprimer ; sur la palette -> ajouter un point
function doubleClic(e) {
  const poignee = poigneeSous(e);
  if (poignee) { supprimerPoint(poignee); return; }
  const nom = Object.keys(motifCourant?.parametres || {}).find((n) => motifCourant.parametres[n].type === "points");
  if (!nom) return;
  viser(e);
  const touche = rayon.intersectObjects(groupePalette.children, true)[0];
  if (!touche) return;
  const p = motifCourant.parametres[nom];
  if (reglages.motif[nom].length >= p.maxi) {
    etat.textContent = `Pas plus de ${p.maxi} points pour ce motif.`;
    setTimeout(() => (etat.textContent = ""), 2500);
    return;
  }
  const local = contenuPalette.worldToLocal(touche.point.clone());
  reglages.motif[nom].push([Math.round(local.x), Math.round(local.y)]);
  pointSelectionne = { nom, index: reglages.motif[nom].length - 1 };
  dessinerPoints();
  calculer();
}

function supprimerPoint(poignee) {
  const { nomParametre: nom, index } = poignee.userData;
  const p = motifCourant.parametres[nom];
  if (index === null) return;                          // un « Point » seul ne se supprime pas
  if (reglages.motif[nom].length <= p.mini) {
    etat.textContent = `Il faut garder au moins ${p.mini} point${p.mini > 1 ? "s" : ""}.`;
    setTimeout(() => (etat.textContent = ""), 2500);
    return;
  }
  reglages.motif[nom].splice(index, 1);
  pointSelectionne = null;
  dessinerPoints();
  calculer();
}

// ---------------------------------------------------------------------------
// Panneau : curseurs, choix du motif et du contour
// ---------------------------------------------------------------------------

let app = null;
const avecRobot = () => true;   // l'aperçu est toujours en vraie grandeur, avec le bras
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

// paramètres « Point » et « Points » : une ligne dans le panneau, des poignées sur la palette
function point(conteneur, nom, p) {
  reglages.motif[nom] = p.type === "point" ? [...p.valeur] : p.valeur.map((xy) => [...xy]);
  const bloc = document.createElement("div");
  bloc.className = "reglage";
  bloc.dataset.point = nom;
  const geste = p.type === "point"
    ? "Clique sur la boule noire pour la déplacer."
    : `Double-clic sur la palette : ajouter un point (${p.maxi} au plus). Clic sur un point : le déplacer. ` +
      `Double-clic sur un point : le supprimer.`;
  bloc.innerHTML = `
    <div class="ligne"><span><span class="pastille-point"></span>${nom.replaceAll("_", " ")}</span><output></output></div>
    <p class="aide">${p.aide} ${geste}</p>`;
  conteneur.appendChild(bloc);
}

// paramètre « Liste » : des éléments que l'on ajoute (« + Ajouter ») ou retire (« × ») ;
// chaque élément a un curseur, ou plusieurs côte à côte s'il a des « champs »
const LETTRES = "ABCDEFGHIJ";

// valeur la plus éloignée de celles qui existent (angles : circulaires sur 180° ou 360°)
function plusEloignee(existantes, bas, haut, pas) {
  const circulaire = haut - bas === 180 || haut - bas === 360;
  const ecart = (a, b) => circulaire ? Math.min(Math.abs(a - b), haut - bas - Math.abs(a - b)) : Math.abs(a - b);
  let meilleur = bas, plusLoin = -1;
  for (let x = bas; x <= haut; x += pas) {
    const d = existantes.length ? Math.min(...existantes.map((y) => ecart(x, y))) : 0;
    if (d > plusLoin) { plusLoin = d; meilleur = x; }
  }
  return Math.round(meilleur / pas) * pas;
}

function liste(conteneur, nom, p) {
  reglages.motif[nom] = p.valeur.map((x) => (typeof x === "object" ? { ...x } : x));
  const bloc = document.createElement("div");
  bloc.className = "reglage liste";
  conteneur.appendChild(bloc);

  // un curseur compact : libellé, valeur, glissière
  const petitCurseur = (libelle, valeur, q, changer) => {
    const unite = q.unite ? " " + q.unite : "";
    const zone = document.createElement("label");
    zone.className = "champ";
    zone.title = q.aide || "";
    zone.innerHTML = `<span class="ligne"><span>${libelle}</span><output>${valeur}${unite}</output></span>
      <input type="range" min="${q.mini}" max="${q.maxi}" step="${q.pas}" value="${valeur}">`;
    const entree = zone.querySelector("input");
    entree.addEventListener("input", () => (zone.querySelector("output").textContent = entree.value + unite));
    entree.addEventListener("change", () => changer(Number(entree.value)));
    return zone;
  };

  const dessiner = () => {
    const v = reglages.motif[nom];
    const titre = p.element ? p.element + "s" : nom.replaceAll("_", " ");   // « Série » -> « Séries »
    bloc.innerHTML = `<div class="ligne"><span>${titre}</span><output>${v.length}</output></div>
      <p class="aide">${p.aide}</p>`;
    v.forEach((x, i) => {
      const titre = p.element ? `${p.element} ${LETTRES[i] ?? i + 1}` : `${i + 1}`;
      const ligne = document.createElement("div");
      ligne.className = "element";
      ligne.innerHTML = `<div class="titre-element"><span>${titre}</span>
        ${v.length > p.mini ? `<button type="button" class="retirer" title="Retirer">×</button>` : ""}</div>
        <div class="champs"></div>`;
      const champs = ligne.querySelector(".champs");
      if (p.champs) {
        for (const [cle, q] of Object.entries(p.champs)) {
          champs.appendChild(petitCurseur(cle.replaceAll("_", " "), x[cle], q, (val) => { x[cle] = val; calculer(); }));
        }
      } else {
        const q = { mini: p.bornes[0], maxi: p.bornes[1], pas: p.pas, unite: p.unite };
        champs.appendChild(petitCurseur("valeur", x, q, (val) => { v[i] = val; calculer(); }));
      }
      ligne.querySelector(".retirer")?.addEventListener("click", () => { v.splice(i, 1); dessiner(); calculer(); });
      bloc.appendChild(ligne);
    });
    if (v.length < p.maxi) {
      const ajouter = document.createElement("button");
      ajouter.type = "button";
      ajouter.className = "ajouter";
      ajouter.textContent = `+ Ajouter ${p.element ? "une " + p.element.toLowerCase() : "un élément"}`;
      ajouter.addEventListener("click", () => {
        // un angle prend la direction la plus ouverte ; les autres réglages copient le dernier élément
        if (p.champs) {
          const nouveau = {};
          for (const [cle, q] of Object.entries(p.champs)) {
            const circulaire = q.maxi - q.mini === 180 || q.maxi - q.mini === 360;
            nouveau[cle] = circulaire ? plusEloignee(v.map((e) => e[cle]), q.mini, q.maxi, q.pas)
                                      : (v.at(-1)?.[cle] ?? q.valeur);
          }
          v.push(nouveau);
        } else {
          v.push(plusEloignee(v, p.bornes[0], p.bornes[1], p.pas));
        }
        dessiner();
        calculer();
      });
      bloc.appendChild(ajouter);
    }
  };
  dessiner();
}

// paramètre « Choix » : une liste déroulante
function choix(conteneur, nom, p) {
  reglages.motif[nom] = p.valeur;
  const bloc = document.createElement("div");
  bloc.className = "reglage";
  bloc.innerHTML = `
    <div class="ligne"><span>${nom.replaceAll("_", " ")}</span></div>
    <select>${p.options.map((o) => `<option${o === p.valeur ? " selected" : ""}>${o}</option>`).join("")}</select>
    <p class="aide">${p.aide}</p>`;
  bloc.querySelector("select").addEventListener("change", (e) => { reglages.motif[nom] = e.target.value; calculer(); });
  conteneur.appendChild(bloc);
}

// paramètre « Case » : oui / non
function caseACocher(conteneur, nom, p) {
  reglages.motif[nom] = p.valeur;
  const bloc = document.createElement("div");
  bloc.className = "reglage";
  bloc.innerHTML = `
    <label class="case"><input type="checkbox"${p.valeur ? " checked" : ""}> ${nom.replaceAll("_", " ")}</label>
    <p class="aide">${p.aide}</p>`;
  bloc.querySelector("input").addEventListener("change", (e) => { reglages.motif[nom] = e.target.checked; calculer(); });
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

let motifCourant = null;

function choisirMotif(id) {
  const motif = motifs.find((m) => m.id === id);
  motifCourant = motif;
  pointSelectionne = null;
  const conteneur = $("reglages-motif");
  conteneur.innerHTML = "";
  reglages.motif = {};
  if (motif.erreur) conteneur.innerHTML = `<p class="erreur">${motif.erreur}</p>`;
  for (const [nom, p] of Object.entries(motif.parametres)) {
    if (p.type === "point" || p.type === "points") point(conteneur, nom, p);
    else if (p.type === "choix") choix(conteneur, nom, p);
    else if (p.type === "case") caseACocher(conteneur, nom, p);
    else if (p.type === "liste") liste(conteneur, nom, p);
    else curseur(conteneur, nom, p, reglages.motif);
  }
  dessinerPoints();
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
    // points du motif ramenés sur le plateau par le calcul : les poignées suivent
    let pointsBouges = false;
    for (const [nom, v] of Object.entries(r.points_motif || {})) {
      if (JSON.stringify(v) !== JSON.stringify(reglages.motif[nom])) { reglages.motif[nom] = v; pointsBouges = true; }
    }
    if (pointsBouges) dessinerPoints();
    positionnerPalette();
    dessinerPalette(r.contour);
    dessinerTrame(r, Number($("exageration").value));
    afficherBilan(r);
    majMaquette();
    // curseur Taille : la part du maximum réellement utilisée, et la taille en mm
    $("taille").value = Math.round(r.taille * 100);
    $("valeur-taille").textContent = `${Math.round(r.taille * 100)} % : ${r.dimensions[0]} × ${r.dimensions[1]} mm`;
    if (!$("vitesse-robot").value) $("vitesse-robot").value = r.vitesse;
    if (!dejaCadre) { if (avecRobot()) placer(null); vue3d(); dejaCadre = true; }
    // la nouvelle trame tout de suite ; le robot (plus long) juste après
    groupeTrame.visible = true;
    groupeCordon.visible = false;
    etat.textContent = "";
    if (avecRobot()) setTimeout(calculerRobot, 30);
    console.log(`calcul : ${((performance.now() - debut) / 1000).toFixed(2)} s`);
  }, 20);
}

// télécharge le fichier DXF ou SVG du dernier calcul
function telecharger(format) {
  if (!app) return;
  const options = format === "gcode" ? { largeur_essai: Number($("largeur-essai").value) } : {};
  const r = JSON.parse(app.exporter(format, JSON.stringify(options)));
  if (r.erreur) { alert(r.erreur); return; }
  const type = { svg: "image/svg+xml", dxf: "application/dxf", script: "text/plain", gcode: "text/plain" }[format];
  const lien = document.createElement("a");
  lien.href = URL.createObjectURL(new Blob([r.texte], { type }));
  lien.download = r.nom;
  lien.click();
  URL.revokeObjectURL(lien.href);
}

async function lireTexte(chemin) {
  // « no-cache » : on redemande toujours au serveur si le fichier a changé (après une mise à jour)
  const reponse = await fetch("../" + chemin, { cache: "no-cache" });
  if (!reponse.ok) throw new Error(`Fichier introuvable : ${chemin}`);
  return reponse.text();
}

// ---------------------------------------------------------------------------
// Démarrage
// ---------------------------------------------------------------------------

// panneau flottant : on le déplace en le tenant par son titre (il reste dans la fenêtre)
function panneauDeplacable() {
  const panneau = $("panneau");
  let depart = null;
  $("entete-panneau").addEventListener("pointerdown", (e) => {
    depart = [e.clientX, e.clientY, panneau.offsetLeft, panneau.offsetTop];
    e.target.setPointerCapture(e.pointerId);
  });
  $("entete-panneau").addEventListener("pointermove", (e) => {
    if (!depart) return;
    const x = Math.min(Math.max(depart[2] + e.clientX - depart[0], 0), window.innerWidth - 60);
    const y = Math.min(Math.max(depart[3] + e.clientY - depart[1], 0), window.innerHeight - 40);
    panneau.style.left = x + "px";
    panneau.style.top = y + "px";
  });
  $("entete-panneau").addEventListener("pointerup", () => (depart = null));
}

async function demarrer() {
  panneauDeplacable();
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
      const objet = g.object;
      if (objet?.userData.nomParametre) {       // une poignée de point
        if (!e.value) deplacerPoint(objet);
        return;
      }
      if (e.value) groupeZone.visible = false;
      else placerDepuisGizmo();
    });
  }
  // un seul gizmo à la fois : au moment d'appuyer (avant les gizmos, phase de capture),
  // les flèches et le carré ont priorité ; l'anneau ne tourne que si l'on est seulement sur lui
  $("scene").addEventListener("pointerdown", () => {
    if (gizmoDeplacer.axis) gizmoTourner.enabled = false;
    else if (gizmoTourner.axis) gizmoDeplacer.enabled = false;
  }, true);
  window.addEventListener("pointerup", () => setTimeout(() => { for (const g of gizmos) g.enabled = true; }, 0));
  rendu.domElement.addEventListener("pointerdown", (e) => (appui = [e.clientX, e.clientY]));
  rendu.domElement.addEventListener("pointerup", selectionner);
  rendu.domElement.addEventListener("dblclick", doubleClic);
  window.addEventListener("keydown", (e) => {
    if ((e.key === "Delete" || e.key === "Backspace") && !e.target.closest?.("input, select, textarea")) {
      const poignee = gizmoDeplacer.object;
      if (poignee?.userData.nomParametre) supprimerPoint(poignee);
    }
  });
  $("export-dxf").onclick = () => telecharger("dxf");
  $("export-svg").onclick = () => telecharger("svg");
  $("export-script").onclick = () => telecharger("script");
  $("export-gcode").onclick = () => telecharger("gcode");
  $("largeur-essai").addEventListener("input", majMaquette);
  $("taille").addEventListener("input", (e) => ($("valeur-taille").textContent = e.target.value + " %"));
  $("taille").addEventListener("change", (e) => { reglages.taille = Number(e.target.value) / 100; calculer(); });
  // vitesse du robot : recalcul (durée, animation, programme) quand on valide le champ
  $("vitesse-robot").addEventListener("change", (e) => {
    const v = Number(e.target.value);
    if (v > 0) { reglages.vitesse = v; calculer(); }
  });
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
    // un groupe d'options par groupe d'étudiants, l'exemple à part
    // les 4 groupes toujours présents, même sans motif ; l'exemple à la fin
    const GROUPES = ["groupe_1", "groupe_2", "groupe_3", "groupe_4"];
    const groupes = [...new Set([...GROUPES, ...motifs.map((m) => m.groupe).filter((g) => g), ""])];
    $("choix-motif").innerHTML = groupes.map((g) => {
      const titre = g ? g.replace("groupe_", "Groupe ") : "Exemple (référence)";
      let options = motifs.filter((m) => m.groupe === g).map((m) => `<option value="${m.id}">${m.nom}</option>`);
      if (!options.length) options = ["<option disabled>aucun motif pour l'instant (à créer par une issue)</option>"];
      return `<optgroup label="${titre}">${options.join("")}</optgroup>`;
    }).join("");
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
      delete reglages.taille;      // nouvelle forme : sa taille réelle si elle tient
      calculer();
    };
    $("choix-contour").onchange = (e) => {
      if (e.target.value !== "importe") choisirExemple(e.target.value);
    };
    $("fichier-contour").onchange = async (e) => {
      const fichier = e.target.files[0];
      if (!fichier) return;
      contour = { nom: fichier.name, texte: await fichier.text() };
      delete reglages.taille;
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
