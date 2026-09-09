/**
 * The wire field, and the face that pushes out of it.
 *
 * Ruled by Tee 2026-09-09, in three steps: an interactive digital face, then a
 * face recognition wireframe as the reference, then the shape of the idea, which
 * is his: the background IS the wire mesh, and the face indents into it when
 * DEVON is active. So this is not a model of a head. It is a flat grid, and a
 * relief field that deforms it, and the amount of deformation is how awake DEVON
 * is.
 *
 * Nothing is copied from the reference image, which is a licensed stock
 * illustration. The topology here is a plain lattice and the relief is the
 * analytic field below, so the artwork is the estate's own.
 *
 * Three earlier passes tried to SCULPT a head out of spheres and boxes and each
 * one rendered a toy. The lesson kept in this file: primitives cannot carry a
 * face, but a displaced surface can, because a face is mostly a depth map.
 *
 * Pure. No three, no DOM, no React, so scripts/presence-check.ts can execute it.
 */

export type Weights = {
  jawOpen?: number;
  mouthFunnel?: number;
  mouthPucker?: number;
  blinkLeft?: number;
  blinkRight?: number;
  browInnerUp?: number;
};

export type GridSpec = {
  /** Vertices across and down. */
  columns: number;
  rows: number;
  /** Half extents of the field in world units. */
  halfWidth: number;
  halfHeight: number;
};

/*
 * Sized so the lattice runs past the frame on every side at the canvas's own
 * camera (z 3.1, fov 32), which is what makes it read as a field DEVON is
 * inside rather than as a rectangle floating in one.
 */
export const DEFAULT_GRID: GridSpec = {
  columns: 104,
  rows: 72,
  halfWidth: 2.25,
  halfHeight: 1.55,
};

/*
 * WHY THESE NUMBERS, measured rather than chosen.
 *
 * A feature cannot be sharper than the lattice that samples it. The first
 * sharpening pass tightened the nose to a 0.062 radius, which is 0.124 units
 * across, on a grid whose cell was 6.4/54 = 0.119 units. The nose was one cell
 * wide, so it fell between vertices and rendered as nothing, and the face came
 * out softer than the blunt version it replaced.
 *
 * At these extents the cell is 4.5/104 = 0.043 units, so the narrowest feature
 * in faceRelief, the nose ridge, spans about three cells and the mouth line
 * about two. That is the floor: tightening any feature further means adding
 * columns in the same commit, or it will silently vanish.
 */
export const CELL_WIDTH = (DEFAULT_GRID.halfWidth * 2) / (DEFAULT_GRID.columns - 1);
export const NARROWEST_FEATURE_RADIUS = 0.062;

/** A soft bump, 1 at the centre and falling to 0 by `radius`. */
function bump(dx: number, dy: number, radiusX: number, radiusY: number): number {
  const d = Math.hypot(dx / radiusX, dy / radiusY);
  if (d >= 1) return 0;
  return Math.cos((d * Math.PI) / 2) ** 2;
}

/**
 * How far the surface stands proud of the flat field at (x, y), before the
 * activity level scales it.
 *
 * Positive is toward the viewer. The eye sockets and the mouth are negative on
 * purpose: a face is not only bulges, and the recesses are what make it read as
 * a face rather than as a lump.
 */
export function faceRelief(x: number, y: number, weights: Weights = {}): number {
  // Outside the head oval the field stays flat, which is what keeps the mesh
  // reading as a background with a face in it rather than as a warped sheet.
  const mask = bump(x, y - 0.02, 0.86, 1.12);
  if (mask <= 0) return 0;

  const open = weights.jawOpen ?? 0;
  const funnel = weights.mouthFunnel ?? 0;
  const pucker = weights.mouthPucker ?? 0;
  const browUp = weights.browInnerUp ?? 0;

  // The cranium. Deliberately shallower than the features that sit on it: a
  // tall dome swamps everything else and the face reads as an egg, which is
  // what the first sharpening pass looked like.
  let z = 0.46 * mask;

  // Brow ridges: tight and pronounced, and they carry the expression.
  for (const side of [-1, 1]) {
    z += (0.19 + 0.08 * browUp) * bump(x - side * 0.29, y - (0.45 + browUp * 0.05), 0.24, 0.085);
  }

  // Eye sockets, cut hard so the brow above them has something to sit over. A
  // closed lid fills the socket back in, so a blink reads as the surface
  // smoothing rather than as the eye vanishing.
  for (const side of [-1, 1] as const) {
    const blink = side < 0 ? (weights.blinkLeft ?? 0) : (weights.blinkRight ?? 0);
    z -= 0.3 * (1 - 0.85 * blink) * bump(x - side * 0.3, y - 0.25, 0.16, 0.1);
    // The eyeball itself, so the socket is not an empty pit.
    z += 0.12 * (1 - blink) * bump(x - side * 0.3, y - 0.25, 0.085, 0.055);
  }

  // The nose: a narrow ridge and a defined tip, the strongest vertical feature.
  z += 0.3 * bump(x, y + 0.04, 0.062, 0.3);
  z += 0.17 * bump(x, y + 0.26, 0.1, 0.075);
  // Nostril shadows, which is what stops the tip reading as a beak.
  for (const side of [-1, 1]) {
    z -= 0.09 * bump(x - side * 0.1, y + 0.3, 0.05, 0.045);
  }

  // Cheekbones: higher and tighter than before so they catch light as edges.
  for (const side of [-1, 1]) {
    z += 0.14 * bump(x - side * 0.45, y - 0.06, 0.2, 0.16);
  }

  // The mouth. A cut line at rest, opening into a deep well as the jaw drops,
  // with a lip ridge above and below so the opening has edges.
  const mouthWidth = 0.27 * (1 - 0.35 * pucker + 0.2 * funnel);
  const mouthHeight = 0.045 + 0.17 * open;
  z += 0.08 * bump(x, y + 0.48, mouthWidth * 1.15, 0.055);
  z += 0.07 * bump(x, y + 0.66, mouthWidth * 1.15, 0.06);
  z -= (0.16 + 0.55 * open) * bump(x, y + 0.57 + open * 0.05, mouthWidth, mouthHeight);

  // Chin, and the jaw line under it.
  z += 0.13 * bump(x, y + 0.85, 0.24, 0.16);
  z -= 0.05 * bump(x, y + 0.74, 0.3, 0.05);

  return z;
}

/** Vertex count for a grid. */
export function vertexCount(grid: GridSpec = DEFAULT_GRID): number {
  return grid.columns * grid.rows;
}

/**
 * The line segments of the lattice, as index pairs.
 *
 * Horizontal runs then vertical runs. Built once; only the positions move.
 */
export function buildGridEdges(grid: GridSpec = DEFAULT_GRID): Uint32Array {
  const { columns, rows } = grid;
  const horizontal = rows * (columns - 1);
  const vertical = columns * (rows - 1);
  const out = new Uint32Array((horizontal + vertical) * 2);
  let w = 0;

  for (let r = 0; r < rows; r += 1) {
    for (let c = 0; c < columns - 1; c += 1) {
      out[w++] = r * columns + c;
      out[w++] = r * columns + c + 1;
    }
  }
  for (let c = 0; c < columns; c += 1) {
    for (let r = 0; r < rows - 1; r += 1) {
      out[w++] = r * columns + c;
      out[w++] = (r + 1) * columns + c;
    }
  }
  return out;
}

/** The flat (x, y) of every vertex, which never changes. */
export function buildGridPlane(grid: GridSpec = DEFAULT_GRID): Float32Array {
  const { columns, rows, halfWidth, halfHeight } = grid;
  const out = new Float32Array(columns * rows * 3);
  for (let r = 0; r < rows; r += 1) {
    for (let c = 0; c < columns; c += 1) {
      const i = (r * columns + c) * 3;
      out[i] = -halfWidth + (c / (columns - 1)) * halfWidth * 2;
      out[i + 1] = halfHeight - (r / (rows - 1)) * halfHeight * 2;
      out[i + 2] = 0;
    }
  }
  return out;
}

/**
 * Write the displaced z for every vertex into `positions` in place.
 *
 * `activity` is how far the face has emerged: 0 leaves a perfectly flat field,
 * 1 is the full relief. Returns the peak displacement written, which is what a
 * check can assert on without a canvas.
 */
export function applyRelief(
  positions: Float32Array,
  activity: number,
  weights: Weights = {},
  grid: GridSpec = DEFAULT_GRID,
): number {
  const clamped = Math.max(0, Math.min(1, activity));
  let peak = 0;
  const total = grid.columns * grid.rows;
  for (let v = 0; v < total; v += 1) {
    const i = v * 3;
    const z = faceRelief(positions[i], positions[i + 1], weights) * clamped;
    positions[i + 2] = z;
    if (Math.abs(z) > Math.abs(peak)) peak = z;
  }
  return peak;
}

/**
 * The aether: the slow standing motion of the field itself.
 *
 * Ruled by Tee 2026-09-09, "wire mesh needs digital Aether". Without it the
 * lattice renders as graph paper, because a grid at rest is a grid. This is the
 * medium DEVON sits inside, breathing on its own whether or not he is speaking.
 */
export function ambientWave(x: number, y: number, t: number): number {
  return (
    0.035 * Math.sin(x * 1.6 + t * 0.55) * Math.cos(y * 1.3 - t * 0.4) +
    0.018 * Math.sin((x + y) * 2.4 - t * 0.9) +
    0.012 * Math.cos(Math.hypot(x, y) * 3.1 - t * 1.2)
  );
}

/**
 * Displace the field, combining the face relief with the ambient motion.
 *
 * Returns the peak absolute displacement, so a check can assert that an active
 * face actually moves the sheet and an idle one barely does.
 */
export function applyField(
  positions: Float32Array,
  activity: number,
  time: number,
  weights: Weights = {},
  grid: GridSpec = DEFAULT_GRID,
  /**
   * Optional per vertex output of the FACE relief alone, without the ambient
   * wave. Lighting must come from this rather than from the final z: the wave
   * moves every vertex, so colouring by total depth washes the face out into
   * the background, which is exactly what it did on the first aether pass.
   */
  faceOnly?: Float32Array,
): number {
  const clamped = Math.max(0, Math.min(1, activity));
  let peak = 0;
  const total = grid.columns * grid.rows;
  for (let v = 0; v < total; v += 1) {
    const i = v * 3;
    const x = positions[i];
    const y = positions[i + 1];
    const face = faceRelief(x, y, weights) * clamped;
    positions[i + 2] = face + ambientWave(x, y, time);
    if (faceOnly) faceOnly[v] = face;
    if (Math.abs(face) > peak) peak = Math.abs(face);
  }
  return peak;
}

/**
 * Light the field by its own depth.
 *
 * This is what makes the face legible. Geometry alone hides it: the lattice is
 * seen nearly face on, so a vertex a little closer to the viewer looks the same
 * as its neighbours. Brightness does not hide, so depth is written as light and
 * the face reads even when the relief is slight.
 *
 * `low` and `high` are RGB triples in 0..1.
 */
export function writeDepthColors(
  faceOnly: Float32Array,
  colors: Float32Array,
  low: readonly [number, number, number],
  high: readonly [number, number, number],
  range = 0.55,
): void {
  for (let v = 0; v < faceOnly.length; v += 1) {
    const t = Math.max(0, Math.min(1, faceOnly[v] / range));
    // Sharpened rather than eased. A smooth ramp spread the face's light over
    // the whole sheet and it read as haze; this keeps the lit region tight to
    // where the surface actually stands proud.
    const e = t * t;
    const i = v * 3;
    colors[i] = low[0] + (high[0] - low[0]) * e;
    colors[i + 1] = low[1] + (high[1] - low[1]) * e;
    colors[i + 2] = low[2] + (high[2] - low[2]) * e;
  }
}

/** Starting positions for the drifting motes that fill the volume. */
export function buildMotes(count: number, grid: GridSpec = DEFAULT_GRID): Float32Array {
  const out = new Float32Array(count * 3);
  // Deterministic: a fixed lattice walk rather than Math.random, so the field
  // is identical on every load and a check can rely on it.
  for (let i = 0; i < count; i += 1) {
    const a = (i * 2.399963229728653) % (Math.PI * 2);
    const r = Math.sqrt((i + 0.5) / count);
    out[i * 3] = Math.cos(a) * r * grid.halfWidth * 1.05;
    out[i * 3 + 1] = Math.sin(a) * r * grid.halfHeight * 1.05;
    out[i * 3 + 2] = 0.35 + ((i * 37) % 100) / 100 * 1.1;
  }
  return out;
}

/* ------------------------------------------------------------------ */
/* The head itself: a dense point cloud, not a bulge in the sheet.     */
/*                                                                    */
/* Ruled by Tee 2026-09-09 from a board of digital face scan           */
/* references. Every one of them is the same object: thousands of      */
/* glowing points in the shape of a head, floating in a dark void,     */
/* with the features legible. A relief in a background grid reads as a */
/* disturbance; this reads as a face.                                  */
/*                                                                    */
/* The wire field stays behind it, so his earlier ruling still holds:  */
/* the background IS the mesh, and the head forms out of it.           */
/* ------------------------------------------------------------------ */

/** Half extents of the head in the same units faceRelief is written in. */
export const HEAD_HALF_WIDTH = 0.86;
export const HEAD_HALF_HEIGHT = 1.12;

/**
 * Even, organic coverage of the head's silhouette.
 *
 * A sunflower distribution rather than a grid: the references show scattered
 * points, and a grid sampled inside an ellipse shows its rows the moment the
 * surface tilts. Deterministic, so the cloud is identical on every load.
 */
export function buildHeadCloud(count: number): Float32Array {
  const out = new Float32Array(count * 3);
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < count; i += 1) {
    const r = Math.sqrt((i + 0.5) / count);
    const a = i * golden;
    out[i * 3] = Math.cos(a) * r * HEAD_HALF_WIDTH;
    out[i * 3 + 1] = Math.sin(a) * r * HEAD_HALF_HEIGHT + 0.02;
    out[i * 3 + 2] = 0;
  }
  return out;
}

/**
 * Write the head cloud's depth, and report each point's relief for lighting.
 *
 * Same field as the background sheet, so the head and the mesh it forms out of
 * agree by construction rather than by two tunings that drift apart.
 */
export function applyHeadRelief(
  positions: Float32Array,
  activity: number,
  time: number,
  weights: Weights = {},
  faceOnly?: Float32Array,
): number {
  const clamped = Math.max(0, Math.min(1, activity));
  let peak = 0;
  const count = positions.length / 3;
  for (let i = 0; i < count; i += 1) {
    const p = i * 3;
    const x = positions[p];
    const y = positions[p + 1];
    const relief = faceRelief(x, y, weights);
    // The head keeps a little of its own shape even at rest, so it is a head
    // dissolving into the field rather than a flat disc of dots.
    const z = relief * (0.32 + 0.68 * clamped) + ambientWave(x, y, time) * 0.5;
    positions[p + 2] = z;
    if (faceOnly) faceOnly[i] = relief * clamped;
    if (relief > peak) peak = relief;
  }
  return peak;
}
