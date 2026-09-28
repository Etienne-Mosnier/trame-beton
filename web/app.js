// Aperçu de la trame : curseurs générés depuis PARAMETRES, calcul en Python (Pyodide),
// dessin avec three.js. Repère : celui de la palette, en mm, z vers le haut.

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { Line2 } from "three/addons/lines/Line2.js";
import { LineGeometry } from "three/addons/lines/LineGeometry.js";
import { LineMaterial } from "three/addons/lines/LineMaterial.js";
import { preparer, URL_PYODIDE } from "./pyodide_trame.mjs";

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

// groupes redessinés à chaque calcul
const groupePalette = new THREE.Group();
const groupeTrame = new THREE.Group();
const groupeAlertes = new THREE.Group(); // endroits à problème, en rouge
scene.add(groupePalette, groupeTrame, groupeAlertes);
const materiaux = [];

let palette = [1200, 800];

function vueDessus() {
  const [lx, ly] = palette;
  controles.target.set(lx / 2, ly / 2, 0);
  camera.position.set(lx / 2, ly / 2 - 1, Math.max(lx, ly) * 1.6);
  controles.update();
  activer("vue-dessus");
}

function vue3d() {
  const [lx, ly] = palette;
  controles.target.set(lx / 2, ly / 2, 0);
  camera.position.set(lx / 2 + 250, -ly * 1.25, Math.max(lx, ly) * 1.05);
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

function boucle() {
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
  plateau.position.set(lx / 2, ly / 2, -11.5);
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
  vider(groupeAlertes);
  if (!$("montrer-alertes").checked) return;
  const rouge = "#e11d48";
  for (const c of resultat.controles) {
    if (c.statut === "ok") continue;
    for (const s of c.segments) {
      groupeAlertes.add(trait(s.map((p) => [p[0], p[1], (p[2] ?? 0) * exageration + 3]), rouge, 6));
    }
    for (const p of c.points) {
      const anneau = new THREE.Mesh(
        new THREE.RingGeometry(9, 13, 24),
        new THREE.MeshBasicMaterial({ color: rouge, side: THREE.DoubleSide }),
      );
      anneau.position.set(p[0], p[1], 4);
      groupeAlertes.add(anneau);
    }
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
    dessinerPalette(r.contour);
    dessinerTrame(r, Number($("exageration").value));
    afficherBilan(r);
    if (!dejaCadre) { vue3d(); dejaCadre = true; }
    etat.textContent = "";
    console.log(`calcul : ${((performance.now() - debut) / 1000).toFixed(2)} s`);
  }, 20);
}

// télécharge le fichier DXF ou SVG du dernier calcul
function telecharger(format) {
  if (!app) return;
  const r = JSON.parse(app.exporter(format));
  if (r.erreur) { alert(r.erreur); return; }
  const type = format === "svg" ? "image/svg+xml" : "application/dxf";
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
  $("export-dxf").onclick = () => telecharger("dxf");
  $("export-svg").onclick = () => telecharger("svg");
  $("montrer-alertes").addEventListener("change", () => {
    if (dernierResultat) dessinerAlertes(dernierResultat, Number($("exageration").value));
  });
  $("exageration").addEventListener("input", (e) => {
    $("valeur-exageration").textContent = "× " + e.target.value;
    if (dernierResultat) dessinerTrame(dernierResultat, Number(e.target.value));
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
  } catch (erreur) {
    etat.innerHTML = `<span class="erreur">Erreur : ${erreur.message}</span>`;
    console.error(erreur);
  }
}

demarrer();
