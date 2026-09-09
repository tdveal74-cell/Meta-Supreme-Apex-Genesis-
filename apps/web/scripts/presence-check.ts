/**
 * Proof for the three pure presence modules. No test framework: node:assert
 * and a plain process exit code. Run from apps/web:
 *
 *   node --experimental-strip-types scripts/presence-check.ts
 *
 * The explicit ".ts" extensions are for Node's resolver; tsconfig carries
 * allowImportingTsExtensions so tsc accepts them too.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  ARKIT_BLENDSHAPES,
  isBlendshape,
  parseServerMessage,
} from "../lib/presence/protocol.ts";
import { FrameBuffer, lerpWeights } from "../lib/presence/frame-buffer.ts";
import { VoiceActivityDetector } from "../lib/presence/vad.ts";
import {
  CELL_WIDTH,
  DEFAULT_GRID,
  NARROWEST_FEATURE_RADIUS,
  ambientWave,
  applyField,
  buildGridEdges,
  buildGridPlane,
  faceRelief,
  vertexCount,
  writeDepthColors,
} from "../components/presence/face-mesh.ts";
import {
  PCM_RATE,
  PLAYBACK_LEAD_S,
  base64ToBytes,
  durationSeconds,
  pcmToFloat32,
  placeChunk,
} from "../lib/presence/pcm-player.ts";

let checks = 0;
function check(name: string, run: () => void): void {
  run();
  checks += 1;
  console.log(`ok ${checks} ${name}`);
}

/* protocol */

check("ARKit list carries 52 distinct names", () => {
  assert.equal(ARKIT_BLENDSHAPES.length, 52);
  assert.equal(new Set(ARKIT_BLENDSHAPES).size, 52);
  assert.equal(ARKIT_BLENDSHAPES[0], "eyeBlinkLeft");
  assert.equal(ARKIT_BLENDSHAPES[51], "tongueOut");
  assert.ok(isBlendshape("jawOpen"));
  assert.ok(!isBlendshape("JawOpen"));
  assert.ok(!isBlendshape(42));
});

check("parseServerMessage rejects garbage without throwing", () => {
  const garbage = [
    "",
    "not json",
    "{",
    "null",
    "42",
    "[]",
    '"frame"',
    "{}",
    '{"t":"unknown"}',
    '{"t":42}',
    '{"t":"frame"}',
    '{"t":"frame","turn_id":"a","seq":1,"at_ms":10,"priority":3,"weights":{}}',
    '{"t":"frame","turn_id":"a","seq":1,"at_ms":10,"priority":0,"weights":{"jawOpen":"wide"}}',
    '{"t":"frame","turn_id":"a","seq":1,"at_ms":10,"priority":0,"weights":[]}',
    '{"t":"state","state":"dancing","turn_id":null,"at_ms":1}',
    '{"t":"state","state":"idle","turn_id":null}',
    '{"t":"ready","session_id":"s","protocol":2,"speech":"mock","inference":"x","fallback":"y","livekit":{"configured":false,"url":null}}',
    '{"t":"ready","session_id":"s","protocol":1,"speech":"mock","inference":"x","fallback":"y","livekit":{"configured":"no","url":null}}',
    '{"t":"metrics","turn_id":"a","provider":"p","fell_back":false,"ttft_ms":1,"breaker":"tripped","frames_sent":1,"frames_dropped":0,"tokens":1}',
    '{"t":"audio","turn_id":"a","seq":1,"at_ms":0,"codec":"opus","rate":16000,"b64":""}',
    '{"t":"error","code":"401","message":"nope"}',
    '{"t":"pong","at_ms":1}',
  ];
  for (const raw of garbage) {
    assert.equal(parseServerMessage(raw), null, `should reject: ${raw}`);
  }
});

check("parseServerMessage accepts a valid frame and clamps weights", () => {
  const raw = JSON.stringify({
    t: "frame",
    turn_id: "turn-1",
    seq: 7,
    at_ms: 233.5,
    priority: 1,
    weights: { jawOpen: 0.4, browInnerUp: 1.7, eyeBlinkLeft: -0.2, notAShape: 0.9 },
  });
  const message = parseServerMessage(raw);
  assert.ok(message !== null);
  assert.equal(message.t, "frame");
  if (message.t !== "frame") throw new Error("unreachable");
  assert.equal(message.turn_id, "turn-1");
  assert.equal(message.seq, 7);
  assert.equal(message.at_ms, 233.5);
  assert.equal(message.priority, 1);
  assert.deepEqual(message.weights, { jawOpen: 0.4, browInnerUp: 1, eyeBlinkLeft: 0 });
});

check("parseServerMessage accepts every other server type", () => {
  const valid = [
    '{"t":"ready","session_id":"s","protocol":1,"speech":"mock","inference":"mock-llm","fallback":"none","livekit":{"configured":false,"url":null}}',
    '{"t":"ready","session_id":"s","protocol":1,"speech":"cartesia","inference":"x","fallback":"y","livekit":{"configured":true,"url":"wss://lk.example"}}',
    '{"t":"state","state":"speaking","turn_id":"a","at_ms":12}',
    '{"t":"state","state":"idle","turn_id":null,"at_ms":0}',
    '{"t":"token","turn_id":"a","text":"hel"}',
    '{"t":"audio","turn_id":"a","seq":1,"at_ms":0,"codec":"pcm_s16le","rate":16000,"b64":"AAAA"}',
    '{"t":"interrupt_ack","turn_id":"a","flushed_frames":3,"server_latency_ms":12.5}',
    '{"t":"metrics","turn_id":"a","provider":"mock","fell_back":false,"ttft_ms":180,"breaker":"closed","frames_sent":90,"frames_dropped":2,"tokens":40}',
    '{"t":"pong","at_ms":1,"server_ms":2}',
    '{"t":"error","code":401,"message":"bad token"}',
  ];
  for (const raw of valid) {
    const message = parseServerMessage(raw);
    assert.ok(message !== null, `should accept: ${raw}`);
    assert.equal(message.t, JSON.parse(raw).t);
  }
});

/* frame buffer */

function frame(seq: number, at_ms: number, priority: 0 | 1 | 2, jawOpen = 0) {
  return { turn_id: "t", seq, at_ms, priority, weights: { jawOpen } };
}

check("FrameBuffer.sample picks the newest frame at or before the clock", () => {
  const buffer = new FrameBuffer();
  buffer.push(frame(1, 0, 0, 0.1));
  buffer.push(frame(2, 33, 0, 0.2));
  buffer.push(frame(3, 66, 0, 0.3));
  buffer.push(frame(4, 100, 0, 0.4));
  assert.equal(buffer.pushed, 4);

  assert.equal(buffer.sample(-1), null, "nothing due before the first frame");
  assert.equal(buffer.size(), 4);

  const picked = buffer.sample(70);
  assert.ok(picked !== null);
  assert.equal(picked.seq, 3, "seq 3 is the newest at or before 70 ms");
  assert.equal(buffer.size(), 1, "older frames are gone, seq 4 remains");
  assert.equal(buffer.sampled, 1);
  assert.equal(buffer.dropped, 2, "seq 1 and 2 were skipped");

  assert.equal(buffer.sample(99), null, "seq 4 is not due yet");
  const last = buffer.sample(100);
  assert.ok(last !== null);
  assert.equal(last.seq, 4);
  assert.equal(buffer.size(), 0);
  assert.deepEqual(buffer.counters(), { pushed: 4, sampled: 2, dropped: 2 });
});

check("FrameBuffer.push keeps at_ms order for a late frame", () => {
  const buffer = new FrameBuffer();
  buffer.push(frame(1, 0, 0));
  buffer.push(frame(3, 66, 0));
  buffer.push(frame(2, 33, 0));
  assert.deepEqual(
    buffer.frames.map((f) => f.seq),
    [1, 2, 3],
  );
});

check("FrameBuffer.compress drops priority 2, then 1, then thins 0", () => {
  const load = () => {
    const buffer = new FrameBuffer();
    // 12 frames, priorities cycling 0,1,2.
    for (let i = 0; i < 12; i += 1) buffer.push(frame(i, i * 10, (i % 3) as 0 | 1 | 2));
    return buffer;
  };
  const priorities = (buffer: FrameBuffer) => buffer.frames.map((f) => f.priority);

  const calm = load();
  assert.equal(calm.compress(100, 100), 0, "at the window nothing is dropped");
  assert.equal(calm.size(), 12);

  const mild = load();
  assert.equal(mild.compress(101, 100), 4, "one window behind drops the four priority 2 frames");
  assert.ok(!priorities(mild).includes(2));
  assert.ok(priorities(mild).includes(1));
  assert.equal(mild.dropped, 4);

  const worse = load();
  assert.equal(worse.compress(201, 100), 8, "two windows behind drops priority 1 as well");
  assert.deepEqual(priorities(worse), [0, 0, 0, 0]);

  const worst = load();
  assert.equal(worst.compress(301, 100), 10, "three windows behind thins priority 0 to every second frame");
  assert.deepEqual(
    worst.frames.map((f) => f.seq),
    [3, 9],
    "the newest priority 0 frame (seq 9) survives the thinning",
  );
  assert.equal(worst.dropped, 10);
});

check("FrameBuffer.flush empties the buffer and reports the count", () => {
  const buffer = new FrameBuffer();
  buffer.push(frame(1, 0, 0));
  buffer.push(frame(2, 33, 1));
  buffer.push(frame(3, 66, 2));
  assert.equal(buffer.flush(), 3);
  assert.equal(buffer.size(), 0);
  assert.equal(buffer.flush(), 0);
  assert.deepEqual(buffer.counters(), { pushed: 3, sampled: 0, dropped: 3 });
});

check("lerpWeights blends and treats missing names as 0", () => {
  const blended = lerpWeights({ jawOpen: 0.2 }, { jawOpen: 0.6, browInnerUp: 1 }, 0.5);
  assert.deepEqual(blended, { jawOpen: 0.4, browInnerUp: 0.5 });
  assert.deepEqual(lerpWeights({ jawOpen: 1 }, { jawOpen: 0 }, 0), { jawOpen: 1 });
  assert.deepEqual(lerpWeights({ jawOpen: 1 }, { jawOpen: 0 }, 1), { jawOpen: 0 });
  assert.deepEqual(lerpWeights({ jawOpen: 1 }, { jawOpen: 0 }, 5), { jawOpen: 0 }, "alpha is clamped");
});

/* voice activity detector */

check("VAD ignores a click shorter than the 40 ms attack", () => {
  const vad = new VoiceActivityDetector();
  assert.equal(vad.feed(0.5, 0), null);
  assert.equal(vad.feed(0.5, 16), null);
  assert.equal(vad.feed(0.5, 32), null);
  assert.equal(vad.feed(0.001, 48), null, "energy broke before 40 ms");
  assert.equal(vad.speaking, false);
  assert.equal(vad.feed(0.5, 64), null, "the run restarts from silence");
  assert.equal(vad.feed(0.5, 96), null, "32 ms into the new run");
});

check("VAD needs 40 ms of energy to start and 300 ms of silence to end", () => {
  const vad = new VoiceActivityDetector();
  assert.equal(vad.feed(0.05, 1000), null);
  assert.equal(vad.feed(0.05, 1016), null);
  assert.equal(vad.feed(0.05, 1032), null);
  assert.equal(vad.feed(0.05, 1040), "speech_start", "40 ms of sustained energy");
  assert.equal(vad.speaking, true);
  assert.equal(vad.feed(0.05, 1056), null, "no repeat while still speaking");

  assert.equal(vad.feed(0.0, 1100), null, "silence begins");
  assert.equal(vad.feed(0.0, 1300), null, "200 ms of silence is a pause, not an end");
  assert.equal(vad.feed(0.05, 1316), null, "energy resets the hangover");
  assert.equal(vad.feed(0.0, 1400), null);
  assert.equal(vad.feed(0.0, 1699), null, "299 ms");
  assert.equal(vad.feed(0.0, 1700), "speech_end", "300 ms of silence");
  assert.equal(vad.speaking, false);
});

check("VAD honours a custom threshold and windows", () => {
  const vad = new VoiceActivityDetector({ threshold: 0.1, attackMs: 10, hangoverMs: 50 });
  assert.equal(vad.feed(0.05, 0), null, "below the raised threshold");
  assert.equal(vad.feed(0.2, 10), null);
  assert.equal(vad.feed(0.2, 20), "speech_start");
  assert.equal(vad.feed(0.0, 30), null);
  assert.equal(vad.feed(0.0, 80), "speech_end");
  assert.equal(vad.feed(Number.NaN, 90), null, "NaN reads as silence");
});

/* ------------------------------------------------------------------ */
/* The wire field and the face that emerges from it.                   */
/*                                                                    */
/* Ruled by Tee 2026-09-09: the background is the wire mesh and the    */
/* face indents into it when DEVON is active. face-mesh.ts is kept     */
/* pure precisely so that claim can be executed rather than eyeballed. */
/* Three sculpted attempts before this one were judged only by looking */
/* and all three shipped a toy.                                        */
/* ------------------------------------------------------------------ */

check("the field is flat everywhere outside the head", () => {
  assert.equal(faceRelief(2.5, 0), 0, "far to the side");
  assert.equal(faceRelief(0, 1.9), 0, "far above");
  assert.ok(faceRelief(0, 0) > 0.5, "and stands proud at the centre of the face");
});

check("an idle field is nearly flat and an active one carries the face", () => {
  const positions = buildGridPlane(DEFAULT_GRID);
  const face = new Float32Array(vertexCount(DEFAULT_GRID));

  applyField(positions, 0.14, 0, {}, DEFAULT_GRID, face);
  const idle = face.reduce((m, v) => Math.max(m, v), 0);

  applyField(positions, 1, 0, {}, DEFAULT_GRID, face);
  const active = face.reduce((m, v) => Math.max(m, v), 0);

  assert.ok(active > idle * 4, `the face must emerge: idle ${idle}, active ${active}`);
});

check("the mouth opens the surface rather than only moving it", () => {
  const shut = faceRelief(0, -0.56, { jawOpen: 0 });
  const open = faceRelief(0, -0.56, { jawOpen: 1 });
  assert.ok(open < shut, "an open jaw must cut deeper into the sheet");
});

check("a closed lid fills the eye socket back in", () => {
  const openEye = faceRelief(-0.31, 0.24, { blinkLeft: 0 });
  const shutEye = faceRelief(-0.31, 0.24, { blinkLeft: 1 });
  assert.ok(shutEye > openEye, "the socket smooths over on a blink");
});

check("the ambient wave moves and is bounded", () => {
  assert.notEqual(ambientWave(0.4, 0.2, 0), ambientWave(0.4, 0.2, 3), "it must be alive");
  for (let t = 0; t < 12; t += 0.7) {
    for (const x of [-3, -1, 0, 1, 3]) {
      assert.ok(Math.abs(ambientWave(x, x / 2, t)) < 0.1, "the aether never swamps the face");
    }
  }
});

check("the background carries no face light while the wave moves it", () => {
  // THE regression, and the reason this assertion is shaped this way. Colouring
  // by total z let the ambient wave light the whole sheet, so the face washed
  // out into the background. A ratio test does not catch it: the wave lifts the
  // idle and the active peak together and the ratio survives. What catches it is
  // a vertex that is FAR OUTSIDE the head being asked whether it carries any
  // face light at all, at a time when the wave is definitely moving it.
  const positions = buildGridPlane(DEFAULT_GRID);
  const face = new Float32Array(vertexCount(DEFAULT_GRID));
  applyField(positions, 1, 4.2, { jawOpen: 0.5 }, DEFAULT_GRID, face);

  let checkedOutside = 0;
  for (let v = 0; v < face.length; v += 1) {
    const x = positions[v * 3];
    const y = positions[v * 3 + 1];
    if (Math.hypot(x / 0.86, (y - 0.02) / 1.12) < 1.25) continue; // inside or near the face
    checkedOutside += 1;
    assert.equal(
      face[v],
      0,
      `vertex at (${x.toFixed(2)}, ${y.toFixed(2)}) is outside the head and must carry no face light, got ${face[v]}`,
    );
  }
  assert.ok(checkedOutside > 200, `the lattice must extend well past the face, only checked ${checkedOutside}`);
  // And the field really was moving at that moment, so this is not a vacuous pass.
  assert.notEqual(positions[2], 0, "the ambient wave must be displacing the sheet");
});

check("depth maps to light monotonically", () => {
  const face = new Float32Array(4);
  face.set([0, 0.2, 0.45, 0.62]);
  const colors = new Float32Array(12);
  writeDepthColors(face, colors, [0, 0, 0], [1, 1, 1], 0.62);
  assert.equal(colors[0], 0, "a flat vertex stays dark");
  assert.ok(colors[9] > 0.95, "a vertex at full relief is fully lit");
  assert.ok(colors[3] < colors[6] && colors[6] < colors[9], "and it rises monotonically");
});

check("every lattice index points at a real vertex", () => {
  const indices = buildGridEdges(DEFAULT_GRID);
  const total = vertexCount(DEFAULT_GRID);
  assert.ok(indices.length > 0);
  assert.equal(indices.length % 2, 0, "line segments come in pairs");
  for (let i = 0; i < indices.length; i += 1) {
    assert.ok(indices[i] < total, `index ${indices[i]} is outside ${total} vertices`);
  }
});

check("the lattice can actually resolve the narrowest feature", () => {
  // The bug this exists for: the nose was tightened to a radius smaller than a
  // grid cell, so it fell between vertices and rendered as nothing, and the
  // sharpened face came out blurrier than the blunt one it replaced. A feature
  // cannot be sharper than the lattice that samples it.
  const spans = (NARROWEST_FEATURE_RADIUS * 2) / CELL_WIDTH;
  assert.ok(
    spans >= 2.5,
    `the narrowest feature spans ${spans.toFixed(2)} cells; under about 2.5 it disappears. ` +
      "Tighten a feature and you must add columns in the same commit.",
  );
});


/* pcm player: the path by which anything is actually heard */

check("base64 decodes to the exact bytes, and refuses garbage", () => {
  assert.deepEqual(Array.from(base64ToBytes("AAECAw==")), [0, 1, 2, 3]);
  assert.deepEqual(Array.from(base64ToBytes("AAEC")), [0, 1, 2]);
  // Malformed input costs one chunk of audio, never the turn.
  for (const bad of ["!!!", "A", "====", "AA*A"]) {
    assert.equal(base64ToBytes(bad).length, 0, `${bad} decoded to something`);
  }
  assert.equal(base64ToBytes("").length, 0);
});

check("PCM converts signed little endian to the full Float32 range", () => {
  // -32768, 32767, 0. Written as bytes so the endianness is in the test rather
  // than inherited from the host.
  const samples = pcmToFloat32(new Uint8Array([0x00, 0x80, 0xff, 0x7f, 0x00, 0x00]));
  assert.equal(samples.length, 3);
  assert.equal(samples[0], -1);
  assert.ok(Math.abs(samples[1] - 1) < 0.0001);
  assert.equal(samples[2], 0);
  // A negative sample read unsigned would come back positive, which is silence
  // turned into a click and the single most likely mistake here.
  const negative = pcmToFloat32(new Uint8Array([0x18, 0xfc]));
  assert.ok(negative[0] < 0, `expected a negative sample, got ${negative[0]}`);
  // A trailing odd byte is not a sample.
  assert.equal(pcmToFloat32(new Uint8Array([0x01])).length, 0);
});

check("a chunk is placed on the turn's own origin, not on its arrival", () => {
  const start = 10;
  // Arrival order does not matter: at_ms decides the slot.
  assert.equal(placeChunk(0, start, 9).when, 10);
  assert.equal(placeChunk(250, start, 9).when, 10.25);
  assert.equal(placeChunk(1000, start, 9).when, 11);
  assert.equal(placeChunk(250, start, 9).late, false);
});

check("a chunk whose slot has passed plays now rather than being dropped", () => {
  const placement = placeChunk(100, 10, 10.5);
  assert.equal(placement.when, 10.5);
  assert.equal(placement.late, true);
  // A silent drop would be the worse answer: a late syllable still carries a word.
  assert.ok(Number.isFinite(placement.when));
});

check("a chunk with a broken at_ms plays now and is counted late", () => {
  for (const bad of [Number.NaN, Number.POSITIVE_INFINITY]) {
    const placement = placeChunk(bad, 10, 12);
    assert.equal(placement.when, 12);
    assert.equal(placement.late, true);
  }
});

check("the lead is enough to absorb jitter and short enough not to be heard", () => {
  assert.ok(PLAYBACK_LEAD_S > 0, "a zero lead schedules the first chunk in the past");
  assert.ok(PLAYBACK_LEAD_S < 0.2, "a lead over 200 ms is audible as delay");
});

check("the socket hands audio to a player and the stage supplies one", () => {
  // The pure module above can be perfect while nothing calls it, which is the
  // state this repository was actually in: the socket counted every chunk and
  // dropped it. So the wiring is read out of the real files. Both are asserted
  // non trivial first, because a path that no longer exists would otherwise
  // read as an empty string and match nothing forever.
  const socket = readFileSync(
    new URL("../components/presence/usePresenceSocket.ts", import.meta.url),
    "utf8",
  );
  const stage = readFileSync(
    new URL("../components/presence/PresenceStage.tsx", import.meta.url),
    "utf8",
  );
  assert.ok(socket.length > 2000, "usePresenceSocket.ts did not read");
  assert.ok(stage.length > 2000, "PresenceStage.tsx did not read");
  // Both halves, and this is why. The first version of this check looked only
  // for /onAudioRef\.current/, and a mutation that replaced the handler with a
  // null literal still passed: the ref ASSIGNMENT at the top of the hook also
  // matches that pattern. An assertion that survives the mutation it names is
  // not an assertion. So the read and the CALL are both required.
  assert.ok(
    /const handler = onAudioRef\.current/.test(socket),
    "the socket no longer reads the audio handler",
  );
  assert.ok(
    /\bhandler\(message\)/.test(socket),
    "the socket reads an audio handler and never calls it",
  );
  assert.ok(
    /case "audio"/.test(socket) && !/does not decode or play it/.test(socket),
    "the socket still describes itself as dropping audio",
  );
  assert.ok(
    /onAudio:\s*playback\.play/.test(stage),
    "PresenceStage no longer supplies a player to the socket",
  );
  assert.ok(
    /playback\.unlock/.test(stage),
    "PresenceStage offers no way to satisfy the autoplay gesture",
  );
});

check("barge-in stops the voice, not only the face", () => {
  // A fresh critic measured this gap on 2026-09-09: `stop` was exported with a
  // comment saying barge-in needed it, and nothing called it. Flushing the frame
  // buffer froze the mouth at once while every source already scheduled played
  // on, and the presence service sends audio unpaced, so the browser can be
  // holding seconds of the reply. DEVON talked over the interruption until the
  // next turn's first chunk happened to trigger the turn-change stop.
  const stage = readFileSync(
    new URL("../components/presence/PresenceStage.tsx", import.meta.url),
    "utf8",
  );
  assert.ok(stage.length > 2000, "PresenceStage.tsx did not read");
  const handler = stage.slice(
    stage.indexOf("const onBargeIn = useCallback("),
    stage.indexOf("const sendInterrupt = useCallback("),
  );
  assert.ok(handler.length > 40, "the onBargeIn handler could not be located");
  assert.ok(
    /buffer\.flush\(\)/.test(handler),
    "barge-in no longer flushes the face frames",
  );
  assert.ok(
    /stopPlayback\(\)|playback\.stop\(\)/.test(handler),
    "barge-in flushes the face and leaves the voice talking",
  );
});

check("duration is read from the bytes at the presence rate", () => {
  assert.equal(PCM_RATE, 16000);
  // 100 ms at 16 kHz is 1600 samples, which is 3200 bytes.
  assert.ok(Math.abs(durationSeconds(new Uint8Array(3200)) - 0.1) < 1e-9);
  assert.equal(durationSeconds(new Uint8Array(0)), 0);
});

/* base URL resolution */

/*
 * A deployed page has to reach the services it talks to. Until 2026-09-09
 * PRESENCE_BASE had no production branch, so a production build resolved it to
 * http://localhost:8010 and /presence dialled whichever machine was viewing it.
 *
 * The first version of this guard asserted that the declaration contained a
 * NODE_ENV branch and that SOME url in it was non loopback https. A fresh
 * critic broke it three ways on 2026-09-09 and each one shipped the original
 * bug to the browser with the guard reporting green:
 *
 *   1. Swap the ternary arms. Production points at localhost, the block still
 *      contains a good looking https url, 31 checks passed.
 *   2. Revert the code and leave the fix in a comment underneath. The slice ran
 *      to the next declaration, so it swallowed the comment.
 *   3. Group the WebSocket bases at the bottom. API_BASE's slice then swallowed
 *      PRESENCE_BASE's evidence and API_BASE itself went unguarded.
 *
 * So this version strips comments, bounds each declaration at its own
 * semicolon, and reads the PRODUCTION arm of the ternary specifically. It also
 * checks that the env override is consulted before the fallback, because
 * reversing that order silently kills NEXT_PUBLIC_PRESENCE_URL, which the
 * compose deployment requires.
 *
 * The cost of reading the arm literally is that the ternary has to stay inline.
 * Extracting it into a helper is a legitimate refactor that this guard refuses,
 * and the message says so rather than reporting a missing branch.
 */

const SERVICE_BASES = [
  { name: "API_BASE", env: "NEXT_PUBLIC_API_URL" },
  { name: "PRESENCE_BASE", env: "NEXT_PUBLIC_PRESENCE_URL" },
] as const;

function withoutComments(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .split("\n")
    .filter((line) => !line.trim().startsWith("//"))
    .join("\n");
}

function declarationBody(source: string, name: string): string {
  const at = source.indexOf(`export const ${name} =`);
  assert.ok(at >= 0, `${name} is not declared in lib/api-base.ts`);
  const end = source.indexOf(";", at);
  assert.ok(end > at, `${name}'s declaration never terminates with a semicolon`);
  return source.slice(at, end + 1);
}

function unreachableFromABrowser(hostname: string): boolean {
  const host = hostname.toLowerCase();
  return (
    host === "localhost" ||
    host === "0.0.0.0" ||
    host === "::1" ||
    host === "host.docker.internal" ||
    host.endsWith(".local") ||
    /^127\./.test(host) ||
    /^10\./.test(host) ||
    /^192\.168\./.test(host) ||
    /^172\.(1[6-9]|2\d|3[01])\./.test(host)
  );
}

check("each service base reaches a real host in a production build", () => {
  const source = withoutComments(
    readFileSync(new URL("../lib/api-base.ts", import.meta.url), "utf8"),
  );
  assert.ok(source.length > 200, "lib/api-base.ts did not read");

  for (const { name, env } of SERVICE_BASES) {
    const body = declarationBody(source, name);

    const envAt = body.indexOf(`process.env.${env}`);
    const branchAt = body.indexOf("process.env.NODE_ENV");
    assert.ok(envAt >= 0, `${name} no longer reads ${env}, so nothing can override it`);
    assert.ok(
      branchAt >= 0,
      `${name} has no inline NODE_ENV ternary. This guard reads the production arm ` +
        `literally, so the ternary must stay inline in the declaration.`,
    );
    assert.ok(
      envAt < branchAt,
      `${name} consults NODE_ENV before ${env}, so setting ${env} would never win`,
    );

    const ternary = body.match(
      /process\.env\.NODE_ENV\s*===\s*(['"`])production\1\s*\?\s*(['"`])([^'"`]*)\2\s*:\s*(['"`])([^'"`]*)\4/,
    );
    assert.ok(
      ternary !== null,
      `${name}'s production branch is not a literal ternary this guard can read`,
    );
    const production = ternary[3];
    const development = ternary[5];

    assert.ok(
      production.startsWith("https://"),
      `${name}'s PRODUCTION arm is ${JSON.stringify(production)}, which an https page cannot reach`,
    );
    assert.ok(
      !production.endsWith("/"),
      `${name}'s PRODUCTION arm has a trailing slash, so every path built from it doubles the separator`,
    );
    const hostname = new URL(production).hostname;
    assert.ok(
      !unreachableFromABrowser(hostname),
      `${name}'s PRODUCTION arm is ${JSON.stringify(production)}, an address no deployed browser can reach`,
    );
    assert.ok(development.length > 0, `${name}'s development arm is empty`);
  }
});

console.log(`presence-check: ${checks} checks passed`);
