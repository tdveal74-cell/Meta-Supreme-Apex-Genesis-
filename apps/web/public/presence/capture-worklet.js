/**
 * Push to talk capture worklet.
 *
 * Runs on the audio thread and hands the main thread contiguous mono blocks
 * of Float32 samples. The main thread converts them to pcm_s16le and sends
 * them as listen_chunk, which apps/presence/hearing.py assembles into one
 * clip.
 *
 * WHY A WORKLET AND NOT THE ANALYSER useBargeIn ALREADY HAS. An AnalyserNode
 * answers "is someone talking right now": getFloatTimeDomainData copies
 * whatever is in its window at the moment you ask, so two reads a frame apart
 * overlap or skip depending on when the frame landed. Barge in only needs a
 * level, so that is fine there. A transcriber needs every sample once and in
 * order, and this is the only node that gives that.
 *
 * WHY IT BATCHES HERE RATHER THAN ON THE MAIN THREAD. process() is called
 * with 128 samples, which at 48 kHz is 2.67 ms, so posting each block would
 * be 375 postMessage calls a second and 375 structured clones. Accumulating
 * to about a quarter second first makes it four. blocksPerChunk in
 * lib/presence/capture.ts works out the count and passes it in.
 *
 * This file is served as a static asset rather than built into the bundle,
 * because addModule takes a URL. It is deliberately plain ES2019 with no
 * imports: a worklet has no module resolver and no DOM.
 */

class CaptureProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const settings = (options && options.processorOptions) || {};
    const blocks = Number(settings.blocksPerChunk);
    this.blocksPerChunk = Number.isFinite(blocks) && blocks >= 1 ? Math.floor(blocks) : 1;
    this.pending = [];
    this.pendingLength = 0;
    this.capturing = false;

    this.port.onmessage = (event) => {
      const data = event.data || {};
      if (data.t === "start") {
        this.pending = [];
        this.pendingLength = 0;
        this.capturing = true;
      } else if (data.t === "stop") {
        // Flush whatever is held so the tail of the sentence is not lost.
        // A clip that drops its last quarter second ends mid word, and a
        // transcriber completes it into a word nobody said.
        this.capturing = false;
        this.flush();
      }
    };
  }

  flush() {
    if (this.pendingLength === 0) return;
    const merged = new Float32Array(this.pendingLength);
    let offset = 0;
    for (let i = 0; i < this.pending.length; i += 1) {
      merged.set(this.pending[i], offset);
      offset += this.pending[i].length;
    }
    this.pending = [];
    this.pendingLength = 0;
    this.port.postMessage({ t: "chunk", samples: merged }, [merged.buffer]);
  }

  process(inputs) {
    if (!this.capturing) return true;
    const input = inputs[0];
    if (!input || input.length === 0) return true;
    const channel = input[0];
    if (!channel || channel.length === 0) return true;

    // The input buffer is reused between calls, so this has to be a copy.
    this.pending.push(new Float32Array(channel));
    this.pendingLength += channel.length;
    if (this.pending.length >= this.blocksPerChunk) this.flush();
    return true;
  }
}

registerProcessor("presence-capture", CaptureProcessor);
