// Aperçu de la trame : dessin importé en calques (SVG ou DXF), calcul en Python (Pyodide),
// dessin avec three.js. Unités : mm, z vers le haut.
// Repère de la scène : celui du robot. La palette (avec tout ce qu'elle porte) est un objet
// que l'on sélectionne d'un clic et que l'on déplace ou tourne avec un gizmo.

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { TransformControls } from "three/addons/controls/TransformControls.js";
import { Line2 } from "three/addons/lines/Line2.js";
import { LineGeometry } from "three/addons/lines/LineGeometry.js";
import { LineMaterial } from "three/addons/lines/LineMaterial.js";
import { preparer, URL_PYODIDE } from "./pyodide_trame.mjs?v=6a446c1eb7c9";
import { creerBuse, creerRobot } from "./robot.js?v=6a446c1eb7c9";

// une couleur par série, dans l'ordre d'impression
// noir, orange, orange brûlé, orange clair, gris : le rouge est gardé pour les problèmes
const COULEURS = ["#111111", "#f97316", "#9a3412", "#fdba74", "#737373"];
// dimensions du cordon (mm) : celles réglées dans le panneau, reçues à chaque calcul
const cordonReel = { largeur: 10, hauteur: 5 };

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
const groupePauses = new THREE.Group();  // pauses : trajets à vide et points d'attente (toujours visibles)
contenuPalette.add(groupePalette, groupeTrame, groupeAlertes, groupeCordon, groupeAlertesRobot, groupePauses);
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

// Section d'un cordon : une « pilule » (rectangle aux coins arrondis, demi-cercles aux bouts)
// de la largeur et de la hauteur du cordon. Points (u en travers, v vers le haut), v de 0 à hauteur.
const POINTS_PAR_QUART = 4;
function sectionPilule(largeur, hauteur) {
  const r = Math.min(largeur, hauteur) / 2;
  const cu = largeur / 2 - r, bas = r, haut = hauteur - r;
  const coins = [[cu, bas, -90], [cu, haut, 0], [-cu, haut, 90], [-cu, bas, 180]];
  const points = [];
  for (const [u0, v0, debut] of coins) {
    for (let k = 0; k <= POINTS_PAR_QUART; k++) {
      const a = THREE.MathUtils.degToRad(debut + (90 * k) / POINTS_PAR_QUART);
      points.push([u0 + r * Math.cos(a), v0 + r * Math.sin(a)]);
    }
  }
  return points;
}

// Un cordon de béton en volume : la section en pilule poussée le long du chemin. Le chemin passe
// sous le cordon, au milieu de sa largeur ; la section reste perpendiculaire au chemin (elle se
// penche dans les montées des bosses). Pour l'animation, la géométrie se dessine segment par
// segment (userData.parSegment : indices d'un segment).
function cordon(points, largeur, hauteur, couleur) {
  const profil = sectionPilule(largeur, hauteur);
  const m = profil.length, n = points.length;
  const positions = new Float32Array((n * m + 2) * 3);
  const haut = new THREE.Vector3(0, 0, 1), T = new THREE.Vector3(), N = new THREE.Vector3(0, 1, 0);
  const B = new THREE.Vector3(), cote = new THREE.Vector3();
  const centres = [];
  let k = 0;
  for (let i = 0; i < n; i++) {
    const a = points[Math.max(i - 1, 0)], b = points[Math.min(i + 1, n - 1)];
    T.set(b[0] - a[0], b[1] - a[1], (b[2] ?? 0) - (a[2] ?? 0));
    if (T.lengthSq() > 1e-12) {
      T.normalize();
      cote.crossVectors(haut, T);
      if (cote.lengthSq() > 1e-9) N.copy(cote.normalize());
    }
    B.crossVectors(T, N).normalize();
    const [x, y, z] = [points[i][0], points[i][1], points[i][2] ?? 0];
    for (const [u, v] of profil) {
      positions[k++] = x + N.x * u + B.x * v;
      positions[k++] = y + N.y * u + B.y * v;
      positions[k++] = z + N.z * u + B.z * v;
    }
    if (i === 0 || i === n - 1) centres.push([x + B.x * hauteur / 2, y + B.y * hauteur / 2, z + B.z * hauteur / 2]);
  }
  for (const c of centres) { positions[k++] = c[0]; positions[k++] = c[1]; positions[k++] = c[2]; }
  // les segments d'abord (dans l'ordre du chemin), puis les deux bouts
  const indices = [];
  for (let i = 0; i < n - 1; i++) {
    for (let j = 0; j < m; j++) {
      const a = i * m + j, b = i * m + ((j + 1) % m), c = (i + 1) * m + ((j + 1) % m), d = (i + 1) * m + j;
      indices.push(a, b, c, a, c, d);
    }
  }
  const debut = n * m, fin = n * m + 1;
  for (let j = 0; j < m; j++) {
    indices.push(debut, (j + 1) % m, j);
    indices.push(fin, (n - 1) * m + j, (n - 1) * m + ((j + 1) % m));
  }
  const geometrie = new THREE.BufferGeometry();
  geometrie.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometrie.setIndex(indices);
  geometrie.computeVertexNormals();
  const maille = new THREE.Mesh(geometrie, new THREE.MeshStandardMaterial({
    color: couleur, roughness: 0.8, metalness: 0, side: THREE.DoubleSide }));
  maille.userData.parSegment = m * 6;
  maille.userData.segments = n - 1;
  return maille;
}

// cordon dessiné jusqu'au segment 'segments' (animation du robot) ; tout, bouts compris, à la fin
function devoiler(maille, segments) {
  const tout = segments >= maille.userData.segments;
  maille.geometry.setDrawRange(0, tout ? Infinity : Math.max(0, segments) * maille.userData.parSegment);
}

function dessinerPalette() {
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
}

// les cordons en volume, aux dimensions réglées ; « Bosses exagérées » étire la trame en hauteur
function dessinerTrame(resultat, exageration) {
  vider(groupeTrame);
  materiaux.length = 0;
  resultat.waves.forEach((serie, i) => {
    for (const vague of serie) {
      if (vague.length < 2) continue;
      groupeTrame.add(cordon(vague, cordonReel.largeur, cordonReel.hauteur, COULEURS[i % COULEURS.length]));
    }
  });
  exagerer(resultat, exageration);
  redimensionner();
}

// « Bosses exagérées » : la trame et le cordon du robot étirés en hauteur ; pauses et alertes suivent
function exagerer(resultat, exageration) {
  groupeTrame.scale.z = groupeCordon.scale.z = exageration;
  dessinerPauses(resultat, exageration);
  dessinerAlertes(resultat, exageration);
  if (robot.donnees) marquer(groupeAlertesRobot, robot.donnees.alertes, exageration);
}

// pauses, départ et fin : parcours de la buse levée (pointillés gris) et point d'attente
function dessinerPauses(resultat, exageration) {
  vider(groupePauses);
  const attente = (trajet, point, nom) => {
    const points = trajet.map((p, j) => [p[0], p[1], j === 0 || j === trajet.length - 1 ? p[2] * exageration : p[2]]);
    groupePauses.add(trait(points, "#737373", 2, true));
    const [x, y, z] = point;
    const anneau = new THREE.Mesh(new THREE.RingGeometry(12, 18, 32),
                                  new THREE.MeshBasicMaterial({ color: "#c2410c", side: THREE.DoubleSide }));
    anneau.position.set(x, y, z);
    const texte = etiquette(nom, "#c2410c", 34);
    texte.position.set(x, y, z + 40);
    groupePauses.add(anneau, texte);
  };
  (resultat.deplacements || []).forEach((dep, k) => attente(dep, resultat.pauses[k].point, `pause ${k + 1}`));
  if (resultat.depart) attente(resultat.depart.trajet, resultat.depart.point, "départ");
  if (resultat.fin) attente(resultat.fin.trajet, resultat.fin.point, "fin");
}

// les endroits signalés par les contrôles : anneaux et traits rouges, au-dessus des cordons
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
      groupe.add(trait(s.map((p) => [p[0], p[1], ((p[2] ?? 0) + cordonReel.hauteur) * exageration + 2]), rouge, 6));
    }
    for (const p of c.points) {
      const anneau = new THREE.Mesh(
        new THREE.RingGeometry(9, 13, 24),
        new THREE.MeshBasicMaterial({ color: rouge, side: THREE.DoubleSide }),
      );
      anneau.position.set(p[0], p[1], cordonReel.hauteur * exageration + 2);
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

  // cordon : un volume par série, sur la plage de points de cette série (sans approche/dégagement)
  vider(groupeCordon);
  robot.lignes = [];
  const exageration = Number($("exageration").value);
  groupeCordon.scale.z = exageration;
  let debut = 1, serie = d.series[1];
  for (let k = 2; k <= d.points.length - 1; k++) {
    if (k === d.points.length - 1 || d.series[k] !== serie) {
      const points = d.points.slice(debut, k);
      if (points.length > 1 && serie >= 0) {
        const maille = cordon(points, cordonReel.largeur, cordonReel.hauteur, COULEURS[serie % COULEURS.length]);
        groupeCordon.add(maille);
        robot.lignes.push({ maille, debut, fin: k - 1 });
      }
      // la série suivante repart du dernier point, sauf après un trajet buse levée (série -1) :
      // le cordon commence alors en bas, là où la buse se pose
      debut = serie === -1 ? k : k - 1;
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
  for (const { maille, debut, fin } of robot.lignes) devoiler(maille, Math.min(bas, fin) - debut);
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
      `couche de ${String(m.hauteur_couche).replace(".", ",")} mm. Vitesse ` +
      `${String(m.vitesse).replace(".", ",")} mm/s (à accorder avec le débit du boîtier), ` +
      `environ ${Math.max(1, Math.round(m.duree / 60))} min.` +
      (m.tient ? "" : ` ⚠ Trop grand pour le plateau rond de ${m.plateau} mm : cordon d'essai de ` +
                      `${String(Math.floor(m.essai_max * 10) / 10).replace(".", ",")} mm au plus.`);
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
  const surPalette = avecRobot() && rayon.intersectObjects(groupePalette.children, true).length > 0;
  for (const g of gizmos) {
    if (surPalette) g.attach(paletteMobile); else g.detach();
  }
}

// ---------------------------------------------------------------------------
// Panneau : dessin importé, liste des calques, curseurs
// ---------------------------------------------------------------------------

let app = null;
const avecRobot = () => true;   // l'aperçu est toujours en vraie grandeur, avec le bras
// dessin en cours : { cle, exemple, fichiers: [{nom, texte, poignee, date}],
//   calques: [{nom, fichier, couleur, imprime, lignes, longueur}] (sans les calques retirés),
//   ordre: [noms, dans l'ordre d'impression], eteints: Set(noms non imprimés),
//   pauses: Set(noms des calques après lesquels on fait une pause), supprimes: Set(noms retirés) }
let dessin = null;
let dernierResultat = null;
let dejaCadre = false; // la vue 3D est cadrée au premier calcul seulement
const reglages = { moteur: {} };
const MAX_CALQUES = 5;

// texte venu du fichier (noms de calques) : jamais interprété comme du HTML
const echapper = (texte) => String(texte).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

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

// --- le dessin : un ou plusieurs fichiers, que l'on ajoute ou retire ----------------------
// L'ordre, les pauses et les calques retirés sont retenus par le navigateur, pour chaque
// ensemble de fichiers.

const cleDes = (fichiers) => fichiers.map((f) => f.nom).sort().join(" + ");
// les fichiers tels que Python les lit (sans les poignées des fichiers suivis)
const pourPython = (fichiers) => JSON.stringify(fichiers.map(({ nom, texte }) => ({ nom, texte })));

function lireMemoire(cle) {
  try { return JSON.parse(localStorage.getItem("trame-calques:" + cle)); } catch { return null; }
}

function memoriser() {
  if (!dessin || dessin.exemple) return;
  try {
    localStorage.setItem("trame-calques:" + dessin.cle, JSON.stringify({
      ordre: dessin.ordre, eteints: [...dessin.eteints], pauses: [...dessin.pauses], supprimes: [...dessin.supprimes] }));
  } catch { /* navigation privée : l'ordre n'est simplement pas retenu */ }
}

const imprimes = () => dessin ? dessin.ordre.filter((n) => !dessin.eteints.has(n)) : [];

// Ouvre le dessin fait de ces fichiers [{nom, texte, poignee?, date?}].
//   garder  : on reprend l'ordre, les pauses et la taille du dessin en cours (fichier ajouté,
//             retiré ou réenregistré) ; les nouveaux calques vont à la fin de la liste
//   exemple : dessin d'exemple (un import le remplace au lieu de s'y ajouter)
//   revenus : fichiers que l'on vient d'importer à nouveau : leurs calques retirés reviennent
function ouvrirDessin(fichiers, { garder = false, exemple = false, revenus = [] } = {}) {
  if (!app) return;
  const cle = cleDes(fichiers);
  const r = JSON.parse(app.lire_calques(pourPython(fichiers)));
  if (r.erreur) {
    $("message-dessin").innerHTML = `<span class="erreur">${echapper(r.erreur)}</span>`;
    $("bilan").innerHTML = `<p class="erreur">${echapper(r.erreur)}</p>`;
    $("info").textContent = r.details || "";
    return;
  }
  // un exemple repart toujours de son état d'origine : le navigateur ne retient rien pour lui
  const memoire = garder && dessin
    ? { ordre: dessin.ordre, eteints: [...dessin.eteints], pauses: [...dessin.pauses], supprimes: [...dessin.supprimes] }
    : exemple ? null : lireMemoire(cle);
  const supprimes = new Set((memoire?.supprimes || []).filter(
    (n) => !r.calques.some((c) => c.nom === n && revenus.includes(c.fichier))));
  const calques = r.calques.filter((c) => !supprimes.has(c.nom));
  const noms = calques.map((c) => c.nom);
  const connus = (memoire?.ordre || []).filter((n) => noms.includes(n));
  dessin = { cle, fichiers, exemple, calques, supprimes,
             ordre: [...connus, ...noms.filter((n) => !connus.includes(n))] };
  dessin.eteints = new Set((memoire?.eteints || []).filter((n) => noms.includes(n)));
  dessin.pauses = new Set((memoire?.pauses || []).filter((n) => noms.includes(n)));
  // nouveaux calques : imprimés sauf s'ils sont masqués dans le fichier (cadre, palette…)
  for (const c of calques) if (!connus.includes(c.nom) && !c.imprime) dessin.eteints.add(c.nom);
  // au plus 5 calques imprimés : les suivants sont éteints
  imprimes().slice(MAX_CALQUES).forEach((n) => dessin.eteints.add(n));
  if (!garder) delete reglages.taille;    // nouveau dessin : sa taille réelle s'il tient
  memoriser();
  majTitreImport();
  majSuivi();
  if (!calques.length) { viderDessin(); return; }
  dessinerCalques();
  calculer();
}

// retire un calque du dessin ; un fichier dont tous les calques sont retirés quitte le dessin
function supprimer(nom) {
  const calque = dessin.calques.find((c) => c.nom === nom);
  dessin.supprimes.add(nom);
  const restants = dessin.fichiers.filter((f) => f.nom !== calque.fichier
    || dessin.calques.some((c) => c.fichier === f.nom && !dessin.supprimes.has(c.nom)));
  if (!restants.length) { viderDessin(); return; }
  ouvrirDessin(restants, { garder: true, exemple: dessin.exemple });
}

// plus aucun calque : la vue et le bilan se vident
function viderDessin() {
  dessin = null;
  dernierResultat = null;
  robot.donnees = null;
  robot.lignes = [];
  for (const g of [groupeTrame, groupePauses, groupeAlertes, groupeCordon, groupeAlertesRobot]) vider(g);
  $("calques").innerHTML = "";
  $("legende").innerHTML = "";
  $("message-dessin").textContent = "";
  $("info").textContent = "";
  $("bilan").innerHTML = "<p>Aucun calque : importer un ou plusieurs fichiers.</p>";
  majTitreImport();
  majSuivi();
}

// la liste déroulante : un exemple, ou « importé : … » (les fichiers du dessin en cours)
function majTitreImport() {
  const choix = $("choix-dessin");
  choix.querySelectorAll('option[value="importe"], option[value=""]').forEach((o) => o.remove());
  if (dessin?.exemple) return;
  if (!dessin) { choix.add(new Option("aucun dessin", "", true, true)); return; }
  const noms = dessin.fichiers.map((f) => f.nom);
  const titre = noms.length === 1 ? noms[0] : `${noms.length} fichiers (${noms.join(", ")})`;
  choix.add(new Option("importé : " + titre, "importe", true, true));
}

// la liste des calques : glisser une ligne pour changer l'ordre, l'œil pour (ne pas) imprimer
const OEIL = `<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="3" fill="currentColor"/></svg>`;
const OEIL_FERME = `<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" fill="none" stroke="currentColor" stroke-width="2"/><path d="M4 20 20 4" stroke="currentColor" stroke-width="2"/></svg>`;
let glisse = null;   // nom du calque que l'on est en train de glisser

function dessinerCalques() {
  const liste = $("calques");
  liste.innerHTML = "";
  if (!dessin) return;
  const ordreImpression = imprimes();
  for (const nom of dessin.ordre) {
    const calque = dessin.calques.find((c) => c.nom === nom);
    const rang = ordreImpression.indexOf(nom);
    const eteint = rang < 0;
    const li = document.createElement("li");
    li.className = "calque" + (eteint ? " eteint" : "");
    li.draggable = true;
    li.title = "Glisser pour changer l'ordre d'impression";
    const metres = (calque.longueur / 1000).toFixed(1).replace(".", ",");
    li.innerHTML = `
      <span class="poignee" aria-hidden="true">⋮⋮</span>
      <span class="rang">${eteint ? "" : rang + 1}</span>
      <span class="pastille" style="background:${eteint ? "transparent" : COULEURS[rang % COULEURS.length]}"></span>
      <span class="nom" title="${echapper(nom)} (fichier ${echapper(calque.fichier)})">${echapper(nom)}</span>
      <span class="info">${calque.lignes > 1 ? calque.lignes + " morceaux · " : ""}${metres} m</span>
      <button type="button" class="oeil" title="${eteint ? "Imprimer ce calque" : "Ne pas imprimer ce calque"}"
        aria-label="${eteint ? "Imprimer" : "Ne pas imprimer"} le calque ${echapper(nom)}">${eteint ? OEIL_FERME : OEIL}</button>
      <button type="button" class="retirer" title="Retirer ce calque du dessin"
        aria-label="Retirer le calque ${echapper(nom)}">×</button>`;
    li.querySelector(".oeil").addEventListener("click", () => basculer(nom));
    li.querySelector(".retirer").addEventListener("click", () => supprimer(nom));
    // après un calque imprimé : relié ou pause avant le suivant (après le dernier : entre deux couches)
    const dernier = rang === ordreImpression.length - 1;
    li.addEventListener("dragstart", (e) => {
      glisse = nom;
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", nom);
      li.classList.add("glisse");
    });
    li.addEventListener("dragend", () => { glisse = null; dessinerCalques(); });
    li.addEventListener("dragover", (e) => {
      if (glisse === null || glisse === nom) return;
      e.preventDefault();
      const haut = e.offsetY < li.clientHeight / 2;
      li.classList.toggle("avant", haut);
      li.classList.toggle("apres", !haut);
    });
    li.addEventListener("dragleave", () => li.classList.remove("avant", "apres"));
    li.addEventListener("drop", (e) => {
      e.preventDefault();
      if (glisse === null || glisse === nom) return;
      const apres = li.classList.contains("apres");
      const ordre = dessin.ordre.filter((n) => n !== glisse);
      ordre.splice(ordre.indexOf(nom) + (apres ? 1 : 0), 0, glisse);
      dessin.ordre = ordre;
      glisse = null;
      memoriser();
      dessinerCalques();
      calculer();
    });
    liste.appendChild(li);
    if (!eteint && (!dernier || (reglages.moteur.couches || 1) > 1)) liste.appendChild(jonction(nom, dernier));
  }
}

// entre deux calques : « relié » (le cordon continue) ou « pause » (la buse sort du dessin et attend)
function jonction(nom, entreCouches) {
  const pause = dessin.pauses.has(nom);
  const li = document.createElement("li");
  li.className = "jonction" + (pause ? " pause" : "");
  const ou = entreCouches ? "entre deux couches" : "";
  li.innerHTML = `<button type="button" title="${pause ? "Relier sans pause" : "Faire une pause ici : la buse sort du dessin et attend « Continuer »"}">
    ${pause ? "⏸ pause" : "↓ relié"}${ou ? ` <span>${ou}</span>` : ""}</button>`;
  li.querySelector("button").addEventListener("click", () => {
    if (pause) dessin.pauses.delete(nom); else dessin.pauses.add(nom);
    memoriser();
    dessinerCalques();
    calculer();
  });
  return li;
}

function basculer(nom) {
  if (dessin.eteints.has(nom)) {
    if (imprimes().length >= MAX_CALQUES) {
      etat.textContent = `${MAX_CALQUES} calques imprimés au plus : en éteindre un d'abord.`;
      setTimeout(() => (etat.textContent = ""), 3000);
      return;
    }
    dessin.eteints.delete(nom);
  } else {
    dessin.eteints.add(nom);
  }
  memoriser();
  dessinerCalques();
  calculer();
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
        <p><span class="symbole">${symbole[c.statut]}</span> ${echapper(c.titre)}</p>
        ${c.statut === "ok" ? "" : `<p class="petit">${echapper(c.message)}</p>`}
      </div>`).join("")}
    <p class="petit">Cordon de ${r.beton.largeur_cordon} mm${provisoire("largeur_cordon")},
      virage le plus serré ${r.beton.rayon_courbure_min} mm${provisoire("rayon_courbure_min")}.
      Les valeurs provisoires seront fixées pendant les essais.</p>`;
  $("info").textContent = r.info;
  $("message-dessin").textContent = r.message_dessin;
  // légende : les calques dans l'ordre d'impression, chacun par-dessus les précédents
  $("legende").innerHTML = r.calques.map((nom, i) => {
    const role = i === 0 ? "imprimé en premier" : i === 1 ? "passe par-dessus 1"
      : i === 2 ? "passe par-dessus 1 et 2" : `passe par-dessus 1 à ${i}`;
    const pause = r.pauses.some((p) => p.calque === nom && p.couche === 1) && i < r.calques.length - 1
      ? `<div class="pause-legende">⏸ pause</div>` : "";
    return `<div><span class="pastille" style="background:${COULEURS[i % COULEURS.length]}"></span>${i + 1}. ${echapper(nom)} : ${role}</div>${pause}`;
  }).join("");
}

function calculer() {
  if (!app || !dessin) return;
  dessinerCalques();      // le nombre de couches change la liste (pause entre deux couches)
  etat.textContent = "Calcul…";
  // on laisse le navigateur afficher « Calcul… » avant de bloquer pendant le calcul
  setTimeout(() => {
    const debut = performance.now();
    const r = JSON.parse(app.calculer(JSON.stringify({ ...reglages, calques: imprimes(), pauses: [...dessin.pauses] }),
                                      pourPython(dessin.fichiers)));
    if (r.erreur) {
      etat.textContent = "";
      $("bilan").innerHTML = `<p class="erreur">${echapper(r.erreur)}</p>`;
      $("info").textContent = r.details || "";
      return;
    }
    dernierResultat = r;
    palette = r.palette;
    // les cordons de l'aperçu ont les dimensions réglées dans le panneau
    cordonReel.largeur = r.beton.largeur_cordon;
    cordonReel.hauteur = r.beton.hauteur_couche;
    positionnerPalette();
    dessinerPalette();
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

// --- import : bouton, dépôt sur la vue, suivi du fichier ----------------------------------

// Chrome et Edge savent relire un fichier choisi : l'aperçu se met à jour dès qu'un des
// fichiers est réenregistré (dans Rhino, Illustrator…). Ailleurs, on l'importe à nouveau.
function majSuivi() {
  const n = dessin?.fichiers.filter((f) => f.poignee).length || 0;
  $("suivi-fichier").textContent = !n ? ""
    : n === 1 ? "Fichier suivi : l'aperçu se met à jour à chaque enregistrement."
    : `${n} fichiers suivis : l'aperçu se met à jour à chaque enregistrement de l'un d'eux.`;
}

setInterval(async () => {
  const suivis = dessin?.fichiers.filter((f) => f.poignee) || [];
  let change = false;
  for (const f of suivis) {
    try {
      const fichier = await f.poignee.getFile();
      if (fichier.lastModified === f.date) continue;
      f.date = fichier.lastModified;
      f.texte = await fichier.text();
      change = true;
    } catch {
      f.poignee = null;     // fichier déplacé ou supprimé : on arrête de le suivre
      majSuivi();
    }
  }
  if (change) ouvrirDessin(dessin.fichiers, { garder: true });
}, 1500);

const DESSIN_ACCEPTE = /\.(svg|dxf)$/i;

// Importe un ou plusieurs fichiers : ils s'ajoutent au dessin en cours (un fichier du même nom
// est remplacé par sa nouvelle version) ; un dessin d'exemple, lui, est remplacé.
async function importer(fichiers, poignees = []) {
  const refuses = fichiers.filter((f) => !DESSIN_ACCEPTE.test(f.name));
  if (!fichiers.length || refuses.length) {
    const noms = refuses.map((f) => `« ${echapper(f.name)} »`).join(", ");
    $("message-dessin").innerHTML = `<span class="erreur">${noms} : importer des fichiers .svg ou .dxf.</span>`;
    return;
  }
  const nouveaux = await Promise.all(fichiers.map(async (f, i) => (
    { nom: f.name, texte: await f.text(), poignee: poignees[i] || null, date: f.lastModified })));
  const ajout = !!dessin && !dessin.exemple;
  const anciens = ajout ? dessin.fichiers.filter((f) => !nouveaux.some((n) => n.nom === f.nom)) : [];
  ouvrirDessin([...anciens, ...nouveaux], { garder: ajout, revenus: nouveaux.map((n) => n.nom) });
}

// télécharge le fichier DXF ou SVG du dernier calcul
function telecharger(format) {
  if (!app) return;
  if (!dessin) { alert("Rien à exporter : importer d'abord un dessin."); return; }
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
  // un fichier glissé sur la vue est importé
  $("scene").addEventListener("dragover", (e) => {
    if (!e.dataTransfer.types.includes("Files")) return;
    e.preventDefault();
    $("scene").classList.add("depot");
  });
  $("scene").addEventListener("dragleave", () => $("scene").classList.remove("depot"));
  $("scene").addEventListener("drop", async (e) => {
    $("scene").classList.remove("depot");
    const elements = [...e.dataTransfer.items].filter((i) => i.kind === "file");
    if (!elements.length) return;
    e.preventDefault();
    // toutes les demandes partent tout de suite : après un « await », les éléments ne sont plus lisibles
    const demandes = elements.map((el) => el.getAsFileSystemHandle?.());
    const fichiers = elements.map((el) => el.getAsFile());
    const poignees = await Promise.all(demandes.map((d) => d?.catch(() => null)));
    importer(fichiers, poignees.map((p) => (p?.kind === "file" ? p : null)));
  });
  // bouton Importer : dans Chrome et Edge, on garde une poignée vers le fichier pour le suivre
  $("bouton-import").addEventListener("click", async (e) => {
    if (!window.showOpenFilePicker) return;         // autres navigateurs : sélecteur habituel
    e.preventDefault();
    try {
      const poignees = await window.showOpenFilePicker({
        multiple: true,
        types: [{ description: "Dessin DXF ou SVG", accept: { "application/octet-stream": [".dxf", ".svg"] } }],
      });
      importer(await Promise.all(poignees.map((p) => p.getFile())), poignees);
    } catch { /* sélection annulée */ }
  });
  $("fichier-dessin").addEventListener("change", (e) => {
    if (e.target.files.length) importer([...e.target.files]);
    e.target.value = "";
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
    if (dernierResultat) exagerer(dernierResultat, Number(e.target.value));
  });

  try {
    const { loadPyodide } = await import(URL_PYODIDE + "pyodide.mjs");
    const pyodide = await loadPyodide({ indexURL: URL_PYODIDE });
    const pret = await preparer(pyodide, lireTexte, (m) => (etat.textContent = m));
    app = pret.app;

    // réglages du moteur
    for (const [nom, p] of Object.entries(JSON.parse(app.reglages_moteur()))) {
      curseur($("reglages-moteur"), nom, p, reglages.moteur);
    }

    // dessins d'exemple
    const exemples = pret.fichiers.filter((f) => f.startsWith("dessins/"));
    $("choix-dessin").innerHTML = exemples
      .map((f) => `<option value="${f}">exemple : ${f.replace("dessins/", "")}</option>`).join("");
    const parDefaut = exemples.find((f) => f.includes("vagues")) || exemples[0];
    $("choix-dessin").value = parDefaut;
    const choisirExemple = async (chemin) => {
      ouvrirDessin([{ nom: chemin.split("/").pop(), texte: await lireTexte(chemin) }], { exemple: true });
    };
    $("choix-dessin").onchange = (e) => {
      if (e.target.value.startsWith("dessins/")) choisirExemple(e.target.value);
    };
    await choisirExemple(parDefaut);
    chargerRobot();
  } catch (erreur) {
    etat.innerHTML = `<span class="erreur">Erreur : ${erreur.message}</span>`;
    console.error(erreur);
  }
}

demarrer();
