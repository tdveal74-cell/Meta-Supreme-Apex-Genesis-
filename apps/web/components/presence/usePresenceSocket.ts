"use client";

/**
 * The presence socket: JSON text over WebSocket to the presence server,
 * protocol v1 (see lib/presence/protocol.ts).
 *
 * The first message is the hello carrying the DEVON access token that the
 * chat and command center already stored at sign-in. The token never goes in
 * the URL. Reconnects back off 1 s, 2 s, 4 s, 8 s, then 15 s, and only while
 * a token exists; a 401 or 403 from the server stops the retries, since the
 * same token would fail the same way.
 *
 * Every "frame" lands in one FrameBuffer held in a ref, which the avatar
 * canvas samples on its own clock.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { PRESENCE_WS_BASE } from "@/lib/api-base";
import { FrameBuffer } from "@/lib/presence/frame-buffer";
import {
  PROTOCOL_VERSION,
  parseServerMessage,
  type AudioMessage,
  type ClientMessage,
  type InterruptAckMessage,
  type MetricsMessage,
  type PresenceState,
  type ReadyMessage,
  type ServerMessage,
} from "@/lib/presence/protocol";

/** The storage slot DevonChat writes at sign-in and RealShell reads. */
export const TOKEN_SLOT = "devon-chat-token";

export function readDevonToken(): string {
  try {
    return localStorage.getItem(TOKEN_SLOT) || sessionStorage.getItem(TOKEN_SLOT) || "";
  } catch {
    return "";
  }
}

export type ConnectionState =
  | { kind: "locked" }
  | { kind: "connecting"; attempt: number }
  | { kind: "ready" }
  | { kind: "closed"; retryInMs: number | null }
  | { kind: "error"; message: string; retryInMs: number | null };

export type PresenceSnapshot = {
  state: PresenceState;
  turnId: string | null;
  /** The server's stamp on the state message (its audio timeline). */
  atMs: number;
  /** performance.now() when the message arrived: the wall clock origin. */
  arrivedAtMs: number;
};

export type SocketDiagnostics = {
  malformed: number;
  strayFrames: number;
  audioChunksIgnored: number;
};

const BACKOFF_MS = [1000, 2000, 4000, 8000, 15000];
const PING_INTERVAL_MS = 5000;

function newTurnId(): string {
  try {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
  } catch {
    // Fall through to the plain id.
  }
  return `turn-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function describe(value: unknown): string {
  if (value instanceof Error) return value.message;
  return String(value);
}

export type PresenceSocketOptions = {
  /**
   * Called for every audio chunk, in arrival order.
   *
   * The socket does not own playback: an AudioContext needs a user gesture and
   * a component's lifetime, neither of which belongs in a WebSocket effect. It
   * is a ref rather than a dependency so changing the handler does not tear the
   * socket down and reconnect.
   */
  onAudio?: (message: AudioMessage) => void;
};

export function usePresenceSocket(token: string, options: PresenceSocketOptions = {}) {
  const onAudioRef = useRef<PresenceSocketOptions["onAudio"]>(undefined);
  onAudioRef.current = options.onAudio;

  const bufferRef = useRef<FrameBuffer | null>(null);
  if (bufferRef.current === null) bufferRef.current = new FrameBuffer();
  const buffer = bufferRef.current;

  const [connection, setConnection] = useState<ConnectionState>({ kind: "locked" });
  const [ready, setReady] = useState<ReadyMessage | null>(null);
  const [presence, setPresence] = useState<PresenceSnapshot>({
    state: "idle",
    turnId: null,
    atMs: 0,
    arrivedAtMs: 0,
  });
  const [caption, setCaption] = useState("");
  const [metrics, setMetrics] = useState<MetricsMessage | null>(null);
  const [lastAck, setLastAck] = useState<InterruptAckMessage | null>(null);
  const [rttMs, setRttMs] = useState<number | null>(null);

  const sendRef = useRef<((message: ClientMessage) => boolean) | null>(null);
  /** Turn named by the latest "say" we sent. */
  const sayTurnRef = useRef<string | null>(null);
  /** Turn named by the latest "state" message. */
  const stateTurnRef = useRef<string | null>(null);
  /** Turn we interrupted locally; its late frames are dropped. */
  const ignoredTurnRef = useRef<string | null>(null);
  const diagnosticsRef = useRef<SocketDiagnostics>({
    malformed: 0,
    strayFrames: 0,
    audioChunksIgnored: 0,
  });

  useEffect(() => {
    if (!token) {
      setConnection({ kind: "locked" });
      setReady(null);
      return;
    }

    let disposed = false;
    let socket: WebSocket | null = null;
    let attempt = 0;
    let retryTimer: number | null = null;
    let pingTimer: number | null = null;
    let haltReason: string | null = null;

    const send = (message: ClientMessage): boolean => {
      if (!socket || socket.readyState !== WebSocket.OPEN) return false;
      socket.send(JSON.stringify(message));
      return true;
    };
    sendRef.current = send;

    const stopPing = () => {
      if (pingTimer !== null) {
        window.clearInterval(pingTimer);
        pingTimer = null;
      }
    };
    const startPing = () => {
      stopPing();
      pingTimer = window.setInterval(() => {
        send({ t: "ping", at_ms: performance.now() });
      }, PING_INTERVAL_MS);
    };

    const scheduleRetry = (): number | null => {
      if (disposed || haltReason) return null;
      const delay = BACKOFF_MS[Math.min(attempt, BACKOFF_MS.length - 1)];
      attempt += 1;
      retryTimer = window.setTimeout(open, delay);
      return delay;
    };

    const turnIsCurrent = (turnId: string) =>
      turnId !== ignoredTurnRef.current &&
      (turnId === stateTurnRef.current || turnId === sayTurnRef.current);

    const handle = (message: ServerMessage) => {
      switch (message.t) {
        case "ready":
          attempt = 0;
          setReady(message);
          setConnection({ kind: "ready" });
          startPing();
          return;
        case "state": {
          const arrivedAtMs = performance.now();
          if (message.turn_id !== null && message.turn_id !== stateTurnRef.current) {
            stateTurnRef.current = message.turn_id;
            if (message.state === "speaking") buffer.resetCounters();
          }
          if (message.state !== "speaking") {
            // Frames stamped on a timeline that is no longer playing.
            buffer.flush();
          }
          setPresence({
            state: message.state,
            turnId: message.turn_id,
            atMs: message.at_ms,
            arrivedAtMs,
          });
          return;
        }
        case "token":
          if (turnIsCurrent(message.turn_id)) {
            setCaption((current) => current + message.text);
          }
          return;
        case "frame":
          if (!turnIsCurrent(message.turn_id)) {
            diagnosticsRef.current.strayFrames += 1;
            return;
          }
          buffer.push({
            turn_id: message.turn_id,
            seq: message.seq,
            at_ms: message.at_ms,
            priority: message.priority,
            weights: message.weights,
          });
          return;
        case "audio": {
          // Raw PCM arrives only when LiveKit is not configured, which is every
          // deployment so far: the presence service mints join tokens and has
          // never published audio into a room. Until this handler existed the
          // chunk was counted and dropped, so nothing in the estate could be
          // heard whether or not the synthesiser worked.
          if (!turnIsCurrent(message.turn_id)) {
            // A chunk from a turn that was interrupted. Playing it would talk
            // over whatever replaced it.
            diagnosticsRef.current.audioChunksIgnored += 1;
            return;
          }
          const handler = onAudioRef.current;
          if (!handler) {
            diagnosticsRef.current.audioChunksIgnored += 1;
            return;
          }
          handler(message);
          return;
        }
        case "interrupt_ack":
          setLastAck(message);
          return;
        case "metrics":
          setMetrics(message);
          return;
        case "pong":
          setRttMs(performance.now() - message.at_ms);
          return;
        case "error":
          if (message.code === 401 || message.code === 403) {
            haltReason = `${message.code}: ${message.message}`;
          }
          setConnection({
            kind: "error",
            message: `${message.code}: ${message.message}`,
            retryInMs: null,
          });
          return;
        default:
          return;
      }
    };

    const open = () => {
      if (disposed) return;
      retryTimer = null;
      setConnection({ kind: "connecting", attempt });
      let ws: WebSocket;
      try {
        ws = new WebSocket(`${PRESENCE_WS_BASE}/ws/presence`);
      } catch (error) {
        const delay = scheduleRetry();
        setConnection({ kind: "error", message: describe(error), retryInMs: delay });
        return;
      }
      socket = ws;

      ws.onopen = () => {
        send({ t: "hello", token, client: "web", protocol: PROTOCOL_VERSION });
      };
      ws.onmessage = (event) => {
        const message = parseServerMessage(String(event.data));
        if (message === null) {
          diagnosticsRef.current.malformed += 1;
          return;
        }
        handle(message);
      };
      ws.onerror = () => {
        // The close event that follows carries the retry.
      };
      ws.onclose = () => {
        if (socket === ws) socket = null;
        stopPing();
        if (disposed) return;
        if (haltReason) {
          setConnection({ kind: "error", message: haltReason, retryInMs: null });
          return;
        }
        const delay = scheduleRetry();
        setConnection((current) =>
          current.kind === "error"
            ? { kind: "error", message: current.message, retryInMs: delay }
            : { kind: "closed", retryInMs: delay },
        );
      };
    };

    open();

    return () => {
      disposed = true;
      sendRef.current = null;
      stopPing();
      if (retryTimer !== null) window.clearTimeout(retryTimer);
      socket?.close();
      socket = null;
    };
  }, [token, buffer]);

  const say = useCallback((text: string): string | null => {
    const trimmed = text.trim();
    if (!trimmed) return null;
    const turnId = newTurnId();
    sayTurnRef.current = turnId;
    ignoredTurnRef.current = null;
    setCaption("");
    const sent = sendRef.current?.({ t: "say", turn_id: turnId, text: trimmed }) ?? false;
    return sent ? turnId : null;
  }, []);

  /**
   * Tell the server to stop the current turn. atMs is the client clock
   * reading (performance.now()) of the moment that triggered it. Late frames
   * for that turn are dropped from here on. The caller owns the buffer flush
   * so it can time its own reaction.
   */
  const interrupt = useCallback((atMs: number): string | null => {
    const turnId = stateTurnRef.current ?? sayTurnRef.current;
    if (!turnId) return null;
    ignoredTurnRef.current = turnId;
    const sent = sendRef.current?.({ t: "interrupt", turn_id: turnId, at_ms: atMs }) ?? false;
    return sent ? turnId : null;
  }, []);

  const sendRender = useCallback((behindMs: number, fps: number): boolean => {
    const turnId = stateTurnRef.current ?? sayTurnRef.current;
    if (!turnId) return false;
    return (
      sendRef.current?.({
        t: "render",
        turn_id: turnId,
        behind_ms: Math.round(behindMs),
        fps: Math.round(fps),
      }) ?? false
    );
  }, []);

  const diagnostics = useCallback((): SocketDiagnostics => ({ ...diagnosticsRef.current }), []);

  return {
    buffer,
    connection,
    ready,
    presence,
    caption,
    metrics,
    lastAck,
    rttMs,
    say,
    interrupt,
    sendRender,
    diagnostics,
  };
}
