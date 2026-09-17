/**
 * Does a real Web Audio implementation give the capture worklet every sample,
 * once, in order?
 *
 * Run from apps/web:
 *
 *   node --experimental-strip-types scripts/capture-check.mjs
 *
 * WHY A BROWSER AND NOT ANOTHER PURE CHECK
 *
 * `scripts/presence-check.ts` proves the arithmetic in `lib/presence/capture.ts`:
 * the PCM conversion against its own edges, the base64 against Node's Buffer,
 * the clip ceilings against the server's. None of that can prove the one claim
 * the whole ear rests on, which is that `public/presence/capture-worklet.js`
 * hands over a CONTIGUOUS stream.
 *
 * That claim is the reason the worklet exists at all. useBargeIn already opens
 * the microphone and already runs an AnalyserNode, and reusing it would have
 * been less code. An AnalyserNode answers "is someone talking": each
 * getFloatTimeDomainData copies whatever is in its window right now, so two
 * reads a frame apart overlap or skip depending on when the frame landed. Fed
 * to a transcriber that produces a fluent sentence nobody said, which is the
 * failure apps/presence/hearing.py's wav_from_pcm docstring is written against
 * and the one no assertion about types would catch.
 *
 * So a known tone goes in and the concatenated chunks are measured. A dropped
 * block, a duplicated block or a reordered one moves the recovered frequency
 * and changes the sample count. Offline rather than live because it is
 * deterministic and needs no microphone: a fake capture device would test
 * Chromium's tone generator as much as this code.
 *
 * IT DRIVES THE SHIPPED WORKLET, NOT A COPY OF IT
 *
 * The file under `public/` is served to the page over HTTP and loaded by the
 * same `addModule` URL `usePushToTalk.ts` uses, so a mutation to the shipped
 * worklet turns these checks red. audio-check.mjs records what it cost to
 * learn that: its first version re-wrote the hook's calls inside
 * `page.evaluate`, and a mutation to the real hook left all six checks green.
 *
 * It is served from 127.0.0.1 rather than a data: or blob: URL because
 * `audioWorklet` is undefined outside a secure context, and an opaque origin
 * is not one. Measured, not assumed: on about:blank this file's first run died
 * with "Cannot read properties of undefined (reading 'addModule')".
 *
 * Both Playwright and Chromium are resolved from the environment and both
 * THROW when missing, so a runner without them turns the job red rather than
 * green, which is the direction that matters.
 */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { createServer } from "node:http";
import {
  BYTES_PER_SAMPLE,
  ClipBudget,
  blocksPerChunk,
  bytesToBase64,
  floatToPcm16,
} from "../lib/presence/capture.ts";

const WORKLET_PATH = new URL("../public/presence/capture-worklet.js", import.meta.url).pathname;
const WORKLET_URL_PATH = "/presence/capture-worklet.js";

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
      "no Chromium binary found. Set CHROMIUM_BINARY. Tried: " + CHROME_CANDIDATES.join(", "),
    );
  }
  return found;
}

let checks = 0;
function check(name, run) {
  run();
  checks += 1;
  console.log(`ok ${checks} ${name}`);
}

const CONTEXT_RATE = 48000;
const SECONDS = 1;
const TONE_HZ = 440;
const BLOCK = 128;
const PER_CHUNK = blocksPerChunk(CONTEXT_RATE, BLOCK);

const workletSource = readFileSync(WORKLET_PATH, "utf8");
const server = createServer((request, response) => {
  if (request.url === WORKLET_URL_PATH) {
    response.writeHead(200, { "content-type": "text/javascript" });
    response.end(workletSource);
    return;
  }
  response.writeHead(200, { "content-type": "text/html" });
  response.end("<!doctype html><title>capture check</title>");
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const { port } = server.address();

const { chromium } = await loadPlaywright();
const executablePath = findChromium();
const browser = await chromium.launch({ executablePath });

let captured;
try {
  const page = await browser.newPage();
  await page.goto(`http://127.0.0.1:${port}/`);
  captured = await page.evaluate(
    async ({ url, perChunk, rate, seconds, hz }) => {
      const ctx = new OfflineAudioContext(1, Math.ceil(rate * seconds), rate);
      await ctx.audioWorklet.addModule(url);
      const node = new AudioWorkletNode(ctx, "presence-capture", {
        numberOfInputs: 1,
        numberOfOutputs: 0,
        channelCount: 1,
        processorOptions: { blocksPerChunk: perChunk },
      });
      const osc = ctx.createOscillator();
      osc.type = "sine";
      osc.frequency.value = hz;
      osc.connect(node);
      // Also to the destination: an OfflineAudioContext renders the graph that
      // reaches it, and the worklet is a sink with no output of its own.
      osc.connect(ctx.destination);

      const chunks = [];
      node.port.onmessage = (event) => {
        if (event.data && event.data.t === "chunk") chunks.push(Array.from(event.data.samples));
      };
      node.port.postMessage({ t: "start" });
      osc.start(0);
      await ctx.startRendering();
      // The tail the processor is still holding. Without this flush the last
      // chunk of every clip is lost, which cuts the end off every sentence.
      node.port.postMessage({ t: "stop" });
      await new Promise((resolve) => setTimeout(resolve, 200));

      const lengths = chunks.map((chunk) => chunk.length);
      const samples = [];
      for (const chunk of chunks) for (const value of chunk) samples.push(value);
      return { lengths, samples };
    },
    { url: WORKLET_URL_PATH, perChunk: PER_CHUNK, rate: CONTEXT_RATE, seconds: SECONDS, hz: TONE_HZ },
  );
} finally {
  await browser.close();
  server.close();
}

const { lengths, samples } = captured;

check("the worklet hands over every sample exactly once", () => {
  // The decisive count. One second at 48 kHz is 48000 samples. A dropped block
  // is 128 short, a duplicated one is 128 long, and either would be invisible
  // to a check that only looked at whether chunks arrived.
  assert.equal(
    samples.length,
    CONTEXT_RATE * SECONDS,
    `captured ${samples.length} samples for ${SECONDS}s at ${CONTEXT_RATE} Hz`,
  );
  assert.ok(lengths.length > 1, "a single chunk would not exercise the batching at all");
});

check("the tail is flushed rather than dropped", () => {
  // 48000 does not divide by 12032, so the last chunk is short. If stop() did
  // not flush, that remainder would be lost and every clip would end mid word,
  // which a transcriber completes into a word nobody said.
  const full = PER_CHUNK * BLOCK;
  const remainder = (CONTEXT_RATE * SECONDS) % full;
  assert.ok(remainder > 0, "this fixture is meant to leave a partial chunk");
  assert.equal(lengths[lengths.length - 1], remainder, "the short final chunk is the flushed tail");
  for (const length of lengths.slice(0, -1)) {
    assert.equal(length, full, `a full chunk is ${full} samples, got ${length}`);
  }
});

check("batching matches what blocksPerChunk promised", () => {
  const full = PER_CHUNK * BLOCK;
  const chunkMs = (full * 1000) / CONTEXT_RATE;
  assert.ok(chunkMs > 100 && chunkMs < 400, `chunks every ${chunkMs} ms`);
  assert.ok(
    lengths.length < 512,
    `${lengths.length} chunks a second would blow the server's 512 chunk ceiling`,
  );
});

check("the captured stream is contiguous, which an analyser could not give", () => {
  // This is the whole reason the worklet exists. Concatenate the chunks and
  // count zero crossings: a sine at 440 Hz crosses zero twice a cycle, so one
  // second is about 880. Overlapping or skipped windows destroy this number
  // while leaving the sample count plausible.
  let crossings = 0;
  for (let i = 1; i < samples.length; i += 1) {
    if (samples[i - 1] < 0 !== samples[i] < 0) crossings += 1;
  }
  const seconds = samples.length / CONTEXT_RATE;
  const implied = crossings / 2 / seconds;
  assert.ok(
    Math.abs(implied - TONE_HZ) < 2,
    `recovered ${implied.toFixed(2)} Hz from a ${TONE_HZ} Hz tone, so the stream is not contiguous`,
  );
  let peak = 0;
  for (const value of samples) peak = Math.max(peak, Math.abs(value));
  assert.ok(peak > 0.9, `peak ${peak}, so the worklet captured near silence`);
});

check("what the worklet produced survives the encoder the hook feeds it to", () => {
  // The browser half and the pure half, joined. Everything above proves the
  // worklet; this proves the bytes the hook would actually put on the wire.
  const budget = new ClipBudget();
  const payloads = [];
  let offset = 0;
  for (const length of lengths) {
    const slice = Float32Array.from(samples.slice(offset, offset + length));
    offset += length;
    const bytes = floatToPcm16(slice);
    assert.equal(bytes.length, length * BYTES_PER_SAMPLE);
    assert.equal(budget.refuse(bytes.length), null, "a one second clip is nowhere near the ceiling");
    budget.keep(bytes.length);
    payloads.push(bytesToBase64(bytes));
  }
  assert.equal(budget.chunks, lengths.length);
  assert.equal(budget.bytes, CONTEXT_RATE * SECONDS * BYTES_PER_SAMPLE);
  assert.ok(Math.abs(budget.seconds(CONTEXT_RATE) - SECONDS) < 1e-9);
  for (const payload of payloads) {
    assert.ok(payload.length > 0);
    assert.ok(/^[A-Za-z0-9+/]+={0,2}$/.test(payload), "a listen_chunk b64 the server would reject");
  }
});

console.log(`capture-check: ${checks} checks passed in real Chromium`);
console.log(`chromium: ${executablePath}`);
console.log(`captured ${samples.length} samples in ${lengths.length} chunks at ${CONTEXT_RATE} Hz`);
