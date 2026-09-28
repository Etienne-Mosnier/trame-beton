// Le bras UR10e dans la scène : maillages visuels officiels (web/robot/ur10e/visuel, licence BSD-3),
// assemblés comme dans Universal_Robots_ROS2_Description (ur_macro.xacro), plus une buse
// simplifiée. Unités du bras : mètres (le groupe est mis à l'échelle ×1000 pour la scène en mm).

import * as THREE from "three";
import { ColladaLoader } from "three/addons/loaders/ColladaLoader.js";

const PI = Math.PI;

// articulations : origine (xyz en m, rpy en rad) puis rotation autour de z
const ARTICULATIONS = [
  { xyz: [0, 0, 0.1807], rpy: [0, 0, 0], maillage: "shoulder", decalage: { xyz: [0, 0, 0], rpy: [0, 0, PI] } },
  { xyz: [0, 0, 0], rpy: [PI / 2, 0, 0], maillage: "upperarm", decalage: { xyz: [0, 0, 0.1762], rpy: [PI / 2, 0, -PI / 2] } },
  { xyz: [-0.6127, 0, 0], rpy: [0, 0, 0], maillage: "forearm", decalage: { xyz: [0, 0, 0.0393], rpy: [PI / 2, 0, -PI / 2] } },
  { xyz: [-0.57155, 0, 0.17415], rpy: [0, 0, 0], maillage: "wrist1", decalage: { xyz: [0, 0, -0.135], rpy: [PI / 2, 0, 0] } },
  { xyz: [0, -0.11985, 0], rpy: [PI / 2, 0, 0], maillage: "wrist2", decalage: { xyz: [0, 0, -0.12], rpy: [0, 0, 0] } },
  { xyz: [0, 0.11655, 0], rpy: [PI / 2, PI, PI], maillage: "wrist3", decalage: { xyz: [0, -0.0005, -0.1168], rpy: [PI / 2, 0, 0] } },
];

// groupe placé selon une origine URDF : rpy = Rz(yaw)·Ry(pitch)·Rx(roll)
function origine(xyz, rpy) {
  const g = new THREE.Group();
  g.position.set(...xyz);
  g.rotation.set(rpy[0], rpy[1], rpy[2], "ZYX");
  return g;
}

// Crée le bras. Renvoie { groupe, articulations } ; articulations[i].rotation.z = angle i.
export async function creerRobot(dossier) {
  const chargeur = new ColladaLoader();
  const noms = ["base", ...ARTICULATIONS.map((a) => a.maillage)];
  const scenes = Object.fromEntries(await Promise.all(noms.map(async (n) => {
    const collada = await chargeur.loadAsync(`${dossier}/visuel/${n}.dae`);
    // le chargeur tourne les fichiers « Z en haut » pour three.js ; notre scène est déjà Z en haut
    collada.scene.rotation.set(0, 0, 0);
    return [n, collada.scene];
  })));

  const maillage = (nom, decalage) => {
    const g = origine(decalage.xyz, decalage.rpy);
    g.add(scenes[nom]);
    return g;
  };

  // repère « base » du contrôleur -> base_link (rz π) -> base_link_inertia (rz π)
  const groupe = new THREE.Group();
  const baseLink = origine([0, 0, 0], [0, 0, PI]);
  const inertie = origine([0, 0, 0], [0, 0, PI]);
  groupe.add(baseLink);
  baseLink.add(inertie);
  inertie.add(maillage("base", { xyz: [0, 0, 0], rpy: [0, 0, PI] }));

  let parent = inertie;
  const articulations = [];
  ARTICULATIONS.forEach((a) => {
    const o = origine(a.xyz, a.rpy);
    const rotation = new THREE.Group();          // tourne autour de son axe z
    o.add(rotation);
    rotation.add(maillage(a.maillage, a.decalage));
    parent.add(o);
    articulations.push(rotation);
    parent = rotation;
  });

  // wrist_3 -> flange -> tool0
  const bride = origine([0, 0, 0], [0, -PI / 2, -PI / 2]);
  const tool0 = origine([0, 0, 0], [PI / 2, 0, PI / 2]);
  parent.add(bride);
  bride.add(tool0);
  return { groupe, articulations, tool0 };
}

// Buse simplifiée, dans le repère tool0 : une platine sur la bride, un bras jusqu'au-dessus
// du TCP, et la buse elle-même qui finit au TCP. tcp = [x, y, z (mm), rx, ry, rz] (config).
export function creerBuse(tcp) {
  const [x, y, z] = tcp.slice(0, 3).map((v) => v / 1000);
  const materiau = new THREE.MeshStandardMaterial({ color: "#8a8f98", metalness: 0.4, roughness: 0.4 });
  const groupe = new THREE.Group();

  const platine = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, z, 24), materiau);
  platine.rotation.x = PI / 2;                   // cylindre le long de z de tool0
  platine.position.set(0, 0, z / 2);
  groupe.add(platine);

  // axe de la buse : l'axe z du TCP, exprimé dans tool0
  const rv = new THREE.Vector3(...tcp.slice(3));
  const angle = rv.length();
  const q = new THREE.Quaternion().setFromAxisAngle(rv.clone().normalize(), angle);
  const axe = new THREE.Vector3(0, 0, 1).applyQuaternion(q);
  const pointe = new THREE.Vector3(x, y, z);
  const longueur = 0.09;
  const haut = pointe.clone().addScaledVector(axe, -longueur);

  // bras : de la platine jusqu'au haut de la buse
  const depart = new THREE.Vector3(0, 0, z);
  groupe.add(barre(depart, haut, 0.015, materiau));
  // buse : cône qui finit en pointe au TCP
  const buse = new THREE.Mesh(new THREE.CylinderGeometry(0.004, 0.018, longueur, 24), materiau);
  buse.position.copy(haut.clone().add(pointe).multiplyScalar(0.5));
  buse.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), axe);   // petite pointe vers le TCP
  groupe.add(buse);
  return groupe;
}

// cylindre entre deux points
function barre(a, b, rayon, materiau) {
  const direction = b.clone().sub(a);
  const m = new THREE.Mesh(new THREE.CylinderGeometry(rayon, rayon, direction.length(), 16), materiau);
  m.position.copy(a.clone().add(b).multiplyScalar(0.5));
  m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize());
  return m;
}
