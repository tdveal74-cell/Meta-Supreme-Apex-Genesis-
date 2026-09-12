/**
 * Energy based voice activity detector, as a pure state machine.
 *
 * feed() takes an RMS level and a clock reading and answers with a transition
 * or null. Speech has to hold above the threshold for the attack window
 * before "speech_start" fires, so a click or a knock does not count, and
 * silence has to hold for the hangover before "speech_end" fires, so a pause
 * for breath does not end the turn.
 *
 * No browser APIs here: the caller owns the microphone and the clock.
 */

export type VadEvent = "speech_start" | "speech_end" | null;

export type VadOptions = {
  /** RMS level at or above which a tick counts as energy. Default 0.02. */
  threshold?: number;
  /** Energy must persist this long before speech starts. Default 40 ms. */
  attackMs?: number;
  /** Silence must persist this long before speech ends. Default 300 ms. */
  hangoverMs?: number;
};

export const VAD_DEFAULTS = {
  threshold: 0.02,
  attackMs: 40,
  hangoverMs: 300,
};

export class VoiceActivityDetector {
  threshold: number;
  attackMs: number;
  hangoverMs: number;
  speaking = false;
  /** Clock reading of the first energetic tick in the current run, or null. */
  energySince: number | null = null;
  /** Clock reading of the first silent tick in the current run, or null. */
  silenceSince: number | null = null;

  constructor(options: VadOptions = {}) {
    this.threshold = options.threshold ?? VAD_DEFAULTS.threshold;
    this.attackMs = options.attackMs ?? VAD_DEFAULTS.attackMs;
    this.hangoverMs = options.hangoverMs ?? VAD_DEFAULTS.hangoverMs;
  }

  feed(rms: number, nowMs: number): VadEvent {
    const energetic = Number.isFinite(rms) && rms >= this.threshold;

    if (!this.speaking) {
      if (!energetic) {
        this.energySince = null;
        return null;
      }
      if (this.energySince === null) this.energySince = nowMs;
      if (nowMs - this.energySince >= this.attackMs) {
        this.speaking = true;
        this.energySince = null;
        this.silenceSince = null;
        return "speech_start";
      }
      return null;
    }

    if (energetic) {
      this.silenceSince = null;
      return null;
    }
    if (this.silenceSince === null) this.silenceSince = nowMs;
    if (nowMs - this.silenceSince >= this.hangoverMs) {
      this.speaking = false;
      this.silenceSince = null;
      this.energySince = null;
      return "speech_end";
    }
    return null;
  }

  reset(): void {
    this.speaking = false;
    this.energySince = null;
    this.silenceSince = null;
  }
}
