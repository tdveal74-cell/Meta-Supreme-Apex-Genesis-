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
import {
  ARKIT_BLENDSHAPES,
  isBlendshape,
  parseServerMessage,
} from "../lib/presence/protocol.ts";
import { FrameBuffer, lerpWeights } from "../lib/presence/frame-buffer.ts";
import { VoiceActivityDetector } from "../lib/presence/vad.ts";

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

console.log(`presence-check: ${checks} checks passed`);
