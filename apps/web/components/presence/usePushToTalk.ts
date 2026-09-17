"use client";

/**
 * Push to talk: hold the control, speak, release, and the clip goes up as
 * `listen_start` / `listen_chunk` / `listen_end`.
 *
 * This is the half of protocol v2 that was missing. PR #257 built the ear on
 * the server, apps/presence/hearing.py has been able to assemble a clip and
 * transcribe it since, and nothing in the browser had ever sent one, so the
 * whole path was untested against a real client. `PRESENCE_EARS` still
 * defaults to mock on the deployed service, so a clip sent today comes back
 * as MockHearing's scripted line rather than as real transcription. That is
 * the correct default and it is what makes this testable without spending a
 * vendor call.
 *
 * It taps the microphone useBargeIn already opened rather than opening a
 * second one, so there is one permission prompt and one recording indicator.
 * Press start mic first; this hook refuses rather than prompting, because a
 * getUserMedia call outside a user gesture is denied by some browsers and
 * silently queued by others.
 *
 * WHAT IT REFUSES, AND WHY EACH REFUSAL IS ITS OWN MESSAGE. A refusal the
 * speaker cannot act on is the same as a crash to them. So an unsupported
 * rate names the rate, a clip over the ceiling says to say it shorter, a v1
 * server says the server is older than this page, and none of them are
 * folded into one "capture failed".
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ClipBudget,
  bytesToBase64,
  blocksPerChunk,
  floatToPcm16,
  isListenRate,
  rateRefusal,
} from "@/lib/presence/capture";
import { canListen, type ClientMessage, type ListenRate } from "@/lib/presence/protocol";
import type { MicTap } from "./useBargeIn";

/** Samples per process() call. Fixed by the Web Audio specification. */
export const WORKLET_BLOCK_SIZE = 128;

export const WORKLET_URL = "/presence/capture-worklet.js";
export const WORKLET_NAME = "presence-capture";

export type CaptureState =
  | "idle"
  | "unavailable"
  | "arming"
  | "ready"
  | "recording"
  | "sending"
  | "error";

export type PushToTalkOptions = {
  /** The live microphone graph, or null. From useBargeIn's getTap. */
  getTap: () => MicTap | null;
  /** Send one client message over the presence socket. */
  send: (message: ClientMessage) => void;
  /** The protocol the server agreed to in `ready`, or null before it lands. */
  negotiatedProtocol: number | null;
  /** Mint the turn id this clip belongs to. */
  newTurnId: () => string;
};

function describe(value: unknown): string {
  if (value instanceof Error) return value.message;
  return String(value);
}

export function usePushToTalk(options: PushToTalkOptions) {
  const { getTap, send, negotiatedProtocol, newTurnId } = options;

  const [state, setState] = useState<CaptureState>("idle");
  const [message, setMessage] = useState("");
  const [heldSeconds, setHeldSeconds] = useState(0);

  const nodeRef = useRef<AudioWorkletNode | null>(null);
  const contextRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const budgetRef = useRef<ClipBudget>(new ClipBudget());
  const turnRef = useRef<string | null>(null);
  const seqRef = useRef(0);
  const rateRef = useRef<ListenRate | null>(null);
  const sendRef = useRef(send);
  const overRef = useRef(false);

  useEffect(() => {
    sendRef.current = send;
  }, [send]);

  /** Tear the worklet down without touching the shared microphone. */
  const teardown = useCallback(() => {
    const node = nodeRef.current;
    if (node) {
      node.port.onmessage = null;
      try {
        node.port.postMessage({ t: "stop" });
      } catch {
        /* the port is already gone, which is the state we want */
      }
      node.disconnect();
    }
    nodeRef.current = null;
    sourceRef.current = null;
    contextRef.current = null;
  }, []);

  /**
   * Load the worklet and wire it to the open microphone.
   *
   * Separate from the press so the first press does not pay for a module
   * fetch: addModule goes to the network, and a quarter second of silence at
   * the front of the first clip is a quarter second of the sentence.
   */
  const arm = useCallback(async (): Promise<boolean> => {
    if (nodeRef.current) return true;
    if (negotiatedProtocol !== null && !canListen(negotiatedProtocol)) {
      setState("unavailable");
      setMessage(
        `This presence server speaks protocol ${negotiatedProtocol} and the ear ` +
          "arrived in 2, so it cannot hear a clip. Typing still works.",
      );
      return false;
    }
    const tap = getTap();
    if (!tap) {
      setState("unavailable");
      setMessage("Press Start mic first. Capture shares that microphone rather than opening a second one.");
      return false;
    }
    const rate = tap.context.sampleRate;
    const refusal = rateRefusal(rate);
    if (refusal || !isListenRate(rate)) {
      setState("unavailable");
      setMessage(refusal || `Unsupported sample rate ${rate}.`);
      return false;
    }

    setState("arming");
    setMessage("");
    try {
      await tap.context.audioWorklet.addModule(WORKLET_URL);
      const node = new AudioWorkletNode(tap.context, WORKLET_NAME, {
        numberOfInputs: 1,
        numberOfOutputs: 0,
        channelCount: 1,
        processorOptions: {
          blocksPerChunk: blocksPerChunk(rate, WORKLET_BLOCK_SIZE),
        },
      });
      node.port.onmessage = (event: MessageEvent) => {
        const data = event.data as { t?: string; samples?: Float32Array };
        if (data?.t !== "chunk" || !data.samples) return;
        const turnId = turnRef.current;
        if (turnId === null || overRef.current) return;

        const bytes = floatToPcm16(data.samples);
        const budget = budgetRef.current;
        const refused = budget.refuse(bytes.length);
        if (refused) {
          // Stop at the ceiling rather than sending a clip the server drops
          // whole. The turn is abandoned: half a sentence transcribes into a
          // whole one that nobody said.
          overRef.current = true;
          setState("error");
          setMessage(refused.message);
          return;
        }
        budget.keep(bytes.length);
        setHeldSeconds(budget.seconds(rate));
        sendRef.current({
          t: "listen_chunk",
          turn_id: turnId,
          seq: seqRef.current,
          b64: bytesToBase64(bytes),
        });
        seqRef.current += 1;
      };
      tap.source.connect(node);
      nodeRef.current = node;
      contextRef.current = tap.context;
      sourceRef.current = tap.source;
      rateRef.current = rate;
      setState("ready");
      return true;
    } catch (error) {
      setState("error");
      setMessage(`The capture worklet did not load: ${describe(error)}`);
      return false;
    }
  }, [getTap, negotiatedProtocol]);

  /** Press: open the clip and start keeping samples. */
  const press = useCallback(async () => {
    if (state === "recording" || state === "sending") return;
    const armed = await arm();
    if (!armed) return;
    const node = nodeRef.current;
    const rate = rateRef.current;
    if (!node || rate === null) return;

    const turnId = newTurnId();
    turnRef.current = turnId;
    seqRef.current = 0;
    overRef.current = false;
    budgetRef.current.reset();
    setHeldSeconds(0);
    setMessage("");
    setState("recording");
    sendRef.current({ t: "listen_start", turn_id: turnId, codec: "pcm_s16le", rate });
    node.port.postMessage({ t: "start" });
  }, [arm, newTurnId, state]);

  /** Release: flush the tail, close the clip, and let the server transcribe. */
  const release = useCallback(() => {
    const node = nodeRef.current;
    const turnId = turnRef.current;
    if (!node || turnId === null) return;

    // Tell the worklet first. Its stop handler flushes what it is holding,
    // and that post lands before this one because both go through the same
    // port in order, so the tail of the sentence arrives before listen_end.
    node.port.postMessage({ t: "stop" });

    if (overRef.current) {
      // The ceiling already refused this clip. listen_end would make the
      // server transcribe the part that arrived, which is the one outcome
      // worth avoiding, so the turn is dropped instead.
      turnRef.current = null;
      return;
    }

    if (budgetRef.current.chunks === 0) {
      turnRef.current = null;
      setState("ready");
      setMessage("Nothing was recorded. Hold the control while you speak.");
      return;
    }

    sendRef.current({ t: "listen_end", turn_id: turnId });
    turnRef.current = null;
    setState("sending");
  }, []);

  /** The server answered, so the clip is done with. */
  const settle = useCallback(() => {
    setState((current) => (current === "sending" ? "ready" : current));
  }, []);

  useEffect(() => () => teardown(), [teardown]);

  return { state, message, heldSeconds, press, release, settle, arm };
}
