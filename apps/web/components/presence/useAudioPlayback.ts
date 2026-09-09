"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { AudioMessage } from "@/lib/presence/protocol";
import {
  PLAYBACK_LEAD_S,
  base64ToBytes,
  durationSeconds,
  pcmToFloat32,
  scheduleChunk,
} from "@/lib/presence/pcm-player";

/**
 * Playing the raw PCM the presence socket sends.
 *
 * Before this, `usePresenceSocket` counted every audio message and dropped it,
 * and the presence service mints LiveKit join tokens without ever publishing
 * audio into a room (`apps/presence/__init__.py:45`). So no path existed by
 * which anyone could hear DEVON, with LiveKit or without it. A vendor
 * synthesiser on the server end of a lane that discards its output is a lane
 * that has never been heard.
 *
 * WHAT THIS DOES NOT CLAIM
 *
 * "playing" here means chunks were scheduled on an AudioContext that reports
 * itself running. It is not a claim that a human heard anything: the device
 * can be muted, routed elsewhere, or at zero volume, and nothing in a browser
 * can tell. The status string is deliberately about what was scheduled.
 *
 * AUTOPLAY
 *
 * A browser starts an AudioContext suspended until a user gesture, and iOS is
 * strict about it. So the context is created lazily, `unlock` is meant to be
 * called from a click handler, and the status reports "blocked" rather than
 * silently scheduling into a suspended context and looking fine.
 */

export type PlaybackStatus = "idle" | "blocked" | "playing" | "unsupported";

export type PlaybackDiagnostics = {
  /** Chunks handed to the AudioContext. */
  scheduled: number;
  /** Chunks whose slot had already passed when they arrived. */
  late: number;
  /** Chunks whose payload did not decode. */
  malformed: number;
  /** Seconds of audio scheduled, which is what was sent rather than heard. */
  seconds: number;
};

type Turn = {
  id: string;
  /** The AudioContext time this turn's `at_ms` zero sits on. */
  start: number;
  sources: AudioBufferSourceNode[];
  /** When the last chunk scheduled stops sounding. A late chunk queues here. */
  busyUntil: number;
};

function audioContextClass(): typeof AudioContext | null {
  if (typeof window === "undefined") return null;
  const holder = window as unknown as { webkitAudioContext?: typeof AudioContext };
  return window.AudioContext ?? holder.webkitAudioContext ?? null;
}

export function useAudioPlayback() {
  const contextRef = useRef<AudioContext | null>(null);
  const turnRef = useRef<Turn | null>(null);
  const diagnosticsRef = useRef<PlaybackDiagnostics>({
    scheduled: 0,
    late: 0,
    malformed: 0,
    seconds: 0,
  });
  const [status, setStatus] = useState<PlaybackStatus>("idle");

  const context = useCallback((): AudioContext | null => {
    if (contextRef.current) return contextRef.current;
    const Ctor = audioContextClass();
    if (!Ctor) {
      setStatus("unsupported");
      return null;
    }
    try {
      contextRef.current = new Ctor();
    } catch {
      setStatus("unsupported");
      return null;
    }
    return contextRef.current;
  }, []);

  /** Call this from a click. A browser will not start audio without one. */
  const unlock = useCallback(async (): Promise<void> => {
    const ctx = context();
    if (!ctx) return;
    try {
      await ctx.resume();
      setStatus(ctx.state === "running" ? "playing" : "blocked");
    } catch {
      setStatus("blocked");
    }
  }, [context]);

  /** Stop everything still scheduled. Barge-in and turn changes both need it. */
  const stop = useCallback((): void => {
    const turn = turnRef.current;
    turnRef.current = null;
    if (!turn) return;
    for (const source of turn.sources) {
      try {
        source.stop();
      } catch {
        // Already ended. Stopping twice is not an error worth surfacing.
      }
      source.disconnect();
    }
  }, []);

  const play = useCallback(
    (message: AudioMessage): void => {
      const ctx = context();
      if (!ctx) return;
      if (ctx.state === "suspended") {
        // Scheduling into a suspended context would look like success and make
        // no sound, which is the failure this whole module exists to end.
        setStatus("blocked");
        return;
      }

      const bytes = base64ToBytes(message.b64);
      if (bytes.length < 2) {
        diagnosticsRef.current.malformed += 1;
        return;
      }

      let turn = turnRef.current;
      if (!turn || turn.id !== message.turn_id) {
        stop();
        turn = {
          id: message.turn_id,
          start: ctx.currentTime + PLAYBACK_LEAD_S,
          sources: [],
          busyUntil: 0,
        };
        turnRef.current = turn;
      }

      // Every Web Audio call lives in lib/presence/pcm-player.ts so the browser
      // check can execute the same code path rather than a copy of it beside
      // itself. See the AudioSink docstring for the bug that taught us.
      const placed = scheduleChunk(
        ctx,
        pcmToFloat32(bytes),
        message.at_ms,
        turn.start,
        turn.busyUntil,
      );
      turn.busyUntil = Math.max(turn.busyUntil, placed.endsAt);
      turn.sources.push(placed.source);
      placed.source.onended = () => {
        placed.source.disconnect();
        const current = turnRef.current;
        if (!current) return;
        const at = current.sources.indexOf(placed.source);
        if (at >= 0) current.sources.splice(at, 1);
      };

      diagnosticsRef.current.scheduled += 1;
      if (placed.late) diagnosticsRef.current.late += 1;
      diagnosticsRef.current.seconds += durationSeconds(bytes);
      setStatus("playing");
    },
    [context, stop],
  );

  const diagnostics = useCallback((): PlaybackDiagnostics => ({ ...diagnosticsRef.current }), []);

  useEffect(() => {
    return () => {
      stop();
      const ctx = contextRef.current;
      contextRef.current = null;
      if (ctx) void ctx.close().catch(() => undefined);
    };
  }, [stop]);

  return { status, play, stop, unlock, diagnostics };
}
