"use client";

/**
 * Presence: DEVON's face on a stage, with the HUD beside it.
 *
 * Left, the avatar canvas. Right, the command center's instrument panel:
 * connection and presence state, the provider and breaker from the server's
 * metrics, TTFT, frame counts on both ends, the measured barge-in reaction,
 * LiveKit status, a text input that speaks, the microphone gesture, and the
 * model URL.
 *
 * Sign-in is the one the Command Center and Talk to DEVON already did: the
 * token is read from the same storage slot. There is no fourth credential.
 */

import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { PRESENCE_BASE, PRESENCE_WS_BASE } from "@/lib/api-base";
import type { PresenceState } from "@/lib/presence/protocol";
import {
  DevonAvatarCanvas,
  type AvatarDriver,
  type RenderTelemetry,
  type RigInfo,
} from "./DevonAvatarCanvas";
import { useAudioPlayback, type PlaybackDiagnostics } from "./useAudioPlayback";
import { useBargeIn } from "./useBargeIn";
import { useLiveKitAudio } from "./useLiveKitAudio";
import { readDevonToken, TOKEN_SLOT, usePresenceSocket } from "./usePresenceSocket";

const DEFAULT_MODEL_URL = process.env.NEXT_PUBLIC_DEVON_AVATAR_URL?.trim() ?? "";
const RENDER_TELEMETRY_MS = 500;
const HUD_REFRESH_MS = 250;
const SMOOTHING = 0.35;

type HudSample = {
  pushed: number;
  sampled: number;
  dropped: number;
  malformed: number;
  strayFrames: number;
  audioChunksIgnored: number;
  micLevel: number;
  telemetry: RenderTelemetry | null;
};

const EMPTY_PLAYBACK: PlaybackDiagnostics = {
  scheduled: 0,
  late: 0,
  malformed: 0,
  seconds: 0,
};

const EMPTY_HUD: HudSample = {
  pushed: 0,
  sampled: 0,
  dropped: 0,
  malformed: 0,
  strayFrames: 0,
  audioChunksIgnored: 0,
  micLevel: 0,
  telemetry: null,
};

function ms(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "n/a";
  return `${value.toFixed(digits)} ms`;
}

function signalClass(tone: "good" | "wait" | "hold" | "bad" | "off"): string {
  if (tone === "good") return "bg-emerald-300 shadow-[0_0_12px_rgba(110,231,183,.85)]";
  if (tone === "wait") return "animate-pulse bg-amber-200";
  if (tone === "hold") return "bg-sky-300 shadow-[0_0_10px_rgba(125,211,252,.65)]";
  if (tone === "bad") return "bg-red-400 shadow-[0_0_10px_rgba(248,113,113,.65)]";
  return "bg-[#526979]";
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "good" | "wait" | "hold" | "bad" | "off" }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-[#2b4558]/50 py-1.5">
      <span className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.2em] text-[#668092]">
        {tone ? <span className={`h-1.5 w-1.5 rounded-full ${signalClass(tone)}`} /> : null}
        {label}
      </span>
      <span className="truncate font-mono text-[11px] text-[#f5f0e7]">{value}</span>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border border-[#2b4558]/90 bg-[linear-gradient(135deg,rgba(8,19,27,.94),rgba(5,10,14,.82)_48%,rgba(10,23,30,.9))] p-3">
      <h2 className="mb-1 font-mono text-[11px] uppercase tracking-[0.24em] text-[#4fb3a5]">{title}</h2>
      {children}
    </section>
  );
}

export function PresenceStage() {
  const [token, setToken] = useState("");
  useEffect(() => {
    setToken(readDevonToken());
    const onStorage = (event: StorageEvent) => {
      if (event.key === null || event.key === TOKEN_SLOT) setToken(readDevonToken());
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  // Raw PCM playback. The presence service has never published audio into a
  // LiveKit room, so this is the only path by which anything is heard, and
  // before it existed every chunk was counted and dropped.
  const playback = useAudioPlayback();
  const socket = usePresenceSocket(token, { onAudio: playback.play });
  const { buffer, connection, ready, presence, caption, metrics, lastAck, rttMs, say, interrupt, sendRender, diagnostics } = socket;

  // Local "listening" override set by barge-in; the next server state clears it.
  const [override, setOverride] = useState<{ atMs: number } | null>(null);
  useEffect(() => {
    if (override && presence.arrivedAtMs > override.atMs) setOverride(null);
  }, [presence.arrivedAtMs, override]);
  const effectiveState: PresenceState = override ? "listening" : presence.state;

  // LiveKit: mint a token with the DEVON session, join the server's room.
  const mintToken = useCallback(
    async (room: string): Promise<string> => {
      const response = await fetch(`${PRESENCE_BASE}/livekit/token`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ room }),
      });
      if (!response.ok) throw new Error(`livekit/token answered ${response.status}`);
      const body: unknown = await response.json();
      if (body && typeof body === "object") {
        const record = body as Record<string, unknown>;
        if (typeof record.token === "string") return record.token;
        if (typeof record.access_token === "string") return record.access_token;
      }
      throw new Error("livekit/token answered without a token field");
    },
    [token],
  );
  const livekit = useLiveKitAudio({
    configured: ready?.livekit.configured ?? false,
    url: ready?.livekit.url ?? null,
    roomName: ready?.session_id ?? null,
    mintToken,
    enabled: connection.kind === "ready",
  });

  // The frame timeline. LiveKit's clock when it has heard audio; otherwise
  // the wall clock from the moment the speaking state arrived.
  const speakingOriginRef = useRef<number | null>(null);
  const { resetClock } = livekit;
  useEffect(() => {
    if (presence.state === "speaking") {
      speakingOriginRef.current = presence.arrivedAtMs;
      resetClock();
    } else {
      speakingOriginRef.current = null;
    }
  }, [presence.state, presence.turnId, presence.arrivedAtMs, resetClock]);

  const { audioClockMs: livekitClockMs, getAudioLevel } = livekit;
  const audioClockMs = useCallback((): number | null => {
    if (override) return null;
    const heard = livekitClockMs();
    if (heard !== null) return heard;
    const origin = speakingOriginRef.current;
    return origin === null ? null : performance.now() - origin;
  }, [livekitClockMs, override]);

  // Barge-in.
  const onBargeIn = useCallback(() => {
    const flushed = buffer.flush();
    setOverride({ atMs: performance.now() });
    return flushed;
  }, [buffer]);
  const sendInterrupt = useCallback(
    (atMs: number) => {
      interrupt(atMs);
    },
    [interrupt],
  );
  const bargeIn = useBargeIn({ presenceState: effectiveState, onBargeIn, interrupt: sendInterrupt });

  // Render telemetry to the server every ~500 ms while speaking.
  const telemetryRef = useRef<RenderTelemetry | null>(null);
  const onTelemetry = useCallback((telemetry: RenderTelemetry) => {
    telemetryRef.current = telemetry;
  }, []);
  useEffect(() => {
    if (effectiveState !== "speaking") return;
    const id = window.setInterval(() => {
      const telemetry = telemetryRef.current;
      if (telemetry) sendRender(telemetry.behindMs, telemetry.fps);
    }, RENDER_TELEMETRY_MS);
    return () => window.clearInterval(id);
  }, [effectiveState, sendRender]);

  // HUD refresh from the refs that change every animation frame.
  const [hud, setHud] = useState<HudSample>(EMPTY_HUD);
  const [playbackHud, setPlaybackHud] = useState<PlaybackDiagnostics>(EMPTY_PLAYBACK);
  const { getMicLevel } = bargeIn;
  const playbackDiagnostics = playback.diagnostics;
  useEffect(() => {
    const id = window.setInterval(() => {
      const counters = buffer.counters();
      const diag = diagnostics();
      setHud({
        ...counters,
        ...diag,
        micLevel: getMicLevel(),
        telemetry: telemetryRef.current,
      });
      setPlaybackHud(playbackDiagnostics());
    }, HUD_REFRESH_MS);
    return () => window.clearInterval(id);
  }, [buffer, diagnostics, getMicLevel, playbackDiagnostics]);

  const driver = useMemo<AvatarDriver>(
    () => ({
      buffer,
      audioClockMs,
      audioLevel: getAudioLevel,
      state: effectiveState,
      smoothing: SMOOTHING,
      onTelemetry,
    }),
    [buffer, audioClockMs, getAudioLevel, effectiveState, onTelemetry],
  );

  // Model URL: applied on submit so typing does not fire a load per key.
  const [modelDraft, setModelDraft] = useState(DEFAULT_MODEL_URL);
  const [modelUrl, setModelUrl] = useState(DEFAULT_MODEL_URL);
  const [modelError, setModelError] = useState("");
  const [rigInfo, setRigInfo] = useState<RigInfo | null>(null);
  const onModelError = useCallback((message: string) => setModelError(message), []);
  const onRigInfo = useCallback((info: RigInfo) => setRigInfo(info), []);
  const applyModel = (event: FormEvent) => {
    event.preventDefault();
    setModelError("");
    setModelUrl(modelDraft.trim());
  };

  // Say.
  const [draft, setDraft] = useState("");
  const [lastTurn, setLastTurn] = useState<string | null>(null);
  const onSay = (event: FormEvent) => {
    event.preventDefault();
    const turnId = say(draft);
    if (turnId) {
      setLastTurn(turnId);
      setDraft("");
    }
  };

  const signedIn = token.length > 0;
  const live = connection.kind === "ready";
  const connectionLabel =
    connection.kind === "locked"
      ? "locked"
      : connection.kind === "connecting"
        ? `connecting (attempt ${connection.attempt + 1})`
        : connection.kind === "ready"
          ? "ready"
          : connection.kind === "closed"
            ? connection.retryInMs === null
              ? "closed"
              : `closed, retry in ${(connection.retryInMs / 1000).toFixed(0)} s`
            : connection.retryInMs === null
              ? `error: ${connection.message}`
              : `error: ${connection.message} (retry in ${(connection.retryInMs / 1000).toFixed(0)} s)`;
  const connectionTone =
    connection.kind === "ready" ? "good" : connection.kind === "connecting" ? "wait" : connection.kind === "locked" ? "hold" : "bad";
  const stateTone =
    effectiveState === "speaking" ? "good" : effectiveState === "thinking" ? "wait" : effectiveState === "listening" ? "hold" : "off";
  const micLabel =
    bargeIn.mic === "live"
      ? `live, rms ${hud.micLevel.toFixed(3)}${bargeIn.userSpeaking ? ", voice" : ""}`
      : bargeIn.mic;
  const reaction = bargeIn.lastReaction;

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1.55fr)_minmax(320px,1fr)]">
      <div className="flex flex-col gap-3">
        <div className="relative aspect-[16/10] w-full overflow-hidden border border-[#2b4558]/90 bg-[#050a0e] shadow-[0_24px_90px_rgba(0,0,0,.45)]">
          <DevonAvatarCanvas driver={driver} modelUrl={modelUrl} onModelError={onModelError} onRigInfo={onRigInfo} />
          <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[#4fb3a5]/70 to-transparent" />
          <div className="pointer-events-none absolute left-3 top-3 flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.2em] text-[#668092]">
            <span className={`h-1.5 w-1.5 rounded-full ${signalClass(stateTone)}`} />
            {effectiveState}
            {override ? " (local)" : ""}
          </div>
          {modelError ? (
            <div className="absolute inset-x-3 bottom-3 border border-red-400/40 bg-[#0b1116]/90 px-3 py-2 font-mono text-[11px] text-red-200">
              Model failed to load: {modelError}. Showing the procedural head.
            </div>
          ) : null}
          {!signedIn ? (
            <div className="absolute inset-x-3 bottom-3 border border-amber-300/30 bg-[#0b1116]/90 px-3 py-2 text-[11px] leading-5 text-white/70">
              Sign in on the Command Center or Talk to DEVON first. Presence reuses that session and adds no credential of its own.
            </div>
          ) : null}
        </div>

        <div className="min-h-[3.5rem] border border-[#2b4558]/60 bg-black/30 px-3 py-2">
          <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-[#668092]">Caption</div>
          <p className="mt-1 text-sm leading-6 text-[#ede7dc]/90">{caption || (lastTurn ? "Waiting for the first token." : "Nothing said yet.")}</p>
        </div>

        <form onSubmit={onSay} className="flex gap-2">
          <label className="sr-only" htmlFor="presence-say">
            Say something through DEVON
          </label>
          <input
            id="presence-say"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={live ? "Say something through DEVON" : "Connect first"}
            disabled={!live}
            className="min-w-0 flex-1 border border-[#2b4558]/90 bg-black/30 px-3 py-2 text-sm text-white outline-none transition placeholder:text-white/50 focus:border-[#4fb3a5]/60 disabled:opacity-40"
          />
          <button
            type="submit"
            disabled={!live || !draft.trim()}
            className="bg-amber-300 px-4 py-2 text-sm font-bold text-[#151006] transition hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-30"
          >
            Send
          </button>
          <button
            type="button"
            onClick={() => bargeIn.manualBargeIn()}
            disabled={effectiveState !== "speaking"}
            className="border border-red-400/30 bg-red-400/10 px-3 py-2 text-sm font-semibold text-red-200 transition hover:bg-red-400/20 disabled:cursor-not-allowed disabled:opacity-30"
          >
            Interrupt
          </button>
        </form>
      </div>

      <div className="flex flex-col gap-3">
        <Panel title="Link">
          <Stat label="Socket" value={connectionLabel} tone={connectionTone} />
          <Stat label="Endpoint" value={`${PRESENCE_WS_BASE}/ws/presence`} />
          <Stat label="Session" value={ready?.session_id ?? "n/a"} />
          <Stat label="Speech" value={ready ? ready.speech : "n/a"} />
          <Stat label="Inference" value={ready ? `${ready.inference} (fallback ${ready.fallback})` : "n/a"} />
          <Stat label="Round trip" value={ms(rttMs, 1)} />
          <Stat label="Malformed" value={String(hud.malformed)} />
        </Panel>

        <Panel title="Presence">
          <Stat label="State" value={`${effectiveState}${override ? " (local override)" : ""}`} tone={stateTone} />
          <Stat label="Server state" value={`${presence.state} @ ${ms(presence.atMs)}`} />
          <Stat label="Turn" value={presence.turnId ?? lastTurn ?? "none"} />
          <Stat label="Provider" value={metrics ? `${metrics.provider}${metrics.fell_back ? " (fell back)" : ""}` : "n/a"} />
          <Stat label="Breaker" value={metrics?.breaker ?? "n/a"} tone={metrics ? (metrics.breaker === "closed" ? "good" : metrics.breaker === "half_open" ? "wait" : "bad") : undefined} />
          <Stat label="TTFT" value={ms(metrics?.ttft_ms)} />
          <Stat label="Tokens" value={metrics ? String(metrics.tokens) : "n/a"} />
        </Panel>

        <Panel title="Frames">
          <Stat label="Server sent / dropped" value={metrics ? `${metrics.frames_sent} / ${metrics.frames_dropped}` : "n/a"} />
          <Stat label="Client received" value={String(hud.pushed)} />
          <Stat label="Client shown / skipped" value={`${hud.sampled} / ${hud.dropped}`} />
          <Stat label="Stray (old turn)" value={String(hud.strayFrames)} />
          <Stat label="Render fps" value={hud.telemetry ? hud.telemetry.fps.toFixed(0) : "n/a"} />
          <Stat label="Behind" value={ms(hud.telemetry?.behindMs)} />
          <Stat label="Face age" value={hud.telemetry ? (hud.telemetry.frameShown ? ms(hud.telemetry.faceAgeMs) : "no fresh frame") : "n/a"} />
          <Stat label="Rig" value={rigInfo ? (rigInfo.source === "gltf" ? `GLB, ${rigInfo.meshes} morph meshes, ${rigInfo.matched}/52 names` : "procedural head") : "n/a"} />
        </Panel>

        <Panel title="Barge-in">
          <Stat label="Microphone" value={micLabel} tone={bargeIn.mic === "live" ? "good" : bargeIn.mic === "requesting" ? "wait" : bargeIn.mic === "idle" ? "off" : "bad"} />
          <Stat label="Reaction (measured)" value={reaction ? `${reaction.reactionMs.toFixed(1)} ms, ${reaction.source}` : "not yet triggered"} />
          <Stat label="Processing (measured)" value={reaction ? ms(reaction.processingMs, 2) : "n/a"} />
          <Stat label="Flushed locally" value={reaction ? String(reaction.flushed) : "n/a"} />
          <Stat label="Server ack" value={lastAck ? `${lastAck.flushed_frames} flushed, ${ms(lastAck.server_latency_ms, 1)}` : "n/a"} />
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {bargeIn.mic === "live" ? (
              <button type="button" onClick={bargeIn.stop} className="border border-white/15 px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.16em] text-white/70 transition hover:border-white/30 hover:text-white">
                Stop mic
              </button>
            ) : (
              <button
                type="button"
                onClick={() => void bargeIn.start()}
                disabled={bargeIn.mic === "requesting"}
                className="border border-[#4fb3a5]/50 bg-[#4fb3a5]/10 px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.16em] text-[#9fe3d6] transition hover:bg-[#4fb3a5]/20 disabled:opacity-40"
              >
                Start mic
              </button>
            )}
            <span className="text-[11px] leading-4 text-[#718898]">Opens only on this click. Attack 40 ms, hangover 300 ms, threshold 0.02 RMS.</span>
          </div>
          {bargeIn.message ? <p className="mt-2 text-[11px] leading-5 text-red-200/90">{bargeIn.message}</p> : null}
        </Panel>

        <Panel title="Voice">
          <Stat
            label="Playback"
            value={playback.status}
            tone={playback.status === "playing" ? "good" : playback.status === "blocked" ? "wait" : playback.status === "unsupported" ? "bad" : "off"}
          />
          <Stat label="Chunks scheduled" value={String(playbackHud.scheduled)} />
          <Stat label="Chunks arriving late" value={String(playbackHud.late)} />
          <Stat label="Chunks that would not decode" value={String(playbackHud.malformed)} />
          <Stat label="Audio scheduled" value={`${playbackHud.seconds.toFixed(1)}s`} />
          <button
            type="button"
            onClick={() => void playback.unlock()}
            className="mt-2 border border-cyan-400/40 bg-cyan-400/10 px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.16em] text-cyan-200 transition hover:border-cyan-300/60"
          >
            Start audio
          </button>
          <p className="mt-2 text-[11px] leading-4 text-[#718898]">
            A browser will not start audio without a tap, so press this once a session. Scheduled is
            what left for the speakers, not what was heard: a muted device looks identical from here.
          </p>
        </Panel>

        <Panel title="LiveKit">
          <Stat label="Status" value={livekit.status} tone={livekit.status === "connected" ? "good" : livekit.status === "not configured" || livekit.status === "idle" ? "off" : livekit.status === "error" || livekit.status === "disconnected" ? "bad" : "wait"} />
          <Stat label="URL" value={ready?.livekit.url ?? "n/a"} />
          <Stat label="Audio tracks" value={String(livekit.tracks)} />
          <Stat label="Audio clock" value={livekit.audioClockMs() === null ? "wall clock from speaking state" : "remote audio"} />
          <Stat label="Raw audio chunks ignored" value={String(hud.audioChunksIgnored)} />
          {livekit.status === "playback blocked" ? (
            <button type="button" onClick={() => void livekit.unlockPlayback()} className="mt-2 border border-amber-300/40 bg-amber-300/10 px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.16em] text-amber-200">
              Unlock playback
            </button>
          ) : null}
          {livekit.detail ? <p className="mt-2 text-[11px] leading-5 text-red-200/90">{livekit.detail}</p> : null}
          <p className="mt-2 text-[11px] leading-4 text-[#718898]">
            LiveKit is a transport this service can mint tokens for and has never published into, so
            the raw audio path above is the one that carries the voice. This panel stays because a
            configured LiveKit would silence that path, and a reader needs to see which is live.
          </p>
        </Panel>

        <Panel title="Model">
          <form onSubmit={applyModel} className="flex gap-2">
            <label className="sr-only" htmlFor="presence-model-url">
              Avatar GLB URL
            </label>
            <input
              id="presence-model-url"
              value={modelDraft}
              onChange={(event) => setModelDraft(event.target.value)}
              placeholder="GLB URL (leave empty for the procedural head)"
              className="min-w-0 flex-1 border border-[#2b4558]/90 bg-black/30 px-3 py-1.5 font-mono text-[11px] text-white outline-none transition placeholder:text-white/50 focus:border-[#4fb3a5]/60"
            />
            <button type="submit" className="border border-white/15 px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.16em] text-white/70 transition hover:border-white/30 hover:text-white">
              Apply
            </button>
          </form>
          <p className="mt-2 text-[11px] leading-4 text-[#718898]">
            Default from NEXT_PUBLIC_DEVON_AVATAR_URL{DEFAULT_MODEL_URL ? "" : " (unset)"}. The rigged DEVON avatar is an owned-likeness asset behind its own gate and is not shipped here; the procedural head proves the pipeline in its place.
          </p>
        </Panel>
      </div>
    </div>
  );
}
