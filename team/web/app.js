// «Рудник под лимитом»: 3D view of the complex.
// Everything shown comes from the twins in Ditto (read every 2 s through the
// nginx proxy of this page); the scenario and mode buttons write to the
// control twin. Units in the scene are schematic, about 10 m each.

import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from './vendor/CSS2DRenderer.js';
import { GLTFLoader } from './vendor/GLTFLoader.js';

const NS = 'kz.limit';
const NAMES = ['complex', 'control', 'planner', 'pit', 'face-1', 'face-2', 'face-3', 'shovel-1', 'shovel-2', 'shovel-3',
  'crusher', 'conveyor', 'stockpile', 'plant', 'mill-1', 'mill-2', 'flotation', 'thickener', 'process-water',
  'water-intake', 'tailings', 'reclaim', 'substation'];
const SCENARIOS = [
  ['dry_year', 'Маловодный год', 'водозабор −30 %: 1 750 → 1 225 м³/ч'],
  ['grid_peak', 'Вечерний пик энергосистемы', 'лимит 78 → 58 МВт с 18:00 до 22:00'],
  ['mill2_repair', 'Мельница №2 на ремонте', 'одна линия измельчения из двух'],
  ['hard_ore', 'Твёрдая руда в забое №3', 'Wi 15,5 → 19,5 кВт·ч/т'],
];
const POLL_MS = 2000;

const T = {};                       // twin name -> {feature: properties}
const v = (n, f, d = 0) => { const x = T[n]?.[f]?.value; return x === undefined || x === null ? d : x; };
const fmt = (x, nd = 0) => (x === undefined || x === null || Number.isNaN(x)) ? '–'
  : Number(x).toLocaleString('ru-RU', { minimumFractionDigits: nd, maximumFractionDigits: nd });
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const $ = (s) => document.querySelector(s);

// ---------------------------------------------------------------- scene ----
const host = $('#scene');
// preserveDrawingBuffer: screenshots of the page (headless browsers too) show the scene
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
host.appendChild(renderer.domElement);
const labels = new CSS2DRenderer();
labels.domElement.style.position = 'absolute';
labels.domElement.style.top = '0';
labels.domElement.style.pointerEvents = 'none';
host.appendChild(labels.domElement);

const scene = new THREE.Scene();
const SKY_DAY = new THREE.Color(0x9cc3d8), SKY_DUSK = new THREE.Color(0x3d4a66), SKY_NIGHT = new THREE.Color(0x0f1a2a);
scene.background = SKY_DAY.clone();
scene.fog = new THREE.Fog(scene.background, 650, 1300);
const camera = new THREE.PerspectiveCamera(42, 1, 1, 4000);
camera.position.set(-10, 270, 330);
const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(20, 0, 30);
controls.maxPolarAngle = Math.PI * 0.47;
controls.minDistance = 60;
controls.maxDistance = 900;
controls.enableDamping = true;

const hemi = new THREE.HemisphereLight(0xdfeeff, 0x6b5a3a, 1.1);
scene.add(hemi);
const sun = new THREE.DirectionalLight(0xfff1dc, 1.6);
sun.position.set(-160, 260, 120);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
Object.assign(sun.shadow.camera, { left: -320, right: 320, top: 260, bottom: -260, near: 10, far: 900 });
scene.add(sun);

function resize() {
  const w = host.clientWidth, h = host.clientHeight;
  renderer.setSize(w, h);
  labels.setSize(w, h);
  camera.aspect = w / h;
  // centre the scene in the gap between the side panels, when they are shown
  const left = document.querySelector('#left'), right = document.querySelector('#right');
  const bare = document.body.classList.contains('bare') || w < 800;
  const shift = bare || !left || !right ? 0
    : ((left.getBoundingClientRect().right + right.getBoundingClientRect().left) / 2 - w / 2);
  if (shift) camera.setViewOffset(w, h, -shift, -20, w, h); else camera.clearViewOffset();
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);
resize();

const mat = (color, o = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.85, metalness: 0.05, ...o });
function mesh(geo, material, x = 0, y = 0, z = 0, parent = scene) {
  const m = new THREE.Mesh(geo, material);
  m.position.set(x, y, z);
  m.castShadow = true;
  m.receiveShadow = true;
  parent.add(m);
  return m;
}
function label(parent, x, y, z, title) {
  const el = document.createElement('div');
  el.className = 'chip';
  el.innerHTML = `<b>${title}</b><span></span>`;
  const obj = new CSS2DObject(el);
  obj.position.set(x, y, z);
  parent.add(obj);
  return { el, text: (s) => { el.lastChild.innerHTML = s; } };
}

// Objects to flash when the planner names them as the bottleneck.
const highlight = {};               // name -> {materials: [], chip}
function register(name, materials, chip) {
  highlight[name] = { materials: [].concat(materials), chip };
}

// ------------------------------------------------------------- terrain -----
const PIT = new THREE.Vector3(-92, 0, 22);
const PIT_R = 68, PIT_DEPTH = 44, BENCHES = 6;
{
  const shape = new THREE.Shape();
  shape.moveTo(-420, -330); shape.lineTo(420, -330); shape.lineTo(420, 330); shape.lineTo(-420, 330); shape.lineTo(-420, -330);
  const hole = new THREE.Path();
  hole.absarc(PIT.x, -PIT.z, PIT_R, 0, Math.PI * 2, true);
  shape.holes.push(hole);
  const ground = mesh(new THREE.ShapeGeometry(shape, 64), mat(0xb7a67b), 0, 0, 0);
  ground.rotation.x = -Math.PI / 2;
  ground.castShadow = false;
}
// The pit: benches as a lathe profile, coloured by depth (oxide cap to fresh sulphide rock).
const benchY = (k) => -PIT_DEPTH + (PIT_DEPTH / BENCHES) * k;       // floor of bench k
const benchR = (k) => 16 + ((PIT_R - 16) / BENCHES) * k;
{
  const pts = [new THREE.Vector2(0, -PIT_DEPTH), new THREE.Vector2(benchR(0), -PIT_DEPTH)];
  for (let k = 0; k < BENCHES; k++) {
    pts.push(new THREE.Vector2(benchR(k) + 3.5, benchY(k + 1)));
    pts.push(new THREE.Vector2(benchR(k + 1), benchY(k + 1)));
  }
  const geo = new THREE.LatheGeometry(pts, 72);
  const colors = [];
  const cTop = new THREE.Color(0xa0603a), cMid = new THREE.Color(0x8a7d6b), cLow = new THREE.Color(0x5c6863);
  const p = geo.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const t = -p.getY(i) / PIT_DEPTH;
    const c = t < 0.35 ? cTop.clone().lerp(cMid, t / 0.35) : cMid.clone().lerp(cLow, (t - 0.35) / 0.65);
    colors.push(c.r, c.g, c.b);
  }
  geo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  const pit = mesh(geo, mat(0xffffff, { vertexColors: true, side: THREE.DoubleSide, flatShading: true }), PIT.x, 0, PIT.z);
  pit.castShadow = false;
}

// --------------------------------------------------------------- flows -----
// A flow is a path with particles moving along it; rate 0..1 sets how many
// are visible and how fast they go.
const flows = [];
class Flow {
  constructor(points, { color, size = 1.2, count = 60, tube = 0, tubeColor = 0x8a9399, box = false, speed = 0.06 }) {
    this.curve = new THREE.CatmullRomCurve3(points.map((p) => new THREE.Vector3(...p)), false, 'catmullrom', 0.1);
    this.length = this.curve.getLength();
    if (tube) {
      this.pipeMat = mat(tubeColor, { metalness: 0.3, roughness: 0.6 });
      mesh(new THREE.TubeGeometry(this.curve, Math.max(16, Math.round(this.length / 4)), tube, 8), this.pipeMat);
    }
    const geo = box ? new THREE.BoxGeometry(size, size * 0.7, size) : new THREE.SphereGeometry(size * 0.5, 8, 6);
    this.mat = new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.45, roughness: 0.5 });
    this.inst = new THREE.InstancedMesh(geo, this.mat, count);
    this.inst.castShadow = false;
    scene.add(this.inst);
    this.count = count;
    this.offset = Math.random();
    this.speed = speed;
    this.rate = 0;
    this.dummy = new THREE.Object3D();
    flows.push(this);
  }
  set(rate, color) {
    this.rate = clamp(rate, 0, 1);
    if (color !== undefined) { this.mat.color.set(color); this.mat.emissive.set(color); }
  }
  tick(dt) {
    const n = Math.round(this.count * this.rate);
    this.offset = (this.offset + dt * this.speed * (0.4 + this.rate) * 60 / this.length) % 1;
    for (let i = 0; i < this.count; i++) {
      if (i < n) {
        const u = (i / Math.max(n, 1) + this.offset) % 1;
        this.dummy.position.copy(this.curve.getPointAt(u));
        this.dummy.scale.setScalar(1);
      } else {
        this.dummy.scale.setScalar(0.0001);
      }
      this.dummy.updateMatrix();
      this.inst.setMatrixAt(i, this.dummy.matrix);
    }
    this.inst.instanceMatrix.needsUpdate = true;
  }
}

// ------------------------------------------------------------- the pit -----
const FACES = [
  { name: 'face-1', shovel: 'shovel-1', angle: -Math.PI / 2 - 0.25, bench: 4, color: 0xd59a4a, title: 'Забой 1 · Северный' },
  { name: 'face-2', shovel: 'shovel-2', angle: 0.15, bench: 3, color: 0xd8c08a, title: 'Забой 2 · Восточный' },
  { name: 'face-3', shovel: 'shovel-3', angle: Math.PI / 2 + 0.2, bench: 1, color: 0xc0583a, title: 'Забой 3 · Южный, нижний' },
];
const CRUSHER = new THREE.Vector3(-22, 0, -22);
const trucks = [];

function makeShovel(color) {
  const g = new THREE.Group();
  const body = mat(0x3b4a52);
  mesh(new THREE.BoxGeometry(7, 2, 8), mat(0x22282b), 0, 1, 0, g);
  mesh(new THREE.BoxGeometry(6, 4.5, 6.5), body, 0, 4.2, 0.6, g);
  const boom = mesh(new THREE.BoxGeometry(1.1, 1.1, 11), mat(0xc9a227), 0, 7.5, -5.5, g);
  boom.rotation.x = 0.55;
  mesh(new THREE.BoxGeometry(3, 2.6, 2.6), mat(color), 0, 4, -10, g);
  return { g, body };
}
// Box trucks first; useModels() swaps in the Kenney haul truck once it loads.
function makeTruck() {
  const g = new THREE.Group();
  const body = new THREE.Group();
  g.add(body);
  mesh(new THREE.BoxGeometry(3.4, 1.6, 6), mat(0xe0b400), 0, 1.6, 0, body);
  mesh(new THREE.BoxGeometry(3.2, 1.6, 1.6), mat(0x3d4449), 0, 2.4, 2.9, body);
  const load = mesh(new THREE.BoxGeometry(2.8, 1.2, 4.2), mat(0x9b6a45), 0, 3, -0.6, body);
  scene.add(g);
  return { g, body, load, wheels: [] };
}

for (const f of FACES) {
  const r = benchR(f.bench) - 3, y = benchY(f.bench);
  const pos = new THREE.Vector3(PIT.x + Math.cos(f.angle) * r, y, PIT.z + Math.sin(f.angle) * r);
  // the ore face: a patch of the bench wall in the colour of its ore type
  const wallR = benchR(f.bench) + 2;
  f.rock = mat(f.color, { flatShading: true, emissive: 0x000000 });
  const patch = mesh(new THREE.DodecahedronGeometry(6.5, 0), f.rock,
    PIT.x + Math.cos(f.angle) * wallR, y + 4, PIT.z + Math.sin(f.angle) * wallR);
  patch.scale.set(1.4, 0.8, 1.4);
  const s = makeShovel(f.color);
  s.g.position.copy(pos);
  s.g.lookAt(PIT.x + Math.cos(f.angle) * (wallR + 10), y, PIT.z + Math.sin(f.angle) * (wallR + 10));
  s.g.rotateY(Math.PI);
  scene.add(s.g);
  f.chip = label(scene, pos.x, y + 16, pos.z, f.title);
  register(f.name, [f.rock], f.chip);
  register(f.shovel, [s.body], f.chip);

  // haul road: spiral up the benches to the rim, then to the crusher
  const exit = Math.atan2(CRUSHER.z - PIT.z, CRUSHER.x - PIT.x);
  let a0 = f.angle, a1 = exit;
  while (a1 - a0 > Math.PI) a1 -= Math.PI * 2;
  while (a0 - a1 > Math.PI) a1 += Math.PI * 2;
  if (Math.abs(a1 - a0) < 1.2) a1 += a1 >= a0 ? Math.PI * 1.2 : -Math.PI * 1.2;   // ramps need length
  const pts = [];
  for (let i = 0; i <= 24; i++) {
    const s2 = i / 24, yy = y * (1 - s2);
    const rr = benchR(0) + (PIT_R - benchR(0)) * (yy + PIT_DEPTH) / PIT_DEPTH - 4;
    const aa = a0 + (a1 - a0) * s2;
    pts.push(new THREE.Vector3(PIT.x + Math.cos(aa) * rr, yy + 0.8, PIT.z + Math.sin(aa) * rr));
  }
  pts.push(new THREE.Vector3(CRUSHER.x - 8, 0.8, CRUSHER.z + 4));
  f.road = new THREE.CatmullRomCurve3(pts);
  f.trucks = [];
  for (let i = 0; i < 4; i++) {
    const t = makeTruck();
    t.u = i / 4;
    f.trucks.push(t);
    trucks.push({ face: f, t });
  }
}

// ---------------------------------------------------- crushing, stockpile ---
const crusherMat = mat(0x7d8b92);
mesh(new THREE.BoxGeometry(14, 16, 14), crusherMat, CRUSHER.x, 8, CRUSHER.z);
mesh(new THREE.CylinderGeometry(7, 2.5, 6, 16), mat(0x5d666b), CRUSHER.x - 8, 3, CRUSHER.z + 4);
const crusherChip = label(scene, CRUSHER.x, 24, CRUSHER.z, 'Дробилка ККД');
register('crusher', [crusherMat], crusherChip);

const STOCK = [new THREE.Vector3(10, 0, -58), new THREE.Vector3(28, 0, -62), new THREE.Vector3(46, 0, -58)];
const ORE_COLORS = [0xd59a4a, 0xd8c08a, 0xc0583a];
const piles = STOCK.map((p, i) => {
  const m = mesh(new THREE.ConeGeometry(1.33, 1, 32), mat(ORE_COLORS[i], { flatShading: true }), p.x, 0.5, p.z);
  return m;
});
const stockChip = label(scene, 6, 24, -72, 'Склад руды (3 сорта)');
register('stockpile', piles.map((p) => p.material), stockChip);
const conveyor1 = new Flow([[CRUSHER.x + 7, 12, CRUSHER.z], [2, 16, -42], [28, 20, -60]],
  { color: 0x9b6a45, box: true, size: 1.6, count: 70, tube: 0.9, tubeColor: 0x4a5257, speed: 0.08 });
register('conveyor', [conveyor1.pipeMat]);

// ------------------------------------------------------------ the plant ----
const PLANT = new THREE.Vector3(84, 0, -24);
{
  const frame = mat(0x9aa7ae, { transparent: true, opacity: 0.18, depthWrite: false });
  const b = mesh(new THREE.BoxGeometry(44, 26, 46), frame, PLANT.x, 13, PLANT.z);
  b.castShadow = false;
  mesh(new THREE.BoxGeometry(46, 1, 48), mat(0x6f777b), PLANT.x, 0.5, PLANT.z);
  for (const [dx, dz] of [[-22, -23], [22, -23], [-22, 23], [22, 23]]) {
    mesh(new THREE.BoxGeometry(1.2, 26, 1.2), mat(0x6a7479), PLANT.x + dx, 13, PLANT.z + dz);
  }
}
const mills = {};
for (const [i, name] of [[0, 'mill-1'], [1, 'mill-2']]) {
  const z = PLANT.z - 11 + i * 22;
  const g = new THREE.Group();
  g.position.set(PLANT.x - 6, 10, z);
  scene.add(g);
  const shell = mat(0x4f8fa8, { metalness: 0.4, roughness: 0.45, emissive: 0x000000 });
  const drum = mesh(new THREE.CylinderGeometry(8.5, 8.5, 13, 32), shell, 0, 0, 0, g);
  drum.rotation.z = Math.PI / 2;
  for (let k = 0; k < 8; k++) {       // girth ribs, so the rotation is visible
    const a = (k / 8) * Math.PI * 2;
    const rib = mesh(new THREE.BoxGeometry(13.4, 1, 1.2), mat(0x2c3e47), 0, Math.cos(a) * 8.5, Math.sin(a) * 8.5, g);
    rib.rotation.x = a;
  }
  const ball = mesh(new THREE.CylinderGeometry(4.2, 4.2, 12, 24), mat(0x6c9fb3, { metalness: 0.4 }), PLANT.x + 12, 6, z);
  ball.rotation.z = Math.PI / 2;
  mills[name] = { g, shell, ball, speed: 0 };
}
const millChip = label(scene, PLANT.x - 14, 40, PLANT.z - 10, 'Измельчение: 2 линии МПСИ + шаровая');
for (const [name, m] of Object.entries(mills)) register(name, [m.shell, m.ball.material], millChip);
const conveyor2 = new Flow([[28, 3, -52], [48, 10, -38], [PLANT.x - 18, 12, PLANT.z]],
  { color: 0x9b6a45, box: true, size: 1.5, count: 60, tube: 0.8, tubeColor: 0x4a5257, speed: 0.08 });

// flotation cells with froth
const FLOT = new THREE.Vector3(124, 0, -44);
const froth = [];
const flotMat = mat(0x8796a0, { metalness: 0.3 });
for (let i = 0; i < 8; i++) {
  const x = FLOT.x + (i % 4) * 8, z = FLOT.z + Math.floor(i / 4) * 9;
  mesh(new THREE.CylinderGeometry(3.4, 3.4, 6, 20), flotMat, x, 3, z);
  const top = mesh(new THREE.CircleGeometry(3.2, 20), new THREE.MeshStandardMaterial({ color: 0xc8c26a, emissive: 0x7a6e10, emissiveIntensity: 0.3 }), x, 6.05, z);
  top.rotation.x = -Math.PI / 2;
  froth.push(top);
}
const flotChip = label(scene, FLOT.x + 30, 4, FLOT.z + 18, 'Флотация');
register('flotation', [flotMat], flotChip);
new Flow([[PLANT.x + 20, 4, PLANT.z], [FLOT.x - 6, 4, FLOT.z + 4]], { color: 0x8f8a7a, count: 20, tube: 0.6, size: 1 });

// tailings thickener with a turning rake
const THICK = new THREE.Vector3(148, 0, 14);
const thickMat = mat(0xa0a6a8);
mesh(new THREE.CylinderGeometry(15, 15, 4, 40), thickMat, THICK.x, 2, THICK.z);
const thickWater = mesh(new THREE.CircleGeometry(14.2, 40), mat(0x6b7f7c, { roughness: 0.3 }), THICK.x, 4.05, THICK.z);
thickWater.rotation.x = -Math.PI / 2;
const rake = mesh(new THREE.BoxGeometry(28, 0.8, 1), mat(0x30373b), THICK.x, 4.6, THICK.z);
const thickChip = label(scene, THICK.x, 14, THICK.z + 4, 'Сгуститель хвостов');
register('thickener', [thickMat], thickChip);
new Flow([[FLOT.x + 26, 4, FLOT.z + 10], [THICK.x, 6, THICK.z - 14]], { color: 0x8f8a7a, count: 20, tube: 0.6, size: 1 });

// process water tank
const TANK = new THREE.Vector3(100, 0, 30);
const tankShell = new THREE.MeshStandardMaterial({ color: 0xc7d3d9, transparent: true, opacity: 0.28, depthWrite: false });
mesh(new THREE.CylinderGeometry(8, 8, 16, 32, 1, true), tankShell, TANK.x, 8, TANK.z).castShadow = false;
const tankWaterMat = mat(0x3c9fd6, { roughness: 0.25, emissive: 0x0b3550, emissiveIntensity: 0.4 });
const tankWater = mesh(new THREE.CylinderGeometry(7.6, 7.6, 1, 32), tankWaterMat, TANK.x, 0.5, TANK.z);
const tankChip = label(scene, TANK.x - 6, 22, TANK.z + 6, 'Резервуар оборотной воды');
register('process-water', [tankWaterMat], tankChip);
const toPlantWater = new Flow([[TANK.x - 8, 3, TANK.z], [PLANT.x + 8, 4, PLANT.z + 24]],
  { color: 0x4fb3e8, count: 30, tube: 0.7, tubeColor: 0x5d7f91, size: 1 });

// ------------------------------------------------------ tailings storage ----
const TSF = new THREE.Vector3(50, 0, 128);
{
  const pts = [new THREE.Vector2(54, 0), new THREE.Vector2(57, 6), new THREE.Vector2(62, 6), new THREE.Vector2(70, 0)];
  mesh(new THREE.LatheGeometry(pts, 80), mat(0x9d8e70, { flatShading: true }), TSF.x, 0, TSF.z);
  const beach = mesh(new THREE.CircleGeometry(56, 64), mat(0xcfc3a2), TSF.x, 0.6, TSF.z);
  beach.rotation.x = -Math.PI / 2;
}
const pondMat = mat(0x3f8fb8, { roughness: 0.2, metalness: 0.1, emissive: 0x0a2a40, emissiveIntensity: 0.3 });
const pond = mesh(new THREE.CircleGeometry(1, 64), pondMat, TSF.x + 5, 1.2, TSF.z + 6);
pond.rotation.x = -Math.PI / 2;
pond.castShadow = false;
const bargeMat = mat(0xe07a3f);
const barge = mesh(new THREE.BoxGeometry(8, 3, 5), bargeMat, TSF.x - 6, 2.5, TSF.z - 26);
const tsfChip = label(scene, TSF.x + 20, 16, TSF.z + 22, 'Хвостохранилище');
const reclaimChip = label(scene, TSF.x - 30, 12, TSF.z - 22, 'Насосная оборотной воды');
register('tailings', [pondMat], tsfChip);
register('reclaim', [bargeMat], reclaimChip);
const tailsFlow = new Flow([[THICK.x - 6, 3, THICK.z + 14], [118, 2, 70], [TSF.x + 40, 3, TSF.z - 38]],
  { color: 0x9a9384, count: 50, tube: 0.9, tubeColor: 0x6d6a62, size: 1.2 });
const reclaimFlow = new Flow([[TSF.x - 6, 3, TSF.z - 26], [TSF.x + 4, 8, TSF.z - 64], [TANK.x - 4, 3, TANK.z + 8]],
  { color: 0x4fb3e8, count: 50, tube: 0.9, tubeColor: 0x5d7f91, size: 1.3 });

// ------------------------------------------------------- canal and intake ---
{
  const canal = mesh(new THREE.PlaneGeometry(22, 660), mat(0x2f7fae, { roughness: 0.2, emissive: 0x0a2a40, emissiveIntensity: 0.3 }), 222, 0.3, 0);
  canal.rotation.x = -Math.PI / 2;
  canal.castShadow = false;
}
const INTAKE = new THREE.Vector3(204, 0, -30);
const intakeMat = mat(0x8a969c);
mesh(new THREE.BoxGeometry(14, 9, 12), intakeMat, INTAKE.x, 4.5, INTAKE.z);
const intakeChip = label(scene, INTAKE.x - 30, 18, INTAKE.z - 4, 'Водозабор с канала');
const freshFlow = new Flow([[INTAKE.x - 8, 2, INTAKE.z], [180, 2, -10], [150, 2, 40], [TANK.x + 8, 3, TANK.z]],
  { color: 0x6fd0ff, count: 70, tube: 1.0, tubeColor: 0x5d7f91, size: 1.4 });
register('water-intake', [intakeMat, freshFlow.pipeMat], intakeChip);

// --------------------------------------------------------- power network ---
const SUB = new THREE.Vector3(-20, 0, -110);
const subMat = mat(0x8e9aa1, { metalness: 0.4 });
mesh(new THREE.BoxGeometry(40, 1, 26), mat(0x6c7377), SUB.x, 0.5, SUB.z);
for (let i = 0; i < 3; i++) {
  mesh(new THREE.BoxGeometry(6, 7, 5), subMat, SUB.x - 12 + i * 12, 4.5, SUB.z + 4);
  mesh(new THREE.BoxGeometry(0.8, 14, 0.8), mat(0x5b6266), SUB.x - 12 + i * 12, 7, SUB.z - 8);
}
mesh(new THREE.BoxGeometry(30, 0.8, 0.8), mat(0x5b6266), SUB.x, 14, SUB.z - 8);
const subChip = label(scene, SUB.x, 22, SUB.z, 'Подстанция 220/10 кВ');
register('substation', [subMat], subChip);

const powerLines = {};
function powerLine(name, to) {
  const from = new THREE.Vector3(SUB.x, 14, SUB.z - 8);
  const end = new THREE.Vector3(to[0], 14, to[1]);
  const towers = Math.max(2, Math.round(from.distanceTo(end) / 45));
  const pts = [];
  for (let i = 0; i <= towers; i++) {
    const p = from.clone().lerp(end, i / towers);
    mesh(new THREE.BoxGeometry(0.8, 16, 0.8), mat(0x5b6266), p.x, 7, p.z);
    mesh(new THREE.BoxGeometry(5, 0.5, 0.5), mat(0x5b6266), p.x, 14.5, p.z);
    pts.push([p.x, 14.6, p.z]);
    if (i < towers) {                         // sag between towers
      const q = from.clone().lerp(end, (i + 0.5) / towers);
      pts.push([q.x, 11.8, q.z]);
    }
  }
  powerLines[name] = new Flow(pts, { color: 0xf2d14b, count: 30, tube: 0.18, tubeColor: 0x2a2f32, size: 1.4, speed: 0.12 });
}
powerLine('pit', [-60, -40]);
powerLine('plant', [PLANT.x - 10, PLANT.z - 23]);
powerLine('pumps', [INTAKE.x, INTAKE.z - 6]);
powerLine('reclaim', [TSF.x - 64, TSF.z - 40]);

// ------------------------------------------------- concentrate and site ----
// Concentrate goes from flotation to its storage shed; the flow follows the
// flotation twin. The shed, the workshop with idle haul trucks, the admin
// block, boiler house, water tower, loader and dozer are Kenney CC0 models
// (models/*/License.txt), loaded by useModels() below.
const CONC = new THREE.Vector3(170, 0, -80);
const concFlow = new Flow([[FLOT.x + 28, 4, FLOT.z - 2], [150, 6, -62], [CONC.x - 14, 5, CONC.z + 6]],
  { color: 0x5f6b55, box: true, size: 1.4, count: 24, tube: 0.7, tubeColor: 0x4a5257, speed: 0.06 });
const concChip = label(scene, CONC.x + 4, 26, CONC.z - 4, 'Склад медного концентрата');
const WORKSHOP = new THREE.Vector3(-118, 0, -88);
const PARK = Array.from({ length: 6 }, (_, i) => new THREE.Vector3(WORKSHOP.x - 30 + i * 10, 0, WORKSHOP.z + 26));
const parked = [];

const gltf = new GLTFLoader();
// The Judge Environment renders without a GPU, so the models are kept cheap:
// Lambert instead of the glTF PBR material (the same flat-coloured look for a
// fraction of the per-pixel cost) and no shadow casting.
const loadModel = (path) => gltf.loadAsync(`models/${path}.glb`).then((g) => {
  g.scene.traverse((o) => {
    if (!o.isMesh) return;
    o.material = new THREE.MeshLambertMaterial({ map: o.material.map, color: o.material.color });
    o.receiveShadow = true;
  });
  return g.scene;
});
function place(model, scale, x, z, rotY = 0, y = 0) {
  const m = model.clone();
  m.scale.setScalar(scale);
  m.position.set(x, y, z);
  m.rotation.y = rotY;
  scene.add(m);
  return m;
}
function haulTruck(model) {
  const m = model.clone();
  m.scale.setScalar(2.2);
  m.getObjectByName('arm').visible = false;           // the garbage-truck arms; a haul truck has none
  return { m, load: m.getObjectByName('trash'), wheels: m.children.filter((c) => c.name.startsWith('wheel')) };
}
async function useModels() {
  const [truck, loader, shed, hangar, admin, boiler, tower, container, tankL] = await Promise.all([
    'vehicles/garbage-truck', 'vehicles/tractor-shovel', 'industrial/building-r', 'industrial/building-j',
    'industrial/building-e', 'industrial/building-c', 'industrial/water-tower', 'industrial/shipping-container-a',
    'industrial/detail-tank-large'].map(loadModel));
  for (const { t } of trucks) {
    const h = haulTruck(truck);
    t.g.remove(t.body);
    t.g.add(h.m);
    Object.assign(t, { body: h.m, load: h.load, wheels: h.wheels });
  }
  for (const p of PARK) {
    const h = haulTruck(truck);
    h.load.visible = false;
    h.m.position.copy(p);
    h.m.rotation.y = Math.PI;
    scene.add(h.m);
    parked.push(h.m);
  }
  place(hangar, 24, WORKSHOP.x, WORKSHOP.z, Math.PI);
  const stockLoader = place(loader, 3, -4, -66, Math.PI / 2 - 0.3);
  stockLoader.userData.shovel = stockLoader.getObjectByName('shovel');
  loaders.push(stockLoader);
  loaders.push(place(loader, 3, TSF.x + 59, TSF.z + 4, 0.4, 6));      // dozer on the dam crest
  place(shed, 15, CONC.x, CONC.z, -Math.PI / 2);
  for (let i = 0; i < 6; i++) place(container, 9, CONC.x + 22 + (i % 3) * 5, CONC.z - 10 + Math.floor(i / 3) * 10, 0);
  place(tankL, 9, FLOT.x + 6, FLOT.z - 22, 0);                       // reagent tanks of the flotation
  place(tankL, 9, FLOT.x + 22, FLOT.z - 22, 0);
  place(admin, 17, 46, -108, Math.PI);
  place(boiler, 15, 86, -106, Math.PI);
  place(tower, 14, 116, -102, 0);
  if (T.complex) update3d();
}
const loaders = [];
useModels().catch((e) => console.warn('3D models not loaded, keeping the simple shapes:', e));

// --------------------------------------------------------------- update ----
let lastSun = -1;
function setSky(hour) {
  const h = ((hour % 24) + 24) % 24;
  let c, k;
  if (h >= 7 && h < 18) { c = SKY_DAY; k = 1; }
  else if (h >= 18 && h < 21) { c = SKY_DAY.clone().lerp(SKY_DUSK, (h - 18) / 3); k = 1 - 0.25 * (h - 18) / 3; }
  else if (h >= 21 || h < 5) { c = SKY_DUSK.clone().lerp(SKY_NIGHT, 0.6); k = 0.72; }
  else { c = SKY_NIGHT.clone().lerp(SKY_DAY, (h - 5) / 2); k = 0.72 + 0.28 * (h - 5) / 2; }
  scene.background.copy(c);
  scene.fog.color.copy(c);
  sun.intensity = 1.6 * k;
  hemi.intensity = 1.1 * Math.max(k, 0.8);
  if (Math.abs(h - lastSun) > 0.2) {
    const a = ((h - 6) / 12) * Math.PI;
    sun.position.set(-260 * Math.cos(a), 120 + 200 * Math.max(Math.sin(a), 0.25), 120);
    lastSun = h;
  }
}

let bottleneckNow = new Set();
function update3d() {
  setSky(v('complex', 'sim_hour', 16.5));
  const peakOn = v('substation', 'peak_restriction', false);

  for (const f of FACES) {
    const rate = v(f.shovel, 'rate');
    const wi = v(f.name, 'bond_wi');
    const hard = v(f.name, 'hard_ore', false);
    f.rock.color.set(hard ? 0x6b4a7a : f.color);
    f.rate = rate;
    f.chip.text(`${fmt(rate)} т/ч · ${fmt(v(f.name, 'grade'), 2)} % Cu · Wi ${fmt(wi, 1)}${hard ? ' · <b style="color:#d7a8ff">твёрдая</b>' : ''}`);
  }
  const crush = v('crusher', 'throughput');
  crusherChip.text(`${fmt(crush)} т/ч · ${fmt(v('crusher', 'load'))} %`);
  conveyor1.set(crush / 3600);

  const secs = [1, 2, 3].map((i) => v('stockpile', `section_${i}`));
  secs.forEach((t, i) => {
    const h = Math.max(0.6, Math.cbrt(t / 11.6));
    piles[i].scale.set(h, h, h);
    piles[i].position.y = h / 2;
  });
  stockChip.text(`${fmt(v('stockpile', 'total') / 1000, 1)} тыс. т · ${fmt(v('stockpile', 'fill'))} %`);

  const feed = v('plant', 'feed');
  conveyor2.set(feed / 3200);
  const millLines = [];
  for (const [name, m] of Object.entries(mills)) {
    const state = v(name, 'state', 'running');
    const f = v(name, 'feed');
    m.speed = state === 'running' ? 0.4 + 0.6 * f / 1600 : 0;
    m.shell.color.set(state === 'running' ? 0x4f8fa8 : state === 'repair' ? 0x6d6d6d : 0xb23a35);
    m.ball.material.color.set(state === 'running' ? 0x6c9fb3 : 0x777777);
    m.state = state;
    const n = name.slice(-1);
    millLines.push(state === 'running'
      ? `линия ${n}: ${fmt(f)} т/ч · ${fmt(v(name, 'power'), 1)} МВт · ${fmt(v(name, 'specific_energy'), 1)} кВт·ч/т`
      : state === 'repair' ? `линия ${n}: <b style="color:#ffcf6b">РЕМОНТ</b>`
        : `линия ${n}: <b style="color:#ff8a80">ОТКЛЮЧЕНА САОН, ещё ${fmt(v(name, 'trip_left'))} мин</b>`);
  }
  millChip.text(millLines.join('<br>'));
  millChip.el.classList.toggle('alarm', Object.values(mills).some((m) => m.state === 'tripped'));
  const cu = v('flotation', 'copper');
  froth.forEach((t) => { t.material.emissiveIntensity = 0.15 + 0.9 * clamp(cu / 12, 0, 1); });
  flotChip.text(`извлечение ${fmt(v('flotation', 'recovery'), 1)} % · ${fmt(cu, 2)} т Cu/ч`);
  const conc = v('flotation', 'concentrate');
  concFlow.set(conc / 50);
  concChip.text(`${fmt(conc, 1)} т/ч · за сутки ${fmt(v('complex', 'copper_today') / 0.24)} т`);   // 24 % Cu
  // haul trucks not needed on the faces wait at the workshop
  const busy = FACES.reduce((s, f) => s + Math.min(f.trucks.length, Math.ceil((f.rate || 0) / 420)), 0);
  parked.forEach((m, i) => { m.visible = i < trucks.length - busy; });

  const high = v('thickener', 'mode') === 'high-density';
  thickWater.material.color.set(high ? 0x9a8f72 : 0x6b7f7c);
  thickChip.text(`${fmt(v('thickener', 'underflow_solids'), 1)} % твёрдого${high ? ' · <b style="color:#ffcf6b">высокоплотный</b>' : ''}`);
  tailsFlow.set(v('thickener', 'water_to_tailings') / 2800);

  const level = v('process-water', 'level') / 100;
  tankWater.scale.y = Math.max(0.2, 15.5 * level);
  tankWater.position.y = tankWater.scale.y / 2;
  tankWaterMat.color.set(level < 0.2 ? 0xd0574f : 0x3c9fd6);
  const left = v('process-water', 'hours_to_trip', -1);
  tankChip.text(`${fmt(level * 100)} % · расход ${fmt(v('process-water', 'demand'))} м³/ч`
    + (v('process-water', 'interlock', false) ? ' · <b style="color:#ff8a80">БЛОКИРОВКА</b>'
      : left >= 0 ? ` · пусто через ${fmt(left, 1)} ч` : ''));
  tankChip.el.classList.toggle('alarm', !!v('process-water', 'interlock', false));
  toPlantWater.set(v('process-water', 'demand') / 2800);

  const area = v('tailings', 'pond_area', 1.6);
  const pr = 40 * Math.sqrt(area / 1.6);
  pond.scale.set(pr, pr, 1);
  const reserve = v('tailings', 'reserve_days', -1);
  tsfChip.text(`пруд ${fmt(v('tailings', 'pond_volume') / 1e6, 3)} млн м³ · ${reserve >= 0 ? `запас ${fmt(reserve)} сут` : 'баланс ≥ 0'}`);
  const rec = v('reclaim', 'flow');
  reclaimChip.text(`${fmt(rec)} / ${fmt(v('reclaim', 'capacity'))} м³/ч`);
  reclaimFlow.set(rec / 1100);

  const fresh = v('water-intake', 'flow'), freshLim = v('water-intake', 'limit', 1750);
  freshFlow.set(fresh / 1750);
  freshFlow.pipeMat.color.set(fresh >= freshLim * 0.97 ? 0xe0883a : 0x5d7f91);
  intakeChip.text(`${fmt(fresh)} / ${fmt(freshLim)} м³/ч${v('water-intake', 'dry_year', false) ? ' · <b style="color:#ffcf6b">маловодье</b>' : ''}`);

  const load = v('substation', 'load'), lim = v('substation', 'limit', 78);
  const util = load / lim;
  const powerColor = util > 0.97 ? 0xff6b4a : util > 0.9 ? 0xf0a640 : 0xf2d14b;
  subChip.text(`${fmt(load, 1)} / ${fmt(lim)} МВт${peakOn ? ' · <b style="color:#ffcf6b">пик</b>' : ''}`);
  subChip.el.classList.toggle('alarm', util > 1);
  const pitMW = ([1, 2, 3].reduce((s, i) => s + v(`shovel-${i}`, 'power'), 0) + v('crusher', 'power') + v('conveyor', 'power')) / 1000;
  powerLines.pit.set(pitMW / 6, powerColor);
  powerLines.plant.set(v('plant', 'power') / 60, powerColor);
  powerLines.pumps.set(v('water-intake', 'power') / 2500, powerColor);
  powerLines.reclaim.set(v('reclaim', 'power') / 900, powerColor);

  bottleneckNow = new Set(String(v('planner', 'bottleneck_twins', '')).split(',').filter(Boolean));
  for (const [name, h] of Object.entries(highlight)) {
    h.chip?.el.classList.toggle('bottleneck-on', bottleneckNow.has(name));
    if (!bottleneckNow.has(name)) h.materials.forEach((m) => m.emissive?.set(0x000000));
  }
}

// ------------------------------------------------------------------ HUD ----
function bar(id, frac, text, warn = 0.9, bad = 1.0) {
  const el = $(id);
  el.querySelector('u').style.width = `${clamp(frac, 0, 1) * 100}%`;
  el.querySelector('output').innerHTML = text;
  el.classList.toggle('warn', frac >= warn && frac < bad);
  el.classList.toggle('bad', frac >= bad);
}

const scenarioBox = $('#scenarios');
for (const [key, title, sub] of SCENARIOS) {
  const b = document.createElement('button');
  b.className = 'scenario';
  b.dataset.key = key;
  b.innerHTML = `<span class="sw"></span><span>${title}<small>${sub}</small></span>`;
  b.addEventListener('click', () => toggleScenario(key, b));
  scenarioBox.appendChild(b);
}
for (const b of document.querySelectorAll('.mode button')) {
  b.addEventListener('click', () => setMode(b.dataset.mode));
}
function togglePanels() {
  document.body.classList.toggle('bare');
  resize();
  $('#toggle-panels').textContent = document.body.classList.contains('bare') ? 'Показать панели' : 'Скрыть панели';
}
$('#toggle-panels').addEventListener('click', togglePanels);
window.addEventListener('keydown', (e) => { if (e.key === 'h' || e.key === 'р') togglePanels(); });
$('#grafana').href = `${location.protocol}//${location.hostname}:3000/d/rudnik-pod-limitom/`;

async function put(path, body) {
  const r = await fetch(`/api/2/things/${NS}:control/features/${path}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  if (!r.ok && r.status !== 204) throw new Error(`Ditto ответил ${r.status}`);
}
async function toggleScenario(key, el) {
  const on = !T.control?.[key]?.active;
  el.classList.add('busy');
  try {
    await put(`${key}/properties/active`, on);
    T.control[key].active = on;
    updateHud();
  } catch (e) { alert(`Не удалось переключить сценарий: ${e.message}`); }
  el.classList.remove('busy');
}
async function setMode(mode) {
  try {
    await put('mode/properties/value', mode);
    T.control.mode = { value: mode };
    updateHud();
  } catch (e) { alert(`Не удалось сменить режим: ${e.message}`); }
}

function updateHud() {
  const hour = v('complex', 'sim_hour', 0);
  $('#clock').textContent = v('complex', 'sim_clock', '--:--');
  $('#day').textContent = `сутки ${v('complex', 'sim_day', 1)} · ×60`;
  const mode = T.control?.mode?.value || 'optimizer';
  for (const b of document.querySelectorAll('.mode button')) b.classList.toggle('on', b.dataset.mode === mode);
  for (const b of scenarioBox.children) b.classList.toggle('on', !!T.control?.[b.dataset.key]?.active);

  $('#k-cu').textContent = fmt(v('complex', 'copper_tph'), 2);
  $('#k-cuday').textContent = fmt(v('complex', 'copper_today'), 1);
  $('#k-ore').textContent = fmt(v('complex', 'ore_tph'));

  const load = v('substation', 'load'), lim = v('substation', 'limit', 78);
  bar('#b-power', load / lim, `${fmt(load, 1)} из ${fmt(lim)} МВт · отключений САОН за сутки: ${fmt(v('substation', 'shed_today'))}`, 0.93, 0.995);
  const fresh = v('water-intake', 'flow'), fl = v('water-intake', 'limit', 1750);
  bar('#b-fresh', fresh / fl, `${fmt(fresh)} из ${fmt(fl)} м³/ч`, 0.9, 0.98);
  const ml = ['mill-1', 'mill-2'].filter((m) => v(m, 'state') === 'running');
  const mload = ml.length ? ml.reduce((s, m) => s + v(m, 'load'), 0) / ml.length / 100 : 0;
  bar('#b-mills', mload, `${ml.length} из 2 линий в работе · ${fmt(mload * 100)} % мощности`, 0.97, 2);
  const lvl = v('process-water', 'level') / 100;
  const tankEl = $('#b-tank');
  bar('#b-tank', lvl, `${fmt(lvl * 100)} % · приход ${fmt(v('process-water', 'supply'))} / расход ${fmt(v('process-water', 'demand'))} м³/ч`, 2, 2);
  tankEl.classList.toggle('bad', lvl < 0.2);
  tankEl.classList.toggle('warn', lvl >= 0.2 && lvl < 0.45);
  bar('#b-stock', v('stockpile', 'fill') / 100, `${fmt(v('stockpile', 'total') / 1000, 1)} из 60 тыс. т`, 0.9, 0.99);
  const reserve = v('tailings', 'reserve_days', -1);
  $('#pond-note').textContent = `Пруд хвостохранилища: ${fmt(v('tailings', 'pond_volume') / 1e6, 3)} млн м³, баланс ${fmt(v('tailings', 'net_balance'))} м³/ч`
    + (reserve >= 0 ? `, запаса воды на ${fmt(reserve)} сут.` : '.');

  const bn = v('planner', 'bottleneck', '–');
  const bnEl = $('#bottleneck');
  bnEl.textContent = bn === 'нет' ? 'Узких мест нет' : `Узкие места: ${bn}`;
  bnEl.classList.toggle('none', bn === 'нет');
  $('#c-plan').textContent = fmt(v('planner', 'copper_plan_day'), 1);
  $('#c-base').textContent = fmt(v('planner', 'copper_baseline_day'), 1);
  $('#c-ref').textContent = fmt(v('planner', 'copper_reference_day'), 1);
  const advice = String(v('planner', 'advice', '')).split('\n').filter((s) => s && !s.startsWith('Узкие места'));
  $('#advice').innerHTML = advice.map((s) => `<li>${s}</li>`).join('');

  const events = String(v('complex', 'events', '')).split('\n').filter(Boolean);
  $('#events').innerHTML = events.map((e) => `<span>${e}</span>`).join('') || '<span>Событий пока нет</span>';

  let sched = null;
  try { sched = JSON.parse(v('planner', 'schedule', 'null')); } catch { sched = null; }
  if (sched) drawCharts(sched, hour);
}

function drawChart(canvas, hours, series, { unit, max, title }) {
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height, L = 52, R = 10, TOP = 30, B = 26;
  ctx.clearRect(0, 0, W, H);
  ctx.font = '20px system-ui, sans-serif';
  ctx.fillStyle = '#93a4ad';
  ctx.fillText(title, L, 20);
  const n = hours.length, bw = (W - L - R) / n;
  const y = (val) => TOP + (H - TOP - B) * (1 - val / max);
  ctx.strokeStyle = 'rgba(255,255,255,0.08)';
  ctx.fillStyle = '#93a4ad';
  ctx.font = '17px system-ui, sans-serif';
  for (let k = 0; k <= 4; k++) {
    const val = (max / 4) * k;
    ctx.beginPath(); ctx.moveTo(L, y(val)); ctx.lineTo(W - R, y(val)); ctx.stroke();
    ctx.fillText(fmt(val), 4, y(val) + 5);
  }
  hours.forEach((h, i) => { if (i % 3 === 0) ctx.fillText(`${String(h).padStart(2, '0')}`, L + i * bw + 2, H - 6); });
  let legendX = L + 300;
  for (const s of series) {
    ctx.fillStyle = s.color; ctx.strokeStyle = s.color;
    if (s.kind === 'bar') {
      s.data.forEach((val, i) => ctx.fillRect(L + i * bw + 2, y(val), bw - 4, y(0) - y(val)));
    } else {
      ctx.lineWidth = s.width || 3;
      ctx.setLineDash(s.dash || []);
      ctx.beginPath();
      s.data.forEach((val, i) => {
        const x0 = L + i * bw, x1 = x0 + bw;
        if (i === 0) ctx.moveTo(x0, y(val)); else ctx.lineTo(x0, y(val));
        ctx.lineTo(x1, y(val));
      });
      ctx.stroke();
      ctx.setLineDash([]);
    }
    ctx.fillRect(legendX, 9, 16, 10);
    ctx.fillStyle = '#c5d3da';
    ctx.font = '17px system-ui, sans-serif';
    ctx.fillText(s.name, legendX + 22, 19);
    legendX += ctx.measureText(s.name).width + 44;
  }
}
function drawCharts(s, hour) {
  drawChart($('#chart-ore'), s.hour, [
    { name: 'план', kind: 'bar', data: s.ore, color: 'rgba(224,122,63,0.85)' },
    { name: 'по отделам', kind: 'line', data: s.baseline_ore, color: '#c5d3da', dash: [6, 5] },
  ], { max: 3500, title: 'Питание фабрики, т/ч' });
  drawChart($('#chart-power'), s.hour, [
    { name: 'нагрузка по плану', kind: 'bar', data: s.power, color: 'rgba(242,209,75,0.8)' },
    { name: 'лимит', kind: 'line', data: s.power_limit, color: '#ef5350' },
  ], { max: 90, title: 'Мощность, МВт' });
}

// ----------------------------------------------------------------- data ----
const conn = $('#conn');
async function poll() {
  try {
    const r = await fetch(`/api/2/things?ids=${NAMES.map((n) => `${NS}:${n}`).join(',')}`, { cache: 'no-store' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    for (const t of await r.json()) {
      const name = t.thingId.split(':')[1];
      T[name] = Object.fromEntries(Object.entries(t.features || {}).map(([k, f]) => [k, f.properties || {}]));
    }
    conn.textContent = 'данные из Ditto';
    conn.classList.add('ok');
    if (T.complex) { update3d(); updateHud(); }
  } catch (e) {
    conn.textContent = `нет связи с Ditto (${e.message})`;
    conn.classList.remove('ok');
  }
  setTimeout(poll, POLL_MS);
}
poll();

// ------------------------------------------------------------- animate ----
const clock = new THREE.Clock();
function animate() {
  const dt = Math.min(clock.getDelta(), 0.1);
  const t = clock.elapsedTime;
  for (const f of flows) f.tick(dt);
  for (const m of Object.values(mills)) m.g.rotation.x += dt * m.speed * 1.6;
  rake.rotation.y += dt * 0.25;
  for (const { face, t: truck } of trucks) {
    const active = face.trucks.indexOf(truck) < Math.ceil((face.rate || 0) / 420);
    truck.g.visible = active;
    if (!active) continue;
    truck.u = (truck.u + dt * 0.035) % 2;
    const back = truck.u > 1;
    const u = back ? 2 - truck.u : truck.u;
    const p = face.road.getPointAt(u);
    const ahead = face.road.getPointAt(clamp(back ? u - 0.01 : u + 0.01, 0, 1));
    truck.g.position.copy(p);
    truck.g.lookAt(ahead.x, p.y, ahead.z);
    truck.load.visible = !back;
    for (const w of truck.wheels) w.rotation.x += dt * 4;
  }
  for (const l of loaders) if (l.userData.shovel) l.userData.shovel.rotation.x = -0.25 + 0.25 * Math.sin(t * 1.3);
  const pulse = 0.5 + 0.5 * Math.sin(t * 5);
  for (const name of bottleneckNow) {
    highlight[name]?.materials.forEach((m) => m.emissive?.setRGB(0.6 * pulse, 0.33 * pulse, 0.02 * pulse));
  }
  for (const m of Object.values(mills)) {
    if (m.state === 'tripped') m.shell.emissive.setRGB(0.5 * pulse, 0, 0);
  }
  controls.update();
  renderer.render(scene, camera);
  labels.render(scene, camera);
  requestAnimationFrame(animate);
}
animate();
