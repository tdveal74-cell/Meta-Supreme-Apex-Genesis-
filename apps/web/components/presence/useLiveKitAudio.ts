"use client";

/**
 * Remote audio over LiveKit, wrapped for the presence stage.
 *
 * Given the server's LiveKit URL and a token minting function, the hook joins
 * the room, attaches every remote audio track to a hidden <audio> element,
 * and taps the same track through an AnalyserNode so the stage can read the
 * remote RMS (energy driven jawOpen fallback) and an audio clock (ms since
 * the first non silent remote sample was heard, which stands in for the
 * server's audio timeline).
 *
 * When the server reports LiveKit as not configured the hook stays idle and
 * reports "not configured"; the stage then runs the frame timeline on the
 * wall clock from the moment the speaking state arrived.
 *
 * UNVERIFIED: this LiveKit path has not been exercised against a live
 * LiveKit server in this build. It type checks against livekit-client
 * 2.22.3 and follows its Room / RoomEvent.TrackSubscribed / attach API, and
 * that is the extent of the evidence.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Room, RoomEvent, Track, type RemoteTrack } from "livekit-client";

export type LiveKitStatus =
  | "not configured"
  | "idle"
  | "minting token"
  | "connecting"
  | "connected"
  | "playback blocked"
  | "disconnected"
  | "error";

export type LiveKitAudioOptions = {
  configured: boolean;
  url: string | null;
  roomName: string | null;
  /** POST the token endpoint and return the LiveKit access token. */
  mintToken: (room: string) => Promise<string>;
  /** Join only when true (the stage flips it once the presence socket is ready). */
  enabled: boolean;
};

/** RMS above this counts as "heard" for the audio clock origin. */
const HEARD_RMS = 0.004;

function describe(value: unknown): string {
  if (value instanceof Error) return value.message;
  return String(value);
}

export function useLiveKitAudio(options: LiveKitAudioOptions) {
  const { configured, url, roomName, mintToken, enabled } = options;
  const [status, setStatus] = useState<LiveKitStatus>(configured ? "idle" : "not configured");
  const [detail, setDetail] = useState("");
  const [tracks, setTracks] = useState(0);

  const roomRef = useRef<Room | null>(null);
  const contextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const samplesRef = useRef<Float32Array<ArrayBuffer> | null>(null);
  const firstHeardRef = useRef<number | null>(null);

  /**
   * RMS of the remote audio right now, 0..1. Also advances the audio clock
   * origin the first time sound is heard, so call it every animation frame
   * while a turn is playing.
   */
  const getAudioLevel = useCallback((): number => {
    const analyser = analyserRef.current;
    const samples = samplesRef.current;
    if (!analyser || !samples) return 0;
    analyser.getFloatTimeDomainData(samples);
    let sum = 0;
    for (let i = 0; i < samples.length; i += 1) sum += samples[i] * samples[i];
    const rms = Math.sqrt(sum / samples.length);
    if (rms >= HEARD_RMS && firstHeardRef.current === null) {
      firstHeardRef.current = performance.now();
    }
    return rms;
  }, []);

  /** ms since the first remote audio was heard, or null before that. */
  const audioClockMs = useCallback((): number | null => {
    const origin = firstHeardRef.current;
    return origin === null ? null : performance.now() - origin;
  }, []);

  /** Start a new turn's clock: the next heard sample becomes 0 ms. */
  const resetClock = useCallback(() => {
    firstHeardRef.current = null;
  }, []);

  /** Autoplay policies may hold playback until a gesture; call this from one. */
  const unlockPlayback = useCallback(async () => {
    try {
      await roomRef.current?.startAudio();
      await contextRef.current?.resume();
      setStatus((current) => (current === "playback blocked" ? "connected" : current));
    } catch (error) {
      setDetail(describe(error));
    }
  }, []);

  useEffect(() => {
    if (!configured) {
      setStatus("not configured");
      return;
    }
    if (!enabled || !url || !roomName) {
      setStatus("idle");
      return;
    }

    let cancelled = false;
    const room = new Room();
    roomRef.current = room;

    const audio = document.createElement("audio");
    audio.autoplay = true;
    audio.hidden = true;
    audio.setAttribute("data-presence-remote-audio", "");
    document.body.appendChild(audio);

    const onTrackSubscribed = (track: RemoteTrack) => {
      if (track.kind !== Track.Kind.Audio) return;
      track.attach(audio);
      try {
        const context = contextRef.current ?? new AudioContext();
        contextRef.current = context;
        const source = context.createMediaStreamSource(new MediaStream([track.mediaStreamTrack]));
        const analyser = context.createAnalyser();
        analyser.fftSize = 1024;
        analyser.smoothingTimeConstant = 0;
        // The analyser only listens; the <audio> element is what plays.
        source.connect(analyser);
        analyserRef.current = analyser;
        samplesRef.current = new Float32Array(analyser.fftSize);
      } catch (error) {
        setDetail(`Analyser unavailable: ${describe(error)}`);
      }
      setTracks((count) => count + 1);
      setStatus(room.canPlaybackAudio ? "connected" : "playback blocked");
    };
    const onTrackUnsubscribed = (track: RemoteTrack) => {
      if (track.kind !== Track.Kind.Audio) return;
      track.detach(audio);
      setTracks((count) => Math.max(0, count - 1));
    };
    const onDisconnected = () => {
      if (!cancelled) setStatus("disconnected");
    };

    room.on(RoomEvent.TrackSubscribed, onTrackSubscribed);
    room.on(RoomEvent.TrackUnsubscribed, onTrackUnsubscribed);
    room.on(RoomEvent.Disconnected, onDisconnected);

    (async () => {
      setDetail("");
      setStatus("minting token");
      const token = await mintToken(roomName);
      if (cancelled) return;
      setStatus("connecting");
      await room.connect(url, token, { autoSubscribe: true });
      if (cancelled) return;
      setStatus(room.canPlaybackAudio ? "connected" : "playback blocked");
    })().catch((error) => {
      if (cancelled) return;
      setStatus("error");
      setDetail(describe(error));
    });

    return () => {
      cancelled = true;
      room.off(RoomEvent.TrackSubscribed, onTrackSubscribed);
      room.off(RoomEvent.TrackUnsubscribed, onTrackUnsubscribed);
      room.off(RoomEvent.Disconnected, onDisconnected);
      void room.disconnect();
      roomRef.current = null;
      analyserRef.current = null;
      samplesRef.current = null;
      firstHeardRef.current = null;
      const context = contextRef.current;
      contextRef.current = null;
      if (context) void context.close().catch(() => undefined);
      audio.remove();
      setTracks(0);
    };
  }, [configured, enabled, url, roomName, mintToken]);

  return { status, detail, tracks, getAudioLevel, audioClockMs, resetClock, unlockPlayback };
}
