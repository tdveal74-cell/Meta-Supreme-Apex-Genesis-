/**
 * Client half of the frame pipeline (System gap 1).
 *
 * The server streams blendshape frames stamped on the audio timeline. The
 * renderer asks this buffer, once per animation frame, for the newest frame
 * whose at_ms has already been reached by the audio clock. Everything older
 * than the frame it hands back is discarded: a frame the audio has passed can
 * never be shown honestly.
 *
 * Pure module: no browser or Node APIs, so it can be proven from
 * scripts/presence-check.ts under Node's type stripping.
 */

import type { Blendshape, FramePriority, Weights } from "./protocol";

export type BufferedFrame = {
  turn_id: string;
  seq: number;
  at_ms: number;
  priority: FramePriority;
  weights: Weights;
};

export type FrameCounters = {
  pushed: number;
  sampled: number;
  dropped: number;
};

export class FrameBuffer {
  /** Pending frames ordered by at_ms ascending. */
  frames: BufferedFrame[] = [];
  pushed = 0;
  sampled = 0;
  dropped = 0;

  /** Insert a frame, keeping at_ms order even if the wire delivered it late. */
  push(frame: BufferedFrame): void {
    this.pushed += 1;
    const frames = this.frames;
    const last = frames[frames.length - 1];
    if (last === undefined || last.at_ms <= frame.at_ms) {
      frames.push(frame);
      return;
    }
    let index = frames.length - 1;
    while (index > 0 && frames[index - 1].at_ms > frame.at_ms) index -= 1;
    frames.splice(index, 0, frame);
  }

  /**
   * The newest frame with at_ms <= audioMs, or null when the audio clock has
   * not reached any pending frame. Older frames are discarded and counted as
   * dropped, because the renderer skipped them.
   */
  sample(audioMs: number): BufferedFrame | null {
    const frames = this.frames;
    let index = -1;
    for (let i = 0; i < frames.length; i += 1) {
      if (frames[i].at_ms <= audioMs) index = i;
      else break;
    }
    if (index < 0) return null;
    const frame = frames[index];
    this.frames = frames.slice(index + 1);
    this.sampled += 1;
    this.dropped += index;
    return frame;
  }

  /**
   * Shed load when the renderer has fallen behind the audio clock.
   *
   * behindMs is how far the renderer trails the audio; windowMs is the
   * tolerated lag. The ladder is progressive, one rung per window of lag:
   *   behind > 1 window: drop priority 2 frames (fine detail)
   *   behind > 2 windows: also drop priority 1 frames
   *   behind > 3 windows: also thin priority 0 frames to every second one,
   *                       always keeping the newest
   * Returns how many frames were dropped by this call.
   *
   * The spec fixed the order (2, then 1, then thin 0) and left the trigger
   * open; the window multiples are this build's choice.
   */
  compress(behindMs: number, windowMs: number): number {
    if (!(windowMs > 0) || !(behindMs > windowMs)) return 0;
    const before = this.frames.length;
    const severity = behindMs / windowMs;

    let kept = this.frames.filter((frame) => frame.priority !== 2);
    if (severity > 2) kept = kept.filter((frame) => frame.priority !== 1);
    if (severity > 3) {
      const thinned: BufferedFrame[] = [];
      let keepThis = false;
      // Walk from newest to oldest so the newest frame always survives.
      for (let i = kept.length - 1; i >= 0; i -= 1) {
        const frame = kept[i];
        if (frame.priority !== 0) {
          thinned.push(frame);
          continue;
        }
        keepThis = !keepThis;
        if (keepThis) thinned.push(frame);
      }
      thinned.reverse();
      kept = thinned;
    }

    this.frames = kept;
    const dropped = before - kept.length;
    this.dropped += dropped;
    return dropped;
  }

  /** Discard every pending frame (barge-in). Returns how many went. */
  flush(): number {
    const dropped = this.frames.length;
    this.frames = [];
    this.dropped += dropped;
    return dropped;
  }

  size(): number {
    return this.frames.length;
  }

  /** at_ms of the newest pending frame, or null when empty. */
  newestAtMs(): number | null {
    const last = this.frames[this.frames.length - 1];
    return last === undefined ? null : last.at_ms;
  }

  counters(): FrameCounters {
    return { pushed: this.pushed, sampled: this.sampled, dropped: this.dropped };
  }

  resetCounters(): void {
    this.pushed = 0;
    this.sampled = 0;
    this.dropped = 0;
  }
}

/**
 * Linear interpolation between two weight sets. Names missing on either side
 * read as 0. alpha 0 returns `from`, alpha 1 returns `to`; alpha is clamped.
 */
export function lerpWeights(from: Weights, to: Weights, alpha: number): Weights {
  const a = alpha < 0 ? 0 : alpha > 1 ? 1 : alpha;
  const out: Weights = {};
  const names = new Set<string>([...Object.keys(from), ...Object.keys(to)]);
  for (const name of names) {
    const key = name as Blendshape;
    const start = from[key] ?? 0;
    const end = to[key] ?? 0;
    out[key] = start + (end - start) * a;
  }
  return out;
}
