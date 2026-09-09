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
  columns: 54,
  rows: 38,
  halfWidth: 3.2,
  halfHeight: 2.1,
};

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

  // The cranium itself.
  let z = 0.78 * mask;

  // Brow ridges, lifting with the expression.
  for (const side of [-1, 1]) {
    z += (0.09 + 0.05 * browUp) * bump(x - side * 0.3, y - (0.44 + browUp * 0.05), 0.3, 0.13);
  }

  // Eye sockets. A closed lid fills the socket back in, so a blink reads as the
  // surface smoothing over rather than as the eye vanishing.
  for (const side of [-1, 1] as const) {
    const blink = side < 0 ? (weights.blinkLeft ?? 0) : (weights.blinkRight ?? 0);
    z -= 0.2 * (1 - 0.85 * blink) * bump(x - side * 0.31, y - 0.24, 0.19, 0.12);
  }

  // The nose: a ridge down the midline and a tip.
  z += 0.24 * bump(x, y + 0.06, 0.1, 0.32);
  z += 0.1 * bump(x, y + 0.28, 0.13, 0.09);

  // Cheeks.
  for (const side of [-1, 1]) {
    z += 0.07 * bump(x - side * 0.46, y + 0.12, 0.26, 0.24);
  }

  // The mouth, which is the part the visemes drive. It is a recess at rest and
  // deepens and widens as the jaw opens.
  const mouthWidth = 0.3 * (1 - 0.35 * pucker + 0.2 * funnel);
  const mouthHeight = 0.075 + 0.16 * open;
  z -= (0.1 + 0.48 * open) * bump(x, y + 0.56 + open * 0.05, mouthWidth, mouthHeight);

  // Chin and jaw.
  z += 0.08 * bump(x, y + 0.86, 0.28, 0.2);

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
