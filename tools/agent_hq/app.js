// Agent HQ office. Polls /state every 3 seconds and draws a tower with one
// floor per team, one desk and one robot per bot. Talks only to this server.
import * as THREE from './vendor/three.module.js';

const REFRESH_MS = 3000;
const DESK_X = 2.9;
const FLOOR_H = 4.1;
const FLOOR_D = 4.8;
const STATUS = {
  working: { color: 0x38bdf8, text: 'working' },
  waiting: { color: 0xf59e0b, text: 'waiting on me' },
  stuck: { color: 0xef4444, text: 'stuck' },
  resting: { color: 0x64748b, text: 'resting' },
};
const TEAM_COLORS = { Research: 0x818cf8, Content: 0xf472b6, Visuals: 0x34d399, Ops: 0xfb923c, Unassigned: 0x94a3b8 };
const MODEL_COLORS = [['opus', '#a78bfa'], ['sonnet', '#60a5fa'], ['haiku', '#34d399'], ['fable', '#f472b6'], ['mythos', '#f472b6']];
const FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, sans-serif';

const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------- renderer

const canvas = $('scene');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0b1020);
scene.fog = new THREE.Fog(0x0b1020, 40, 120);
const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 300);

scene.add(new THREE.HemisphereLight(0xc7d7ff, 0x1a1f33, 1.1));
const sun = new THREE.DirectionalLight(0xffffff, 1.6);
sun.position.set(8, 14, 10);
scene.add(sun);
const fill = new THREE.DirectionalLight(0x8fb3ff, 0.5);
fill.position.set(-10, 6, -6);
scene.add(fill);

const ground = new THREE.Mesh(new THREE.CircleGeometry(60, 64), new THREE.MeshStandardMaterial({ color: 0x0e1528, roughness: 1 }));
ground.rotation.x = -Math.PI / 2;
ground.position.y = -0.4;
scene.add(ground);
const grid = new THREE.GridHelper(80, 40, 0x1f2a44, 0x16203a);
grid.position.y = -0.39;
scene.add(grid);

// ---------------------------------------------------------------- orbit

class Orbit {
  constructor(cam, dom) {
    this.camera = cam; this.dom = dom;
    this.target = new THREE.Vector3(0, 4, 0);
    this.theta = 0.36; this.phi = 1.41; this.radius = 24;
    this.min = 4; this.max = 140;
    this.pointers = new Map(); this.pinch = 0; this.moved = 0;
    dom.addEventListener('pointerdown', (e) => this.down(e));
    dom.addEventListener('pointermove', (e) => this.move(e));
    dom.addEventListener('pointerup', (e) => this.up(e));
    dom.addEventListener('pointercancel', (e) => this.up(e));
    dom.addEventListener('wheel', (e) => { e.preventDefault(); this.zoom(Math.exp(e.deltaY * 0.0012)); }, { passive: false });
    dom.addEventListener('contextmenu', (e) => e.preventDefault());
  }
  down(e) { this.dom.setPointerCapture(e.pointerId); this.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY }); this.moved = 0; this.pinch = this.span(); }
  move(e) {
    const p = this.pointers.get(e.pointerId); if (!p) return;
    const dx = e.clientX - p.x, dy = e.clientY - p.y; p.x = e.clientX; p.y = e.clientY;
    this.moved += Math.abs(dx) + Math.abs(dy);
    if (this.pointers.size === 1) {
      if (e.buttons === 2 || e.shiftKey) { this.pan(dx, dy); } else { this.theta -= dx * 0.006; this.phi = clamp(this.phi - dy * 0.006, 0.12, 1.52); }
    } else if (this.pointers.size === 2) {
      const s = this.span(); if (this.pinch > 0 && s > 0) this.zoom(this.pinch / s); this.pinch = s;
      this.pan(dx * 0.5, dy * 0.5);
    }
  }
  up(e) { this.pointers.delete(e.pointerId); this.pinch = this.span(); if (this.moved < 6) onTap(e); }
  span() { const a = [...this.pointers.values()]; return a.length < 2 ? 0 : Math.hypot(a[0].x - a[1].x, a[0].y - a[1].y); }
  zoom(f) { this.radius = clamp(this.radius * f, this.min, this.max); }
  pan(dx, dy) {
    const k = this.radius * 0.0012;
    const right = new THREE.Vector3().setFromMatrixColumn(this.camera.matrix, 0);
    this.target.addScaledVector(right, -dx * k);
    this.target.y = clamp(this.target.y + dy * k, -2, 60);
  }
  update() {
    const sp = Math.sin(this.phi);
    this.camera.position.set(
      this.target.x + this.radius * sp * Math.sin(this.theta),
      this.target.y + this.radius * Math.cos(this.phi),
      this.target.z + this.radius * sp * Math.cos(this.theta));
    this.camera.lookAt(this.target);
  }
}
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const orbit = new Orbit(camera, canvas);

// ---------------------------------------------------------------- labels

function textTexture(lines, opts = {}) {
  const c = document.createElement('canvas');
  const ctx = c.getContext('2d');
  const size = opts.size || 40, pad = opts.pad == null ? 22 : opts.pad, gap = 1.25;
  let w = 0;
  for (const l of lines) { ctx.font = `${l.weight || 600} ${size * (l.scale || 1)}px ${FONT}`; w = Math.max(w, ctx.measureText(l.text).width); }
  c.width = Math.ceil(w + pad * 2);
  c.height = Math.ceil(lines.reduce((h, l) => h + size * (l.scale || 1) * gap, 0) + pad * 2);
  if (opts.bg) { ctx.fillStyle = opts.bg; roundRect(ctx, 0, 0, c.width, c.height, opts.radius == null ? 18 : opts.radius); ctx.fill(); }
  if (opts.border) { ctx.strokeStyle = opts.border; ctx.lineWidth = 4; roundRect(ctx, 2, 2, c.width - 4, c.height - 4, 16); ctx.stroke(); }
  let y = pad;
  for (const l of lines) {
    const fs = size * (l.scale || 1);
    ctx.font = `${l.weight || 600} ${fs}px ${FONT}`;
    ctx.fillStyle = l.color || '#e2e8f0';
    ctx.textBaseline = 'top';
    ctx.textAlign = opts.align || 'center';
    ctx.fillText(l.text, opts.align === 'left' ? pad : c.width / 2, y + fs * 0.12);
    y += fs * gap;
  }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  return { tex, aspect: c.width / c.height };
}
function roundRect(ctx, x, y, w, h, r) {
  r = Math.min(r, w / 2, h / 2);
  ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}
function makeSprite(height) {
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ transparent: true, depthWrite: false }));
  s.userData.height = height; s.userData.key = null;
  return s;
}
function setSprite(sprite, lines, opts) {
  const key = JSON.stringify([lines, opts]);
  if (sprite.userData.key === key) return;
  sprite.userData.key = key;
  const old = sprite.material.map;
  const { tex, aspect } = textTexture(lines, opts);
  sprite.material.map = tex; sprite.material.needsUpdate = true;
  sprite.scale.set(sprite.userData.height * aspect, sprite.userData.height, 1);
  if (old) old.dispose();
}
function setPlaneTexture(mesh, lines, opts) {
  const key = JSON.stringify([lines, opts]);
  if (mesh.userData.key === key) return;
  mesh.userData.key = key;
  const old = mesh.material.map;
  const { tex, aspect } = textTexture(lines, opts);
  mesh.material.map = tex; mesh.material.needsUpdate = true;
  mesh.scale.set(mesh.userData.height * aspect, mesh.userData.height, 1);
  if (old) old.dispose();
}

// ---------------------------------------------------------------- geometry

const G = {
  body: new THREE.CapsuleGeometry(0.27, 0.4, 6, 16),
  head: new THREE.BoxGeometry(0.52, 0.42, 0.48),
  eye: new THREE.BoxGeometry(0.11, 0.12, 0.04),
  mouth: new THREE.BoxGeometry(0.2, 0.03, 0.04),
  arm: new THREE.BoxGeometry(0.11, 0.44, 0.11).translate(0, -0.2, 0),
  hand: new THREE.SphereGeometry(0.08, 10, 10),
  antenna: new THREE.CylinderGeometry(0.02, 0.02, 0.26, 8),
  bulb: new THREE.SphereGeometry(0.07, 12, 12),
  halo: new THREE.TorusGeometry(0.36, 0.035, 10, 40),
  glow: new THREE.SphereGeometry(0.75, 16, 16),
  seat: new THREE.CylinderGeometry(0.3, 0.3, 0.06, 20),
  seatPost: new THREE.CylinderGeometry(0.04, 0.04, 0.4, 8),
  seatBase: new THREE.CylinderGeometry(0.28, 0.28, 0.04, 20),
  deskTop: new THREE.BoxGeometry(1.8, 0.08, 0.86),
  deskLeg: new THREE.BoxGeometry(0.08, 0.72, 0.78),
  monitor: new THREE.BoxGeometry(0.78, 0.46, 0.05),
  screen: new THREE.BoxGeometry(0.7, 0.38, 0.02),
  stand: new THREE.BoxGeometry(0.14, 0.14, 0.14),
  keyboard: new THREE.BoxGeometry(0.56, 0.025, 0.18),
  chip: new THREE.PlaneGeometry(1, 1),
  barBg: new THREE.BoxGeometry(1.5, 0.07, 0.09),
  barFill: new THREE.BoxGeometry(1, 0.08, 0.1).translate(0.5, 0, 0),
};
const M = {
  desk: new THREE.MeshStandardMaterial({ color: 0x27334d, roughness: 0.75, metalness: 0.15 }),
  deskLeg: new THREE.MeshStandardMaterial({ color: 0x1b2437, roughness: 0.8 }),
  monitor: new THREE.MeshStandardMaterial({ color: 0x111827, roughness: 0.5, metalness: 0.4 }),
  dark: new THREE.MeshStandardMaterial({ color: 0x1f2937, roughness: 0.7, metalness: 0.3 }),
  keyboard: new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.9 }),
  barBg: new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.9 }),
  seat: new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.9 }),
  slab: new THREE.MeshStandardMaterial({ color: 0x16213a, roughness: 0.9, metalness: 0.05 }),
  wall: new THREE.MeshStandardMaterial({ color: 0x1b2742, roughness: 0.6, metalness: 0.2, transparent: true, opacity: 0.55, side: THREE.DoubleSide }),
  column: new THREE.MeshStandardMaterial({ color: 0x2a3550, roughness: 0.6, metalness: 0.3 }),
  roof: new THREE.MeshStandardMaterial({ color: 0x1b2742, roughness: 0.7 }),
};

// ---------------------------------------------------------------- bots

const tower = new THREE.Group();
scene.add(tower);
const bots = new Map();   // id -> rig
let signature = '';
let latest = null;
let selectedId = null;

function modelColor(model) {
  const m = String(model || '').toLowerCase();
  for (const [k, c] of MODEL_COLORS) if (m.includes(k)) return c;
  return '#9ca3af';
}
function shortModel(model) {
  let m = String(model || 'unknown');
  m = m.replace(/^claude-/, '');
  return m.length > 16 ? m.slice(0, 15) + '…' : m;
}
function fmtTokens(n) {
  n = Number(n || 0);
  if (n >= 1e6) return (n / 1e6).toFixed(2) + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'k';
  return String(n);
}
function hexCss(c) { return '#' + c.toString(16).padStart(6, '0'); }

function buildBot(bot) {
  const teamColor = TEAM_COLORS[bot.team] ?? 0xa3a3a3;
  const g = new THREE.Group();
  g.userData.botId = bot.id;

  // desk, facing the camera (+z)
  const deskTop = new THREE.Mesh(G.deskTop, M.desk); deskTop.position.set(0, 0.76, 0); g.add(deskTop);
  for (const x of [-0.84, 0.84]) { const leg = new THREE.Mesh(G.deskLeg, M.deskLeg); leg.position.set(x, 0.36, 0); g.add(leg); }
  const stand = new THREE.Mesh(G.stand, M.dark); stand.position.set(-0.25, 0.87, -0.12); g.add(stand);
  const monitor = new THREE.Mesh(G.monitor, M.monitor); monitor.position.set(-0.25, 1.19, -0.12); g.add(monitor);
  const screenMat = new THREE.MeshStandardMaterial({ color: 0x0b1020, emissive: 0x38bdf8, emissiveIntensity: 0.2, roughness: 0.3 });
  const screen = new THREE.Mesh(G.screen, screenMat); screen.position.set(-0.25, 1.19, -0.155); g.add(screen);
  const keyboard = new THREE.Mesh(G.keyboard, M.keyboard); keyboard.position.set(-0.25, 0.815, -0.42); g.add(keyboard);

  // model chip, propped on the right of the desk
  const chip = new THREE.Mesh(G.chip, new THREE.MeshBasicMaterial({ transparent: true, side: THREE.DoubleSide }));
  chip.userData.height = 0.26; chip.position.set(0.5, 0.95, 0.05); chip.rotation.x = -0.35; g.add(chip);

  // token bar along the front edge of the desk
  const barBg = new THREE.Mesh(G.barBg, M.barBg); barBg.position.set(0, 0.83, 0.37); g.add(barBg);
  const barFill = new THREE.Mesh(G.barFill, new THREE.MeshStandardMaterial({ color: 0x38bdf8, emissive: 0x38bdf8, emissiveIntensity: 0.5, roughness: 0.5 }));
  barFill.position.set(-0.75, 0.83, 0.37); barFill.scale.x = 0.001; g.add(barFill);
  const barLabel = makeSprite(0.28); barLabel.position.set(0, 1.08, 0.5); g.add(barLabel);

  // robot behind the desk, facing the camera
  const robot = new THREE.Group(); robot.position.set(0, 0, -0.95); g.add(robot);
  const seatBase = new THREE.Mesh(G.seatBase, M.seat); seatBase.position.y = 0.02; robot.add(seatBase);
  const seatPost = new THREE.Mesh(G.seatPost, M.seat); seatPost.position.y = 0.22; robot.add(seatPost);
  const seat = new THREE.Mesh(G.seat, M.seat); seat.position.y = 0.44; robot.add(seat);
  const bodyMat = new THREE.MeshStandardMaterial({ color: teamColor, emissive: teamColor, emissiveIntensity: 0.05, roughness: 0.45, metalness: 0.25 });
  const body = new THREE.Mesh(G.body, bodyMat); body.position.y = 0.92; robot.add(body);
  const head = new THREE.Mesh(G.head, new THREE.MeshStandardMaterial({ color: 0xe5e7eb, roughness: 0.35, metalness: 0.35 })); head.position.y = 1.52; robot.add(head);
  const eyeMat = new THREE.MeshStandardMaterial({ color: 0x0b1020, emissive: 0x38bdf8, emissiveIntensity: 1.4 });
  const eyes = [-0.13, 0.13].map((x) => { const e = new THREE.Mesh(G.eye, eyeMat); e.position.set(x, 1.56, 0.25); robot.add(e); return e; });
  const mouth = new THREE.Mesh(G.mouth, eyeMat); mouth.position.set(0, 1.42, 0.25); robot.add(mouth);
  const antenna = new THREE.Mesh(G.antenna, M.dark); antenna.position.set(0, 1.86, 0); robot.add(antenna);
  const bulbMat = new THREE.MeshStandardMaterial({ color: 0x38bdf8, emissive: 0x38bdf8, emissiveIntensity: 1.2 });
  const bulb = new THREE.Mesh(G.bulb, bulbMat); bulb.position.set(0, 2.02, 0); robot.add(bulb);
  const arms = [-0.36, 0.36].map((x) => {
    const a = new THREE.Mesh(G.arm, bodyMat); a.position.set(x, 1.12, 0.05); a.rotation.x = -0.2;
    const h = new THREE.Mesh(G.hand, M.dark); h.position.set(0, -0.42, 0); a.add(h); robot.add(a); return a;
  });
  const haloMat = new THREE.MeshBasicMaterial({ color: 0xf59e0b, transparent: true, opacity: 0 });
  const halo = new THREE.Mesh(G.halo, haloMat); halo.position.set(0, 2.3, 0); halo.rotation.x = Math.PI / 2; robot.add(halo);
  const glowMat = new THREE.MeshBasicMaterial({ color: 0xf59e0b, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false });
  const glow = new THREE.Mesh(G.glow, glowMat); glow.position.set(0, 1.3, 0); robot.add(glow);

  const nameLabel = makeSprite(0.56); nameLabel.position.set(0, 2.66, -0.95); g.add(nameLabel);

  return { bot, g, robot, body, bodyMat, head, eyes, eyeMat, mouth, bulbMat, arms, halo, haloMat, glow, glowMat,
    screenMat, barFill, barLabel, chip, nameLabel, status: 'resting', targets: { eye: 1, emis: 0.05 }, seed: Math.random() * 100 };
}

function disposeGroup(obj) {
  obj.traverse((o) => {
    if (o.material && o.material.map && o.userData.key !== undefined) o.material.map.dispose();
    if (o.isSprite || (o.material && o.material.map && o.userData.key)) o.material.dispose();
  });
}

function buildTower(state) {
  for (const rig of bots.values()) disposeGroup(rig.g);
  bots.clear();
  tower.clear();

  const teams = state.teams.length ? state.teams : ['Unassigned'];
  const byTeam = new Map(teams.map((t) => [t, []]));
  for (const b of state.bots) { if (!byTeam.has(b.team)) { byTeam.set(b.team, []); teams.push(b.team); } byTeam.get(b.team).push(b); }
  for (const list of byTeam.values()) list.sort((a, b) => a.name.localeCompare(b.name));
  const maxN = Math.max(1, ...[...byTeam.values()].map((l) => l.length));
  const width = maxN * DESK_X + 2.2;
  const floors = teams.length;

  teams.forEach((team, i) => {
    const y = (floors - 1 - i) * FLOOR_H;
    const color = TEAM_COLORS[team] ?? 0xa3a3a3;
    const slab = new THREE.Mesh(new THREE.BoxGeometry(width, 0.24, FLOOR_D), M.slab); slab.position.set(0, y - 0.12, 0); tower.add(slab);
    const edge = new THREE.Mesh(new THREE.BoxGeometry(width, 0.05, 0.06), new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.6 }));
    edge.position.set(0, y + 0.03, FLOOR_D / 2 - 0.03); tower.add(edge);
    const wall = new THREE.Mesh(new THREE.PlaneGeometry(width, FLOOR_H - 0.3), M.wall); wall.position.set(0, y + FLOOR_H / 2 - 0.1, -FLOOR_D / 2 + 0.15); tower.add(wall);
    for (const x of [-1, 1]) { const col = new THREE.Mesh(new THREE.BoxGeometry(0.34, FLOOR_H, 0.34), M.column); col.position.set(x * (width / 2 + 0.17), y + FLOOR_H / 2 - 0.12, -FLOOR_D / 2 + 0.3); tower.add(col); }
    const label = makeSprite(0.9); label.position.set(-width / 2 - 1.0, y + 1.6, 0.6);
    const list = byTeam.get(team);
    setSprite(label, [{ text: team.toUpperCase(), color: hexCss(color), scale: 1 }, { text: `${list.length} ${list.length === 1 ? 'bot' : 'bots'}`, color: '#94a3b8', scale: 0.62, weight: 500 }], { bg: 'rgba(11,16,32,0.75)', border: hexCss(color), pad: 18 });
    tower.add(label);
    list.forEach((bot, j) => {
      const rig = buildBot(bot);
      rig.g.position.set((j - (list.length - 1) / 2) * DESK_X, y, 0.55);
      tower.add(rig.g);
      bots.set(bot.id, rig);
    });
  });
  const roof = new THREE.Mesh(new THREE.BoxGeometry(width + 0.6, 0.3, FLOOR_D + 0.4), M.roof); roof.position.set(0, floors * FLOOR_H - 0.1, 0); tower.add(roof);
  const sign = makeSprite(1.1); sign.position.set(0, floors * FLOOR_H + 0.9, 0);
  setSprite(sign, [{ text: 'AGENT HQ', color: '#e2e8f0', scale: 1 }], { bg: 'rgba(11,16,32,0.8)', border: '#334155', pad: 20 });
  tower.add(sign);

  const totalH = floors * FLOOR_H;
  orbit.target.set(0, totalH / 2 - 0.2, 0);
  const aspect = window.innerWidth / Math.max(1, window.innerHeight);
  orbit.radius = clamp(Math.max(width * 0.8, totalH * 1.05) * Math.max(1, 1.25 / aspect) + 9, 8, 120);
}

// ---------------------------------------------------------------- apply state

function applyState(state) {
  latest = state;
  const sig = JSON.stringify(state.bots.map((b) => [b.id, b.team, b.name]));
  if (sig !== signature) { signature = sig; buildTower(state); }
  const max = Math.max(1, state.max_tokens_today || 0);
  for (const bot of state.bots) {
    const rig = bots.get(bot.id); if (!rig) continue;
    rig.bot = bot;
    rig.status = bot.status;
    const st = STATUS[bot.status] || STATUS.resting;
    const step = bot.step ? String(bot.step) : (bot.status === 'resting' ? 'idle' : '');
    setSprite(rig.nameLabel, [
      { text: bot.name, color: '#f8fafc', scale: 1 },
      { text: step.length > 34 ? step.slice(0, 33) + '…' : step, color: hexCss(st.color), scale: 0.6, weight: 500 },
    ], { bg: 'rgba(11,16,32,0.78)', border: hexCss(st.color), pad: 16 });
    const model = bot.model_seen && (bot.model === 'inherit' || bot.model === 'unknown') ? bot.model_seen : bot.model;
    setPlaneTexture(rig.chip, [{ text: shortModel(model), color: '#0b1020', scale: 1, weight: 800 }], { bg: modelColor(model), pad: 16, radius: 26 });
    const tokens = bot.tokens_today?.total || 0;
    const ratio = tokens > 0 ? Math.max(0.03, tokens / max) : 0.001;
    rig.barFill.scale.x = ratio * 1.5;
    const barColor = ratio > 0.66 ? 0xf59e0b : (ratio > 0.33 ? 0x22d3ee : 0x38bdf8);
    rig.barFill.material.color.setHex(barColor); rig.barFill.material.emissive.setHex(barColor);
    setSprite(rig.barLabel, [{ text: `${fmtTokens(tokens)} tok`, color: '#cbd5e1', scale: 1, weight: 600 }], { bg: 'rgba(11,16,32,0.6)', pad: 10, radius: 12 });
    rig.g.visible = true;
  }
  renderHeader(state);
  renderPanels(state);
  if (selectedId) renderDetail(selectedId);
}

function renderHeader(state) {
  for (const k of Object.keys(STATUS)) $('c-' + k).textContent = state.counts?.[k] ?? 0;
  $('tokens').textContent = `${fmtTokens(state.tokens_total_today || 0)} tokens today across ${state.bots.length} bots`;
}

function ago(iso, nowEpoch) {
  const t = Date.parse(iso); if (!t) return '';
  const s = Math.max(0, Math.round(nowEpoch - t / 1000));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
  return `${Math.floor(s / 86400)}d`;
}
function hhmm(iso) { const d = new Date(iso); return isNaN(d) ? '' : d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }

function fillList(section, rows, make) {
  const ul = section.querySelector('ul'); const empty = section.querySelector('.empty');
  section.querySelector('.n').textContent = rows.length;
  ul.replaceChildren(...rows.map(make));
  empty.style.display = rows.length ? 'none' : '';
}
function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

function renderPanels(state) {
  fillList($('waiting'), state.waiting || [], (w) => {
    const li = el('li'); li.append(el('b', null, w.bot), el('time', null, ago(w.since, state.now_epoch) + ' ago'));
    li.append(el('span', 'msg', w.message || w.type || 'needs your input'));
    li.addEventListener('click', () => select(w.bot_id)); return li;
  });
  fillList($('finished'), state.finished_today || [], (f) => {
    const li = el('li'); li.append(el('b', null, f.bot), el('time', null, hhmm(f.t)));
    li.append(el('span', 'msg', f.summary || 'stopped')); return li;
  });
}

function select(id) {
  selectedId = id;
  if (!id) { $('detail').hidden = true; return; }
  renderDetail(id);
}
function renderDetail(id) {
  const bot = latest?.bots.find((b) => b.id === id);
  if (!bot) { $('detail').hidden = true; return; }
  const st = STATUS[bot.status] || STATUS.resting;
  $('d-name').textContent = bot.name;
  const s = $('d-status'); s.textContent = st.text; s.style.background = hexCss(st.color);
  $('d-team').textContent = `${bot.team} (${bot.kind})`;
  $('d-model').textContent = bot.model_seen && bot.model_seen !== bot.model ? `${bot.model} (seen: ${bot.model_seen})` : bot.model;
  $('d-job').textContent = bot.job || '';
  $('d-step').textContent = bot.step || (bot.status === 'resting' ? 'idle' : '');
  const t = bot.tokens_today || {};
  $('d-tokens').textContent = `${fmtTokens(t.total)} total: ${fmtTokens(t.input)} in, ${fmtTokens(t.output)} out, ${fmtTokens(t.cache_read)} cache read, ${fmtTokens(t.cache_create)} cache write, ${t.calls || 0} calls`;
  $('d-last').textContent = bot.last_line ? `${new Date(bot.last_line).toLocaleString()} (${ago(bot.last_line, latest.now_epoch)} ago)${bot.stale ? ', stale' : ''}` : 'never';
  $('d-sessions').textContent = `${bot.sessions_active} active, ${bot.sessions_seen} seen`;
  $('d-source').textContent = bot.source || '';
  $('detail').hidden = false;
}
$('detail-close').addEventListener('click', () => select(null));

const raycaster = new THREE.Raycaster();
function onTap(e) {
  const rect = canvas.getBoundingClientRect();
  const p = new THREE.Vector2(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1);
  raycaster.setFromCamera(p, camera);
  const groups = [...bots.values()].map((r) => r.g);
  const hit = raycaster.intersectObjects(groups, true)[0];
  if (!hit) { select(null); return; }
  let o = hit.object;
  while (o && !o.userData.botId) o = o.parent;
  select(o ? o.userData.botId : null);
}

// ---------------------------------------------------------------- animate

const tmpColor = new THREE.Color();
function lerp(a, b, t) { return a + (b - a) * t; }

function animate(timeMs) {
  const t = timeMs / 1000;
  orbit.update();
  for (const rig of bots.values()) {
    const st = STATUS[rig.status] || STATUS.resting;
    const k = rig.seed;
    const working = rig.status === 'working', waiting = rig.status === 'waiting', stuck = rig.status === 'stuck', resting = rig.status === 'resting';
    const eyeTarget = resting ? 0.12 : 1;
    for (const e of rig.eyes) e.scale.y = lerp(e.scale.y, eyeTarget, 0.12);
    rig.mouth.visible = !resting;
    rig.eyeMat.emissive.setHex(st.color);
    rig.eyeMat.emissiveIntensity = resting ? 0.4 : (working && Math.sin(t * 7 + k) > 0.985 ? 0.2 : 1.5);
    rig.bulbMat.color.setHex(st.color); rig.bulbMat.emissive.setHex(st.color);
    rig.bulbMat.emissiveIntensity = stuck ? 0.8 + 0.8 * Math.max(0, Math.sin(t * 2.2 + k)) : (waiting ? 1 + Math.sin(t * 5 + k) * 0.6 : (working ? 1.2 : 0.3));
    rig.screenMat.emissive.setHex(st.color);
    rig.screenMat.emissiveIntensity = working ? 0.75 + 0.25 * Math.sin(t * 9 + k) * Math.sin(t * 3.1) : (resting ? 0.08 : 0.6 + 0.3 * Math.sin(t * 3 + k));
    const emisTarget = stuck ? 0.55 + 0.35 * Math.sin(t * 2.2 + k) : (waiting ? 0.35 + 0.25 * Math.sin(t * 5 + k) : 0.05);
    rig.bodyMat.emissive.setHex(stuck ? 0xef4444 : (waiting ? 0xf59e0b : (TEAM_COLORS[rig.bot.team] ?? 0xa3a3a3)));
    rig.bodyMat.emissiveIntensity = lerp(rig.bodyMat.emissiveIntensity, emisTarget, 0.1);
    const armTarget = working ? -0.95 : (waiting ? -1.9 : -0.2);
    rig.arms.forEach((a, i) => {
      const swing = working ? Math.sin(t * 15 + k + i * Math.PI) * 0.22 : 0;
      a.rotation.x = lerp(a.rotation.x, armTarget + swing, 0.2);
      a.rotation.z = lerp(a.rotation.z, waiting ? (i ? -0.3 : 0.3) : 0, 0.1);
    });
    rig.head.rotation.x = working ? Math.sin(t * 2.3 + k) * 0.06 : (resting ? 0.18 : 0);
    rig.head.rotation.z = stuck ? Math.sin(t * 20) * 0.03 : 0;
    const breathe = resting ? 1 + 0.015 * Math.sin(t * 1.6 + k) : 1;
    rig.body.scale.set(1, breathe, 1);
    rig.robot.position.x = stuck ? Math.sin(t * 28 + k) * 0.015 : 0;
    const haloTarget = waiting ? 0.9 : 0;
    rig.haloMat.opacity = lerp(rig.haloMat.opacity, haloTarget, 0.1);
    rig.halo.scale.setScalar(waiting ? 1 + 0.12 * Math.sin(t * 4 + k) : 1);
    rig.halo.position.y = 2.3 + (waiting ? 0.08 * Math.sin(t * 2 + k) : 0);
    rig.glowMat.color.setHex(stuck ? 0xef4444 : 0xf59e0b);
    rig.glowMat.opacity = lerp(rig.glowMat.opacity, waiting ? 0.16 + 0.08 * Math.sin(t * 4 + k) : (stuck ? 0.1 + 0.06 * Math.sin(t * 2.2 + k) : 0), 0.1);
  }
  renderer.render(scene, camera);
}

function resize() {
  const w = window.innerWidth, h = window.innerHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);
resize();
renderer.setAnimationLoop(animate);

// ---------------------------------------------------------------- data loop

async function tick() {
  try {
    const r = await fetch('/state', { cache: 'no-store' });
    if (!r.ok) throw new Error(String(r.status));
    applyState(await r.json());
    document.body.classList.remove('offline');
  } catch (err) {
    document.body.classList.add('offline');
  }
}
tick();
setInterval(tick, REFRESH_MS);
setInterval(() => { $('clock').textContent = new Date().toLocaleTimeString(); }, 1000);
$('clock').textContent = new Date().toLocaleTimeString();
