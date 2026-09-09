/**
 * Does a real Web Audio implementation accept what the playback hook feeds it?
 *
 * Run from apps/web:
 *
 *   node --experimental-strip-types scripts/audio-check.mjs
 *
 * WHY A BROWSER AND NOT ANOTHER PURE CHECK
 *
 * `scripts/presence-check.ts` proves the arithmetic in `lib/presence/pcm-player.ts`.
 * It cannot prove that a buffer declared at 16000 Hz plays at the right pitch
 * inside a context running at 48000, that `copyToChannel` accepts the exact
 * Float32Array the module builds, or that a source started at an offset lands
 * where it was asked to. Those are the mistakes a pure test cannot see, and this
 * repository has already paid for that lesson twice on the avatar: a
 * `meshStandardMaterial` at metalness 0.95 rendered black with no environment
 * map, and additive blending on flat geometry rendered a flat shape, and neither
 * showed up anywhere except in a rendered frame somebody looked at.
 *
 * So the real module produces the samples in Node, real Chromium renders them
 * through an OfflineAudioContext, and the rendered samples are measured.
 * Offline rather than live because it is deterministic and needs no speakers.
 *
 * IT DRIVES THE SHIPPED CODE, NOT A COPY OF IT
 *
 * The first version of this file re-wrote the hook's Web Audio calls inside
 * `page.evaluate` under a comment claiming they were "exactly the calls
 * useAudioPlayback.ts makes". A fresh critic mutated the shipped hook to declare
 * the buffer at the context's own sample rate, the exact chipmunk bug this file
 * exists to catch, and all six checks below still passed, because nothing here
 * executed the code that made the call. Those calls now live in
 * `lib/presence/pcm-player.ts` as `scheduleChunk`, its source is read and
 * evaluated inside the page, and a mutation to it turns these checks red.
 *
 * NOT IN CI, AND WHY THAT IS NOT AN OVERSIGHT
 *
 * This needs Playwright and a Chromium binary. Neither is pinned by this
 * repository or installed by the web workspace, so a CI step would either
 * download a browser on every run or fail on a machine that has one in a
 * different place. Both paths are resolved from the environment below and both
 * are reported when missing, which is the same posture
 * `.claude/skills/scroll-craft` takes toward its own unpinned tooling. Run it by
 * hand when the audio path changes.
 */

import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { readFileSync } from "node:fs";
import {
  PCM_RATE,
  PLAYBACK_LEAD_S,
  pcmToFloat32,
  placeChunk,
} from "../lib/presence/pcm-player.ts";

const PLAYWRIGHT_CANDIDATES = [
  process.env.PLAYWRIGHT_MODULE,
  "/opt/node22/lib/node_modules/playwright/index.mjs",
  "playwright",
].filter(Boolean);

const CHROME_CANDIDATES = [
  process.env.CHROMIUM_BINARY,
  "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
  "/opt/pw-browsers/chromium/chrome-linux/chrome",
  "/usr/bin/chromium",
  "/usr/bin/google-chrome",
].filter(Boolean);

async function loadPlaywright() {
  for (const candidate of PLAYWRIGHT_CANDIDATES) {
    try {
      return await import(candidate);
    } catch {
      // Try the next one. The failure is reported once, below.
    }
  }
  throw new Error(
    "playwright could not be imported. Set PLAYWRIGHT_MODULE to its index.mjs, " +
      `or install it. Tried: ${PLAYWRIGHT_CANDIDATES.join(", ")}`,
  );
}

function findChromium() {
  const found = CHROME_CANDIDATES.find((path) => path.startsWith("/") && existsSync(path));
  if (!found) {
    throw new Error(
      "no Chromium binary found. Set CHROMIUM_BINARY. Tried: " +
        CHROME_CANDIDATES.join(", "),
    );
  }
  return found;
}

/**
 * A 400 Hz square wave at half scale, 100 ms long, built as little endian bytes.
 *
 * Written out as bytes rather than as samples so the wire format is in the
 * fixture instead of inherited from the host: an unsigned or byte swapped read
 * of this fixture produces a DC offset with no zero crossings at all, which the
 * pitch check below catches.
 */
const DURATION_S = 0.1;
const TONE_HZ = 400;
const AMPLITUDE = 16384;
const SAMPLE_COUNT = Math.round(PCM_RATE * DURATION_S);
const bytes = new Uint8Array(SAMPLE_COUNT * 2);
for (let index = 0; index < SAMPLE_COUNT; index += 1) {
  const period = PCM_RATE / TONE_HZ;
  const value = index % period < period / 2 ? AMPLITUDE : -AMPLITUDE;
  bytes[index * 2] = value & 0xff;
  bytes[index * 2 + 1] = (value >> 8) & 0xff;
}

/** The chunk claims to sit 250 ms into the utterance. */
const AT_MS = 250;

const samples = Array.from(pcmToFloat32(bytes));
const placement = placeChunk(AT_MS, PLAYBACK_LEAD_S, 0);
assert.equal(placement.late, false, "the fixture's own placement is already late");

/**
 * The shipped scheduler's own source, for evaluation inside the page.
 *
 * A browser cannot import a .ts module, and bundling for one check would put a
 * build step between the code and its proof. So the two functions are cut out of
 * the real file by name and their type annotations stripped. Both are asserted
 * present first: a rename that silently matched nothing would leave these checks
 * measuring an empty string and passing forever, which is the failure mode this
 * whole file was written in response to.
 */
const MODULE_SOURCE = readFileSync(
  new URL("../lib/presence/pcm-player.ts", import.meta.url),
  "utf8",
);

function cutFunction(name) {
  const start = MODULE_SOURCE.indexOf(`export function ${name}(`);
  assert.notEqual(start, -1, `${name} is no longer exported from pcm-player.ts`);
  // Functions in this module are top level, so the first line that is exactly a
  // closing brace ends it.
  const end = MODULE_SOURCE.indexOf("\n}\n", start);
  assert.notEqual(end, -1, `could not find the end of ${name}`);
  return MODULE_SOURCE.slice(start, end + 3);
}

const SHIPPED_SCHEDULER = [cutFunction("placeChunk"), cutFunction("scheduleChunk")]
  .join("\n")
  .replaceAll("export function", "function")
  // Strip the type annotations a browser cannot parse. Deliberately narrow: only
  // the annotations these two functions actually carry.
  .replace(/:\s*Placement\b/g, "")
  .replace(/:\s*Scheduled\b/g, "")
  .replace(/(\w+)\s*:\s*AudioSink/g, "$1")
  .replace(/(\w+)\s*:\s*Float32Array<ArrayBuffer>/g, "$1")
  .replace(/(\w+)\s*:\s*number\s*=\s*0/g, "$1 = 0")
  .replace(/(\w+)\s*:\s*number/g, "$1");

assert.ok(
  SHIPPED_SCHEDULER.includes("createBuffer(1, samples.length, PCM_RATE)"),
  "scheduleChunk no longer declares the buffer at the presence rate",
);
assert.ok(
  SHIPPED_SCHEDULER.includes("source.start(placement.when)"),
  "scheduleChunk no longer starts the source at its placed slot",
);

const { chromium } = await loadPlaywright();
const executablePath = findChromium();
const browser = await chromium.launch({ executablePath });
let result;
let late;
try {
  const page = await browser.newPage();
  result = await page.evaluate(
    async ({ samples, rate, totalS, atMs, lead, scheduler }) => {
      const contextRate = 48000;
      const ctx = new OfflineAudioContext(1, Math.ceil(contextRate * totalS), contextRate);
      // The shipped scheduler, evaluated. PCM_RATE is its one free variable.
      const PCM_RATE = rate;
      // eslint-disable-next-line no-new-func
      const scheduleChunk = new Function(
        "PCM_RATE",
        `${scheduler}; return scheduleChunk;`,
      )(PCM_RATE);
      const placed = scheduleChunk(ctx, new Float32Array(samples), atMs, lead, 0);
      const declaredRateFromShippedCall = placed.source.buffer.sampleRate;
      const bufferDurationFromShippedCall = placed.source.buffer.duration;
      const rendered = await ctx.startRendering();
      const channel = rendered.getChannelData(0);

      let firstLoud = -1;
      let lastLoud = -1;
      let peak = 0;
      for (let index = 0; index < channel.length; index += 1) {
        const magnitude = Math.abs(channel[index]);
        if (magnitude > peak) peak = magnitude;
        if (magnitude > 0.05) {
          if (firstLoud < 0) firstLoud = index;
          lastLoud = index;
        }
      }
      let crossings = 0;
      for (let index = firstLoud + 1; index <= lastLoud; index += 1) {
        if (channel[index - 1] <= 0 && channel[index] > 0) crossings += 1;
      }
      return {
        contextRate,
        declaredRate: declaredRateFromShippedCall,
        bufferDurationS: bufferDurationFromShippedCall,
        startedAt: placed.when,
        endsAt: placed.endsAt,
        late: placed.late,
        firstLoudS: firstLoud < 0 ? null : firstLoud / contextRate,
        lastLoudS: lastLoud < 0 ? null : lastLoud / contextRate,
        peak,
        crossings,
      };
    },
    {
      samples,
      rate: PCM_RATE,
      totalS: 0.6,
      atMs: AT_MS,
      lead: PLAYBACK_LEAD_S,
      scheduler: SHIPPED_SCHEDULER,
    },
  );
  // Two late chunks, which is what a throttled tab delivers in one task. They
  // must queue behind each other rather than sum: a critic rendered 200 ms of
  // speech collapsing into 100 ms at a peak of 1.0 before `busyUntil` existed.
  late = await page.evaluate(
    async ({ samples, rate, totalS, scheduler }) => {
      const contextRate = 48000;
      const ctx = new OfflineAudioContext(1, Math.ceil(contextRate * totalS), contextRate);
      const PCM_RATE = rate;
      // eslint-disable-next-line no-new-func
      const scheduleChunk = new Function(
        "PCM_RATE",
        `${scheduler}; return scheduleChunk;`,
      )(PCM_RATE);
      const wave = new Float32Array(samples);
      // A timeline origin in the past, so both chunks are already overdue.
      const origin = -10;
      let busy = 0;
      for (const atMs of [100, 200]) {
        const placed = scheduleChunk(ctx, wave, atMs, origin, busy);
        busy = Math.max(busy, placed.endsAt);
      }
      const rendered = await ctx.startRendering();
      const channel = rendered.getChannelData(0);
      let first = -1;
      let last = -1;
      let peak = 0;
      for (let index = 0; index < channel.length; index += 1) {
        const magnitude = Math.abs(channel[index]);
        if (magnitude > peak) peak = magnitude;
        if (magnitude > 0.05) {
          if (first < 0) first = index;
          last = index;
        }
      }
      return {
        peak,
        soundedS: first < 0 ? 0 : (last - first) / contextRate,
      };
    },
    { samples, rate: PCM_RATE, totalS: 0.6, scheduler: SHIPPED_SCHEDULER },
  );
} finally {
  await browser.close();
}

console.log(`chromium: ${executablePath}`);
console.log(JSON.stringify(result, null, 2));

let checks = 0;
function check(name, run) {
  run();
  checks += 1;
  console.log(`ok ${checks} ${name}`);
}

check("something sounded at all", () => {
  assert.notEqual(result.firstLoudS, null, "the rendered output is silent");
});

check("a buffer declared at the presence rate keeps that rate", () => {
  assert.equal(result.declaredRate, PCM_RATE);
  assert.equal(result.contextRate, 48000);
});

check("the chunk lands where placeChunk put it, not on arrival", () => {
  const expected = PLAYBACK_LEAD_S + AT_MS / 1000;
  assert.ok(
    Math.abs(result.firstLoudS - expected) < 0.005,
    `sound began at ${result.firstLoudS}s, expected ${expected}s`,
  );
});

check("the audio plays for its own duration, not the context's idea of it", () => {
  // The trap: declaring the buffer at ctx.sampleRate would play 100 ms of
  // 16 kHz audio in 33 ms, an octave and a half high.
  assert.ok(
    Math.abs(result.bufferDurationS - DURATION_S) < 0.001,
    `buffer duration ${result.bufferDurationS}s, expected ${DURATION_S}s`,
  );
  const played = result.lastLoudS - result.firstLoudS;
  assert.ok(
    Math.abs(played - DURATION_S) < 0.01,
    `sounded for ${played}s, expected ${DURATION_S}s`,
  );
});

check("the pitch survives the resample", () => {
  // 400 Hz for 100 ms is 40 cycles, and the edge cycle can be clipped by the
  // 0.05 threshold either side.
  assert.ok(
    result.crossings >= 36 && result.crossings <= 44,
    `${result.crossings} zero crossings, expected about 40 for ${TONE_HZ} Hz`,
  );
});

check("half scale PCM renders at half scale, so the sign read is right", () => {
  assert.ok(
    result.peak > 0.4 && result.peak < 0.6,
    `peak ${result.peak}, expected about 0.5`,
  );
});

check("the shipped scheduler placed it, not this script", () => {
  // If these came from anywhere but scheduleChunk, every check above is theatre.
  assert.equal(result.startedAt, PLAYBACK_LEAD_S + AT_MS / 1000);
  assert.equal(result.late, false);
  assert.ok(
    Math.abs(result.endsAt - (result.startedAt + DURATION_S)) < 0.001,
    `endsAt ${result.endsAt} does not follow from startedAt ${result.startedAt}`,
  );
});

check("two late chunks queue rather than play on top of each other", () => {
  console.log(`  two late chunks: ${JSON.stringify(late)}`);
  // Summing two half scale chunks peaks at 1.0. Queueing them keeps 0.5.
  assert.ok(
    late.peak > 0.4 && late.peak < 0.6,
    `peak ${late.peak}: two late chunks summed instead of queueing`,
  );
  // And 200 ms of speech stays 200 ms rather than collapsing into 100.
  assert.ok(
    Math.abs(late.soundedS - DURATION_S * 2) < 0.01,
    `sounded for ${late.soundedS}s, expected ${DURATION_S * 2}s`,
  );
});

console.log(`audio-check: ${checks} checks passed in real Chromium`);
