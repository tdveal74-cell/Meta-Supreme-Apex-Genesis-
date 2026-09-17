/**
 * Presence wire protocol v2: JSON text over WebSocket between the web
 * client and the presence server.
 *
 * Pure module: no browser or Node APIs, no enums, no parameter properties,
 * no namespaces, so Node's type stripping can run it unchanged for the
 * scripts/presence-check.ts proof.
 *
 * v2 adds the ear: `listen_start`, `listen_chunk` and `listen_end` carry one
 * push to talk clip up, and `transcript` carries back what the server heard
 * before it runs the turn. v1 carried no audio in this direction at all.
 *
 * THE VERSION IS NEGOTIATED, NOT PINNED, ON BOTH SIDES NOW.
 *
 * This file used to refuse any `ready` whose protocol was not its own, and
 * apps/presence/protocol.py used to refuse any `hello` that was not the
 * server's. Those two pins faced each other across services that deploy
 * separately, so bumping either one alone blacked out every open page while
 * /health still read healthy. PR #257 fixed the server half: it accepts any
 * version in SUPPORTED_PROTOCOLS and echoes back the one the client asked
 * for.
 *
 * Fixing only the server half would leave the same trap facing the other
 * way. A client pinned at 2 talking to a server rolled back to 1 gets a
 * `ready` carrying 1, refuses it, and blacks out for exactly the reason the
 * server pin used to. So this side accepts any version it supports too, and
 * the negotiated number rides on the parsed message. A caller that wants to
 * send `listen_*` asks whether the number it got back is 2 or better rather
 * than assuming.
 */

/** The version this client asks for in `hello`. */
export const PROTOCOL_VERSION = 2;

/** Every version this client can speak, so a `ready` can be negotiated down. */
export const SUPPORTED_PROTOCOLS: readonly number[] = [1, 2];

/** The first version that carries the ear. Below it, `listen_*` is refused. */
export const LISTEN_MIN_PROTOCOL = 2;

/**
 * Codecs the server accepts in `listen_start`, from apps/presence/protocol.py
 * LISTEN_CODECS. `pcm_s16le` is the AudioWorklet lane: headerless little
 * endian 16 bit samples that the server wraps in a RIFF header before it
 * uploads them.
 */
export const LISTEN_CODECS = ["pcm_s16le", "webm_opus"] as const;
export type ListenCodec = (typeof LISTEN_CODECS)[number];

/** Sample rates the server accepts for pcm_s16le, from LISTEN_RATES. */
export const LISTEN_RATES = [16000, 24000, 44100, 48000] as const;
export type ListenRate = (typeof LISTEN_RATES)[number];

/**
 * Clip ceilings, mirrored from apps/presence/protocol.py MAX_CLIP_BYTES and
 * MAX_CLIP_CHUNKS so the client can stop before it sends a clip the server
 * will drop whole. Mirrored, not authoritative: the server enforces these and
 * closes with 4503 if a client ignores them. Checking here turns a dropped
 * clip into a message the speaker can act on while still holding the thought.
 */
export const MAX_CLIP_BYTES = 8 * 1024 * 1024;
export const MAX_CLIP_CHUNKS = 512;

/** The 52 ARKit blendshape names, in Apple's documented order. */
export const ARKIT_BLENDSHAPES = [
  "eyeBlinkLeft",
  "eyeLookDownLeft",
  "eyeLookInLeft",
  "eyeLookOutLeft",
  "eyeLookUpLeft",
  "eyeSquintLeft",
  "eyeWideLeft",
  "eyeBlinkRight",
  "eyeLookDownRight",
  "eyeLookInRight",
  "eyeLookOutRight",
  "eyeLookUpRight",
  "eyeSquintRight",
  "eyeWideRight",
  "jawForward",
  "jawLeft",
  "jawRight",
  "jawOpen",
  "mouthClose",
  "mouthFunnel",
  "mouthPucker",
  "mouthLeft",
  "mouthRight",
  "mouthSmileLeft",
  "mouthSmileRight",
  "mouthFrownLeft",
  "mouthFrownRight",
  "mouthDimpleLeft",
  "mouthDimpleRight",
  "mouthStretchLeft",
  "mouthStretchRight",
  "mouthRollLower",
  "mouthRollUpper",
  "mouthShrugLower",
  "mouthShrugUpper",
  "mouthPressLeft",
  "mouthPressRight",
  "mouthLowerDownLeft",
  "mouthLowerDownRight",
  "mouthUpperUpLeft",
  "mouthUpperUpRight",
  "browDownLeft",
  "browDownRight",
  "browInnerUp",
  "browOuterUpLeft",
  "browOuterUpRight",
  "cheekPuff",
  "cheekSquintLeft",
  "cheekSquintRight",
  "noseSneerLeft",
  "noseSneerRight",
  "tongueOut",
] as const;

export type Blendshape = (typeof ARKIT_BLENDSHAPES)[number];

/** Blendshape weights, each 0..1. Missing names read as 0. */
export type Weights = Partial<Record<Blendshape, number>>;

export type PresenceState = "idle" | "listening" | "thinking" | "speaking";
export type FramePriority = 0 | 1 | 2;
export type BreakerState = "closed" | "open" | "half_open";
export type SpeechProvider = "mock" | "cartesia";

/* Client to server. */

export type HelloMessage = {
  t: "hello";
  token: string;
  client: "web";
  protocol: number;
};

export type SayMessage = { t: "say"; turn_id: string; text: string };

/** Open a clip. The codec and rate are declared here and never re-sent. */
export type ListenStartMessage = {
  t: "listen_start";
  turn_id: string;
  codec: ListenCodec;
  rate: ListenRate;
};

/** One slice of the clip. `seq` counts from zero and never repeats. */
export type ListenChunkMessage = {
  t: "listen_chunk";
  turn_id: string;
  seq: number;
  b64: string;
};

/** Close the clip. The server transcribes what arrived and starts the turn. */
export type ListenEndMessage = { t: "listen_end"; turn_id: string };

export type InterruptMessage = { t: "interrupt"; turn_id: string; at_ms: number };

export type RenderMessage = {
  t: "render";
  turn_id: string;
  behind_ms: number;
  fps: number;
};

export type PingMessage = { t: "ping"; at_ms: number };

export type ClientMessage =
  | HelloMessage
  | SayMessage
  | ListenStartMessage
  | ListenChunkMessage
  | ListenEndMessage
  | InterruptMessage
  | RenderMessage
  | PingMessage;

/* Server to client. */

export type ReadyMessage = {
  t: "ready";
  session_id: string;
  /** The version the server agreed to, which is the one this client asked
   *  for unless the server is older than this build. */
  protocol: number;
  speech: SpeechProvider;
  inference: string;
  fallback: string;
  livekit: { configured: boolean; url: string | null };
};

export type StateMessage = {
  t: "state";
  state: PresenceState;
  turn_id: string | null;
  at_ms: number;
};

export type TokenMessage = { t: "token"; turn_id: string; text: string };

export type FrameMessage = {
  t: "frame";
  turn_id: string;
  seq: number;
  /** Audio timeline milliseconds from speech start. */
  at_ms: number;
  priority: FramePriority;
  weights: Weights;
};

export type AudioMessage = {
  t: "audio";
  turn_id: string;
  seq: number;
  at_ms: number;
  codec: "pcm_s16le";
  rate: 16000;
  b64: string;
};

export type InterruptAckMessage = {
  t: "interrupt_ack";
  turn_id: string;
  flushed_frames: number;
  server_latency_ms: number;
};

export type MetricsMessage = {
  t: "metrics";
  turn_id: string;
  provider: string;
  fell_back: boolean;
  ttft_ms: number;
  breaker: BreakerState;
  frames_sent: number;
  frames_dropped: number;
  tokens: number;
};

/**
 * What the server heard, sent before the turn it will now run.
 *
 * `confidence` is null when the transcriber reported none, and that is kept
 * apart from zero on purpose: MockHearing has no confidence to report, and a
 * zero here would read as "heard, and certain it was nothing", which is the
 * opposite of what it means.
 */
export type TranscriptMessage = {
  t: "transcript";
  turn_id: string;
  text: string;
  confidence: number | null;
  provider: string;
};

export type PongMessage = { t: "pong"; at_ms: number; server_ms: number };

export type ErrorMessage = { t: "error"; code: number; message: string };

export type ServerMessage =
  | ReadyMessage
  | StateMessage
  | TokenMessage
  | FrameMessage
  | AudioMessage
  | InterruptAckMessage
  | MetricsMessage
  | TranscriptMessage
  | PongMessage
  | ErrorMessage;

const BLENDSHAPE_SET: ReadonlySet<string> = new Set<string>(ARKIT_BLENDSHAPES);

export function isBlendshape(name: unknown): name is Blendshape {
  return typeof name === "string" && BLENDSHAPE_SET.has(name);
}

const SUPPORTED_PROTOCOL_SET: ReadonlySet<number> = new Set(SUPPORTED_PROTOCOLS);

/**
 * Whether a negotiated protocol carries the ear.
 *
 * A caller checks this before it opens a clip. Sending `listen_start` to a
 * server that answered 1 is refused there with 4505, which closes the socket,
 * so the page loses the turn it was in the middle of rather than just the
 * recording.
 */
export function canListen(protocol: number): boolean {
  return Number.isFinite(protocol) && protocol >= LISTEN_MIN_PROTOCOL;
}

const PRESENCE_STATES: ReadonlySet<string> = new Set(["idle", "listening", "thinking", "speaking"]);
const BREAKER_STATES: ReadonlySet<string> = new Set(["closed", "open", "half_open"]);
const SPEECH_PROVIDERS: ReadonlySet<string> = new Set(["mock", "cartesia"]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

/**
 * Validate a frame's weights. Unknown names are dropped, since nothing on the
 * client can map them; a value that is not a finite number makes the whole
 * frame malformed rather than being guessed at. Values are clamped to 0..1.
 */
function parseWeights(value: unknown): Weights | null {
  if (!isRecord(value)) return null;
  const weights: Weights = {};
  for (const key of Object.keys(value)) {
    const raw = value[key];
    if (!isFiniteNumber(raw)) return null;
    if (!isBlendshape(key)) continue;
    weights[key] = raw < 0 ? 0 : raw > 1 ? 1 : raw;
  }
  return weights;
}

/**
 * Parse one server message. Returns null for anything that is not valid
 * JSON, not an object, not a known message type, or a known type with a
 * missing or mistyped field. Never throws.
 */
export function parseServerMessage(raw: string): ServerMessage | null {
  if (typeof raw !== "string" || raw.length === 0) return null;
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!isRecord(value)) return null;
  const t = value.t;
  if (!isString(t)) return null;

  switch (t) {
    case "ready": {
      const livekit = value.livekit;
      if (
        !isString(value.session_id) ||
        !isFiniteNumber(value.protocol) ||
        !SUPPORTED_PROTOCOL_SET.has(value.protocol) ||
        !isString(value.speech) ||
        !SPEECH_PROVIDERS.has(value.speech) ||
        !isString(value.inference) ||
        !isString(value.fallback) ||
        !isRecord(livekit) ||
        typeof livekit.configured !== "boolean" ||
        !(livekit.url === null || isString(livekit.url))
      ) {
        return null;
      }
      return {
        t,
        session_id: value.session_id,
        protocol: value.protocol,
        speech: value.speech as SpeechProvider,
        inference: value.inference,
        fallback: value.fallback,
        livekit: { configured: livekit.configured, url: livekit.url },
      };
    }
    case "state": {
      if (
        !isString(value.state) ||
        !PRESENCE_STATES.has(value.state) ||
        !(value.turn_id === null || isString(value.turn_id)) ||
        !isFiniteNumber(value.at_ms)
      ) {
        return null;
      }
      return {
        t,
        state: value.state as PresenceState,
        turn_id: value.turn_id,
        at_ms: value.at_ms,
      };
    }
    case "token": {
      if (!isString(value.turn_id) || !isString(value.text)) return null;
      return { t, turn_id: value.turn_id, text: value.text };
    }
    case "frame": {
      const priority = value.priority;
      if (
        !isString(value.turn_id) ||
        !isFiniteNumber(value.seq) ||
        !isFiniteNumber(value.at_ms) ||
        !(priority === 0 || priority === 1 || priority === 2)
      ) {
        return null;
      }
      const weights = parseWeights(value.weights);
      if (weights === null) return null;
      return {
        t,
        turn_id: value.turn_id,
        seq: value.seq,
        at_ms: value.at_ms,
        priority,
        weights,
      };
    }
    case "audio": {
      if (
        !isString(value.turn_id) ||
        !isFiniteNumber(value.seq) ||
        !isFiniteNumber(value.at_ms) ||
        value.codec !== "pcm_s16le" ||
        value.rate !== 16000 ||
        !isString(value.b64)
      ) {
        return null;
      }
      return {
        t,
        turn_id: value.turn_id,
        seq: value.seq,
        at_ms: value.at_ms,
        codec: "pcm_s16le",
        rate: 16000,
        b64: value.b64,
      };
    }
    case "interrupt_ack": {
      if (
        !isString(value.turn_id) ||
        !isFiniteNumber(value.flushed_frames) ||
        !isFiniteNumber(value.server_latency_ms)
      ) {
        return null;
      }
      return {
        t,
        turn_id: value.turn_id,
        flushed_frames: value.flushed_frames,
        server_latency_ms: value.server_latency_ms,
      };
    }
    case "metrics": {
      if (
        !isString(value.turn_id) ||
        !isString(value.provider) ||
        typeof value.fell_back !== "boolean" ||
        !isFiniteNumber(value.ttft_ms) ||
        !isString(value.breaker) ||
        !BREAKER_STATES.has(value.breaker) ||
        !isFiniteNumber(value.frames_sent) ||
        !isFiniteNumber(value.frames_dropped) ||
        !isFiniteNumber(value.tokens)
      ) {
        return null;
      }
      return {
        t,
        turn_id: value.turn_id,
        provider: value.provider,
        fell_back: value.fell_back,
        ttft_ms: value.ttft_ms,
        breaker: value.breaker as BreakerState,
        frames_sent: value.frames_sent,
        frames_dropped: value.frames_dropped,
        tokens: value.tokens,
      };
    }
    case "transcript": {
      const confidence = value.confidence;
      if (
        !isString(value.turn_id) ||
        !isString(value.text) ||
        !(confidence === null || isFiniteNumber(confidence)) ||
        !isString(value.provider)
      ) {
        return null;
      }
      return {
        t,
        turn_id: value.turn_id,
        text: value.text,
        confidence: confidence === null ? null : confidence,
        provider: value.provider,
      };
    }
    case "pong": {
      if (!isFiniteNumber(value.at_ms) || !isFiniteNumber(value.server_ms)) return null;
      return { t, at_ms: value.at_ms, server_ms: value.server_ms };
    }
    case "error": {
      if (!isFiniteNumber(value.code) || !isString(value.message)) return null;
      return { t, code: value.code, message: value.message };
    }
    default:
      return null;
  }
}
