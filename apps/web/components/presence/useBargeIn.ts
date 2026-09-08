"use client";

/**
 * Barge-in: the operator starts talking while DEVON is speaking, and DEVON
 * stops.
 *
 * The microphone opens only from an explicit gesture (start() behind a
 * button); nothing here auto starts. Every animation frame the analyser's
 * time domain samples are reduced to an RMS level and fed to the pure
 * VoiceActivityDetector. When the detector reports speech_start while the
 * presence state is "speaking", the same tick, synchronously:
 *   1. the caller's onBargeIn runs (it flushes the FrameBuffer and sets the
 *      local "listening" override),
 *   2. the interrupt goes out over the socket with the tick's clock reading,
 *   3. the reaction is measured and reported, so the HUD shows a number that
 *      was clocked here rather than the specification's target.
 *
 * Two spans are reported. `reactionMs` runs from the first analyser tick
 * that crossed the energy threshold (the start of the attack window) to the
 * local state change, so it includes the detector's attack. `processingMs`
 * runs from the confirming tick to the same point. Neither includes the
 * acoustic path from mouth to microphone, which nothing here can observe.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { PresenceState } from "@/lib/presence/protocol";
import { VoiceActivityDetector, type VadOptions } from "@/lib/presence/vad";

export type MicState = "idle" | "requesting" | "live" | "denied" | "unsupported" | "error";

export type BargeInReaction = {
  /** performance.now() of the confirming analyser tick; sent as at_ms. */
  atMs: number;
  /** From the first threshold crossing to the local state change. */
  reactionMs: number;
  /** From the confirming tick to the local state change. */
  processingMs: number;
  /** Frames the flush discarded. */
  flushed: number;
  /** "mic" for a detector trigger, "manual" for the HUD button. */
  source: "mic" | "manual";
};

export type BargeInOptions = {
  /** The effective presence state (local override applied). */
  presenceState: PresenceState;
  /** Flush the buffer, set the local override, and return the flushed count. */
  onBargeIn: () => number;
  /** Send the interrupt over the socket with the tick's clock reading. */
  interrupt: (atMs: number) => void;
  vad?: VadOptions;
};

function describe(value: unknown): string {
  if (value instanceof Error) return value.message;
  return String(value);
}

export function useBargeIn(options: BargeInOptions) {
  const { presenceState, onBargeIn, interrupt, vad: vadOptions } = options;

  const [mic, setMic] = useState<MicState>("idle");
  const [message, setMessage] = useState("");
  const [userSpeaking, setUserSpeaking] = useState(false);
  const [lastReaction, setLastReaction] = useState<BargeInReaction | null>(null);

  const stateRef = useRef(presenceState);
  const onBargeInRef = useRef(onBargeIn);
  const interruptRef = useRef(interrupt);
  useEffect(() => {
    stateRef.current = presenceState;
    onBargeInRef.current = onBargeIn;
    interruptRef.current = interrupt;
  }, [presenceState, onBargeIn, interrupt]);

  const streamRef = useRef<MediaStream | null>(null);
  const contextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const samplesRef = useRef<Float32Array<ArrayBuffer> | null>(null);
  const vadRef = useRef<VoiceActivityDetector | null>(null);
  const rafRef = useRef<number | null>(null);
  const levelRef = useRef(0);

  /** Shared by the detector path and the HUD button. */
  const trigger = useCallback((source: "mic" | "manual", crossedAtMs: number, tickAtMs: number) => {
    const flushed = onBargeInRef.current();
    const reactedAtMs = performance.now();
    interruptRef.current(tickAtMs);
    const reaction: BargeInReaction = {
      atMs: tickAtMs,
      reactionMs: reactedAtMs - crossedAtMs,
      processingMs: reactedAtMs - tickAtMs,
      flushed,
      source,
    };
    setLastReaction(reaction);
    return reaction;
  }, []);

  const stop = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    analyserRef.current = null;
    samplesRef.current = null;
    vadRef.current = null;
    levelRef.current = 0;
    const context = contextRef.current;
    contextRef.current = null;
    if (context) void context.close().catch(() => undefined);
    setUserSpeaking(false);
    setMic("idle");
  }, []);

  /** Open the microphone. Call from a click handler, never from an effect. */
  const start = useCallback(async () => {
    if (mic === "requesting" || mic === "live") return;
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setMic("unsupported");
      setMessage("This browser exposes no microphone API, so barge-in by voice is unavailable here.");
      return;
    }
    setMic("requesting");
    setMessage("");
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        video: false,
      });
    } catch (error) {
      const name = error instanceof DOMException ? error.name : "";
      if (name === "NotAllowedError" || name === "SecurityError") {
        setMic("denied");
        setMessage("Microphone permission was refused. Allow it in the browser's site settings and press Start mic again.");
      } else if (name === "NotFoundError") {
        setMic("error");
        setMessage("No microphone was found on this device.");
      } else {
        setMic("error");
        setMessage(`Microphone failed: ${describe(error)}`);
      }
      return;
    }

    try {
      const context = new AudioContext();
      const source = context.createMediaStreamSource(stream);
      const analyser = context.createAnalyser();
      analyser.fftSize = 1024;
      analyser.smoothingTimeConstant = 0;
      source.connect(analyser);
      streamRef.current = stream;
      contextRef.current = context;
      analyserRef.current = analyser;
      samplesRef.current = new Float32Array(analyser.fftSize);
      vadRef.current = new VoiceActivityDetector(vadOptions);
      await context.resume();
    } catch (error) {
      stream.getTracks().forEach((track) => track.stop());
      setMic("error");
      setMessage(`Audio analysis failed: ${describe(error)}`);
      return;
    }
    setMic("live");

    const tick = () => {
      const analyser = analyserRef.current;
      const samples = samplesRef.current;
      const vad = vadRef.current;
      if (!analyser || !samples || !vad) return;
      const nowMs = performance.now();
      analyser.getFloatTimeDomainData(samples);
      let sum = 0;
      for (let i = 0; i < samples.length; i += 1) sum += samples[i] * samples[i];
      const rms = Math.sqrt(sum / samples.length);
      levelRef.current = rms;

      // The detector clears energySince when it fires, so read it first.
      const crossedAtMs = vad.energySince ?? nowMs;
      const event = vad.feed(rms, nowMs);
      if (event === "speech_start") {
        setUserSpeaking(true);
        if (stateRef.current === "speaking") trigger("mic", crossedAtMs, nowMs);
      } else if (event === "speech_end") {
        setUserSpeaking(false);
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
  }, [mic, trigger, vadOptions]);

  /** The HUD's Interrupt button: same path, no microphone. */
  const manualBargeIn = useCallback(() => {
    const nowMs = performance.now();
    return trigger("manual", nowMs, nowMs);
  }, [trigger]);

  const getMicLevel = useCallback(() => levelRef.current, []);

  useEffect(() => () => stop(), [stop]);

  return { mic, message, userSpeaking, lastReaction, start, stop, manualBargeIn, getMicLevel };
}
