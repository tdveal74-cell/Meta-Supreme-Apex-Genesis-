/**
 * The audio the presence socket sends, turned into something a browser plays.
 *
 * WHY THIS EXISTS
 *
 * Until now `usePresenceSocket` counted every audio message and threw it away:
 * "this build does not decode or play it". The presence service, meanwhile,
 * mints LiveKit join tokens but has never published audio into a room
 * (`apps/presence/__init__.py:45`). So there was no path, with LiveKit or
 * without it, by which anyone could hear DEVON speak. Building a real Cartesia
 * adapter and stopping there would have produced perfect audio that nothing
 * ever played.
 *
 * WHAT IS PURE AND WHY
 *
 * Everything here is arithmetic over bytes and numbers, with no AudioContext
 * and no DOM, so `scripts/presence-check.ts` can execute it rather than a
 * comment asserting it works. The AudioContext wiring lives in
 * `components/presence/useAudioPlayback.ts`, which is the part a browser has
 * to prove.
 *
 * THE TIMELINE, WHICH IS THE WHOLE POINT
 *
 * Every chunk carries `at_ms`, its position in the utterance, and chunks can
 * arrive early, in bursts, or slightly out of order. So playback is scheduled
 * against one origin per turn rather than played on arrival: chunk `at_ms` is
 * placed at `timelineStart + at_ms / 1000` on the AudioContext clock. Playing
 * on arrival would turn network jitter into audible jitter, and would put the
 * voice on a different clock from the face, which is the exact drift the
 * sliding window buffer exists to prevent.
 */

/** The presence protocol's audio rate. `apps/presence/protocol.py:294`. */
export const PCM_RATE = 16000;

/**
 * How far ahead of "now" a turn's timeline origin is placed.
 *
 * The first chunk arrives after the network has already spent time on it, and
 * a buffer scheduled in the past starts late and clipped. 80 ms is enough to
 * absorb ordinary jitter without being heard as delay.
 */
export const PLAYBACK_LEAD_S = 0.08;

const BASE64 =
  "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

const REVERSE: Int16Array = (() => {
  const table = new Int16Array(128).fill(-1);
  for (let index = 0; index < BASE64.length; index += 1) {
    table[BASE64.charCodeAt(index)] = index;
  }
  return table;
})();

/**
 * Base64 to bytes, written out rather than delegated to `atob`.
 *
 * `atob` exists in both a browser and Node, but it returns a binary string
 * that then needs a charCodeAt loop anyway, and it throws on input this has to
 * survive. This returns an empty array for anything malformed, because a bad
 * chunk must cost one chunk of audio and never the turn.
 */
export function base64ToBytes(value: string): Uint8Array {
  if (typeof value !== "string" || value.length === 0) return new Uint8Array(0);
  let clean = value;
  while (clean.length > 0 && clean[clean.length - 1] === "=") {
    clean = clean.slice(0, -1);
  }
  const bytes = new Uint8Array(Math.floor((clean.length * 3) / 4));
  let out = 0;
  let bits = 0;
  let held = 0;
  for (let index = 0; index < clean.length; index += 1) {
    const code = clean.charCodeAt(index);
    const value6 = code < 128 ? REVERSE[code] : -1;
    if (value6 < 0) return new Uint8Array(0);
    held = (held << 6) | value6;
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      bytes[out] = (held >> bits) & 0xff;
      out += 1;
    }
  }
  return out === bytes.length ? bytes : bytes.subarray(0, out);
}

/**
 * Little endian signed 16 bit PCM to the Float32 the Web Audio API wants.
 *
 * Divided by 32768 rather than 32767: it is the magnitude of the most negative
 * sample, so the range maps to [-1, 1) with no asymmetry and no clipping at
 * full scale. A trailing odd byte is not a sample and is dropped.
 */
export function pcmToFloat32(bytes: Uint8Array): Float32Array<ArrayBuffer> {
  const count = bytes.length >> 1;
  // Explicitly over ArrayBuffer, not ArrayBufferLike: copyToChannel refuses a
  // view that might sit on a SharedArrayBuffer, and the inferred type is the
  // wider one.
  const out = new Float32Array(new ArrayBuffer(count * 4));
  for (let index = 0; index < count; index += 1) {
    const low = bytes[index * 2];
    const high = bytes[index * 2 + 1];
    // The high byte carries the sign, so it is read signed and shifted.
    const sample = ((high << 24) >> 16) | low;
    out[index] = sample / 32768;
  }
  return out;
}

export type Placement = {
  /** When on the AudioContext clock this chunk should start. */
  when: number;
  /** True when the chunk's own slot has already passed. */
  late: boolean;
};

/**
 * Where one chunk goes on the AudioContext clock.
 *
 * A chunk whose slot has passed is played immediately rather than dropped: a
 * late chunk still carries words, and silence is a worse answer than a
 * syllable that lands a few milliseconds tight. The `late` flag is returned so
 * the caller can count it instead of guessing whether the lane is healthy.
 */
export function placeChunk(
  atMs: number,
  timelineStart: number,
  now: number,
): Placement {
  const slot = timelineStart + atMs / 1000;
  if (!Number.isFinite(slot)) return { when: now, late: true };
  if (slot < now) return { when: now, late: true };
  return { when: slot, late: false };
}

/** Seconds of audio in a PCM payload, at the presence rate. */
export function durationSeconds(bytes: Uint8Array): number {
  return bytes.length / 2 / PCM_RATE;
}
