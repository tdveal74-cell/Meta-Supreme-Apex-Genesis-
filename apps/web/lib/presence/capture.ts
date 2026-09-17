/**
 * Push to talk capture: microphone samples out, `listen_chunk` payloads in.
 *
 * Pure module: no browser or Node APIs, no enums, no parameter properties,
 * no namespaces, so Node's type stripping can run it unchanged for the
 * scripts/presence-check.ts proof. The caller owns the microphone, the
 * AudioContext and the socket; everything here is arithmetic on samples.
 *
 * This is the half the ear was missing. PR #257 built the server side of
 * protocol v2, and apps/presence/hearing.py has assembled clips since, but
 * nothing in the browser ever sent one: useBargeIn already opens the
 * microphone and already runs an AnalyserNode, and an AnalyserNode is the
 * wrong tool for this. getFloatTimeDomainData hands back a rolling window of
 * whatever is in the analyser right now, so consecutive reads overlap or skip
 * depending on frame timing. It is exactly right for "is someone talking",
 * which is what barge in asks, and it cannot produce the contiguous stream a
 * transcriber needs. Capture taps the same MediaStream through a worklet
 * instead and keeps every block.
 *
 * WHY NOT RESAMPLE. An AudioContext runs at whatever rate the hardware gives
 * it, usually 44100 or 48000, and both are in the server's LISTEN_RATES, so
 * the common case needs no resampling at all. When the rate is not one the
 * server takes, this module REFUSES rather than converting. A resampler
 * written casually aliases, and audio played at the wrong rate does not fail
 * loudly: it transcribes to a fluent sentence nobody said, which is the one
 * failure apps/presence/hearing.py's wav_from_pcm docstring is written
 * against. A refusal names the rate and costs a retry.
 */

import {
  LISTEN_RATES,
  MAX_CLIP_BYTES,
  MAX_CLIP_CHUNKS,
  type ListenRate,
} from "./protocol.ts";

/** Bytes per sample in pcm_s16le, which is what the name says. */
export const BYTES_PER_SAMPLE = 2;

const RATE_SET: ReadonlySet<number> = new Set(LISTEN_RATES);

export function isListenRate(rate: unknown): rate is ListenRate {
  return typeof rate === "number" && RATE_SET.has(rate);
}

/**
 * Why a rate cannot be used, as a sentence for the operator, or "" when it
 * can. Named rather than boolean because the caller shows this.
 */
export function rateRefusal(rate: number): string {
  if (!Number.isFinite(rate) || rate <= 0) {
    return `This device reports a sample rate of ${rate}, which is not a rate.`;
  }
  if (isListenRate(rate)) return "";
  return (
    `This device records at ${rate} Hz and the server takes ` +
    `${LISTEN_RATES.join(", ")}. Nothing here resamples, because a resampler ` +
    `written in a hurry turns speech into a fluent sentence nobody said.`
  );
}

/**
 * Float samples in -1..1 to little endian signed 16 bit.
 *
 * The range is asymmetric and so is the conversion: -1 maps to -32768 and +1
 * to 32767, because two's complement has one more negative value than
 * positive. Scaling both by 32768 would wrap the loudest positive sample to
 * the loudest NEGATIVE one, which is a click on every peak.
 *
 * A sample outside the range is clamped rather than dropped. Anything that is
 * not a finite number becomes silence, since a NaN written into the buffer
 * reaches the vendor as whatever those two bytes happen to mean.
 */
export function floatToPcm16(samples: Float32Array | ReadonlyArray<number>): Uint8Array {
  const count = samples.length;
  const bytes = new Uint8Array(count * BYTES_PER_SAMPLE);
  const view = new DataView(bytes.buffer);
  for (let i = 0; i < count; i += 1) {
    const raw = samples[i];
    let value = 0;
    if (Number.isFinite(raw)) {
      value = raw < -1 ? -1 : raw > 1 ? 1 : raw;
    }
    view.setInt16(i * BYTES_PER_SAMPLE, value < 0 ? value * 0x8000 : value * 0x7fff, true);
  }
  return bytes;
}

const B64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

/**
 * Base64, written out rather than taken from btoa.
 *
 * btoa exists in both browsers and Node, but it takes a string of code points
 * below 256 and this module holds bytes. Going through a string to reach it
 * means building a megabyte of characters per clip and trusting that nothing
 * upstream handed us a code point above 255. The loop below is the same
 * arithmetic without the detour, and it keeps this module pure enough for the
 * presence-check proof to import.
 */
export function bytesToBase64(bytes: Uint8Array): string {
  let out = "";
  const full = bytes.length - (bytes.length % 3);
  for (let i = 0; i < full; i += 3) {
    const n = (bytes[i] << 16) | (bytes[i + 1] << 8) | bytes[i + 2];
    out +=
      B64_ALPHABET[(n >> 18) & 63] +
      B64_ALPHABET[(n >> 12) & 63] +
      B64_ALPHABET[(n >> 6) & 63] +
      B64_ALPHABET[n & 63];
  }
  const left = bytes.length - full;
  if (left === 1) {
    const n = bytes[full] << 16;
    out += B64_ALPHABET[(n >> 18) & 63] + B64_ALPHABET[(n >> 12) & 63] + "==";
  } else if (left === 2) {
    const n = (bytes[full] << 16) | (bytes[full + 1] << 8);
    out +=
      B64_ALPHABET[(n >> 18) & 63] +
      B64_ALPHABET[(n >> 12) & 63] +
      B64_ALPHABET[(n >> 6) & 63] +
      "=";
  }
  return out;
}

export type ClipRefusal = {
  /** Which ceiling was hit, for the caller to report without re-deriving it. */
  reason: "bytes" | "chunks";
  /** A sentence for the operator. */
  message: string;
};

/**
 * The client's half of the clip ceilings.
 *
 * apps/presence/hearing.py enforces the real ones and drops a breaching clip
 * WHOLE rather than transcribing the part that arrived, because a fluent
 * sentence built from the first half of what was said is worse than an error:
 * nothing downstream can tell it from a good one. So the server is the
 * authority and this is a mirror.
 *
 * It exists because of when each one fires. The server learns the clip is too
 * long at listen_end, after the speaker has finished and waited. Stopping
 * here fires while they are still talking, so the message lands while they
 * still hold the thought. Both refuse the same clip; only the timing differs.
 */
export class ClipBudget {
  readonly maxBytes: number;
  readonly maxChunks: number;
  bytes = 0;
  chunks = 0;

  constructor(maxBytes: number = MAX_CLIP_BYTES, maxChunks: number = MAX_CLIP_CHUNKS) {
    if (!Number.isFinite(maxBytes) || maxBytes <= 0) {
      throw new Error("maxBytes must be a positive number");
    }
    if (!Number.isFinite(maxChunks) || maxChunks <= 0) {
      throw new Error("maxChunks must be a positive number");
    }
    this.maxBytes = maxBytes;
    this.maxChunks = maxChunks;
  }

  /**
   * Whether one more chunk of this size fits, checked BEFORE it is kept, so
   * the ceiling is a ceiling rather than a report of how far past it we
   * already went. Same order as ClipInProgress.append on the server.
   */
  refuse(size: number): ClipRefusal | null {
    if (this.chunks + 1 > this.maxChunks) {
      return {
        reason: "chunks",
        message:
          `That clip reached ${this.maxChunks} chunks, which is the server's ` +
          "ceiling, so nothing was sent. Say it again a little shorter.",
      };
    }
    if (this.bytes + size > this.maxBytes) {
      return {
        reason: "bytes",
        message:
          `That clip reached ${Math.floor(this.maxBytes / (1024 * 1024))} MB, ` +
          "which is the server's ceiling, so nothing was sent. Say it again a " +
          "little shorter.",
      };
    }
    return null;
  }

  /** Record a chunk the caller is about to send. Refuse first. */
  keep(size: number): void {
    this.chunks += 1;
    this.bytes += size;
  }

  reset(): void {
    this.bytes = 0;
    this.chunks = 0;
  }

  /** Seconds of audio held so far at this rate, for the HUD. */
  seconds(rate: number): number {
    if (!Number.isFinite(rate) || rate <= 0) return 0;
    return this.bytes / BYTES_PER_SAMPLE / rate;
  }
}

/**
 * How many worklet blocks to gather before sending one chunk.
 *
 * A worklet hands over 128 samples at a time, which at 48 kHz is 2.67 ms. One
 * socket message per block would be 375 messages a second and would hit the
 * 512 chunk ceiling in under a second and a half of speech, so the ceiling
 * would stop ordinary sentences rather than runaway ones. Gathering to about
 * a quarter second puts a one minute clip at roughly 240 chunks, inside the
 * ceiling with room left.
 */
export function blocksPerChunk(rate: number, blockSize: number, targetMs = 250): number {
  if (!Number.isFinite(rate) || rate <= 0) return 1;
  if (!Number.isFinite(blockSize) || blockSize <= 0) return 1;
  const blocksPerSecond = rate / blockSize;
  const wanted = Math.round((blocksPerSecond * targetMs) / 1000);
  return wanted < 1 ? 1 : wanted;
}
