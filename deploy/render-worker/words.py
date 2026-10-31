#!/usr/bin/env python3
"""Word timings for the render worker's word_timings job.

Runs faster-whisper (base.en by default, int8 on the CPU) over each line file and
writes one JSON object keyed by the file's stem: {"L01": {"text": ..., "words":
[{"text", "start", "end", "p"}], "stt_seconds": ...}}. The worker's
acx_node_assemble job reads that file through words_path and keys it by beat id
or by the line file's stem.

Invoked only by the worker through WHISPER_PYTHON, a python that carries
faster-whisper; see DEPLOY.md, ACX Node section. Pin PyAV below 14 in that
environment: faster-whisper 1.1.1 breaks on PyAV 19 (measured 2026-10-28).
Install requests beside it: faster-whisper 1.1.1 imports it without declaring
it, and huggingface_hub stopped bringing it at 1.0 (found on the box 2026-10-31).
"""
import argparse
import json
import os
import sys
import time


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="base.en")
    ap.add_argument("--output", required=True)
    ap.add_argument("audio", nargs="+")
    a = ap.parse_args()
    from faster_whisper import WhisperModel  # imported here so a missing install is one clear line

    t = time.time()
    m = WhisperModel(a.model, device="cpu", compute_type="int8")
    print("model loaded in %.1fs" % (time.time() - t), flush=True)
    out = {}
    for f in a.audio:
        name = os.path.splitext(os.path.basename(f))[0]
        t0 = time.time()
        segs, _info = m.transcribe(f, word_timestamps=True, language="en", beam_size=5, condition_on_previous_text=False)
        words, text = [], []
        for s in segs:
            text.append(s.text.strip())
            for w in s.words:
                words.append({"text": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3), "p": round(w.probability, 3)})
        out[name] = {"text": " ".join(text), "words": words, "stt_seconds": round(time.time() - t0, 2)}
        print("%s %.2fs | %s" % (name, time.time() - t0, " ".join(text)), flush=True)
    tmp = a.output + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(out, fh, indent=1)
    os.replace(tmp, a.output)
    print("wrote", a.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
