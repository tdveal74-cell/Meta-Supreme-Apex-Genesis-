"""Scan a locked-camera clip for static-region drift.

Reads every STEP-th frame of an mp4, crops four rows off top and bottom when
the frame is 1088 tall, and measures the shift of each static region against
frame 0 and against the previous sample by windowed phase correlation alone.
That is the seed align_still.py starts from; align_still then refines it with
an ECC translation fit, so the two read the same frame up to about 0.17 px
apart (SH100 frame 96, 2026-10-31: 0.59 px by align_still on the PNG, 0.42 by
this scan on the mp4). The difference is the estimator, not the h264 decode.
This is the overview; align_still on the lossless frames is the measurement.

The built-in regions are drawn on the 1920x1080 Episode 1 street plate, so a
clip of another size needs --regions; the scanner refuses otherwise. Prints
the peak absolute shift per region and where it lands, then a thinned table.

Usage: python3 drift_scan.py CLIP.mp4 [--step 4] [--regions name=x0,y0,x1,y1 ...]
"""
import argparse

import cv2
import numpy as np

REGIONS = {
    "skyline": (700, 0, 1500, 190),
    "lobby": (0, 0, 380, 280),
    "right_lamp": (1680, 0, 1920, 430),
}


def gray(im):
    return cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0


def shift(a, b, box):
    x0, y0, x1, y1 = box
    pa = a[y0:y1, x0:x1].copy()
    pb = b[y0:y1, x0:x1].copy()
    win = cv2.createHanningWindow(pa.shape[::-1], cv2.CV_32F)
    (dx, dy), r = cv2.phaseCorrelate(pa, pb, win)
    return dx, dy, r


def read_samples(path, step):
    cap = cv2.VideoCapture(path)
    frames = []
    idx = 0
    while True:
        ok, im = cap.read()
        if not ok:
            break
        if idx % step == 0:
            if im.shape[0] == 1088:
                im = im[4:1084]
            frames.append((idx, gray(im)))
        idx += 1
    return idx, frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("--step", type=int, default=4)
    ap.add_argument("--regions", nargs="*")
    a = ap.parse_args()
    regions = REGIONS
    if a.regions:
        regions = {}
        for text in a.regions:
            name, value = text.split("=")
            regions[name] = tuple(int(x) for x in value.split(","))
    total, frames = read_samples(a.clip, a.step)
    if not frames:
        raise SystemExit(f"{a.clip}: no frames read")
    h, w = frames[0][1].shape
    if not a.regions and (w, h) != (1920, 1080):
        raise SystemExit(f"{a.clip}: frames are {w}x{h}; the built-in regions are for 1920x1080, pass --regions")
    print(f"{a.clip}: {total} frames read, {len(frames)} sampled every {a.step}")
    base = frames[0][1]
    prev = base
    peak = {k: (0.0, 0.0, 0) for k in regions}
    step_peak = {k: (0.0, 0) for k in regions}
    rows = []
    for fi, g in frames[1:]:
        row = [fi]
        for k, box in regions.items():
            dx, dy, r = shift(base, g, box)
            sdx, sdy, _ = shift(prev, g, box)
            row += [dx, dy, r]
            if max(abs(dx), abs(dy)) > max(abs(peak[k][0]), abs(peak[k][1])):
                peak[k] = (dx, dy, fi)
            if max(abs(sdx), abs(sdy)) > step_peak[k][0]:
                step_peak[k] = (max(abs(sdx), abs(sdy)), fi)
        rows.append(row)
        prev = g
    for k in regions:
        dx, dy, fi = peak[k]
        print(f"  {k:10s} peak vs f0: dx={dx:+.3f} dy={dy:+.3f} at f{fi}; "
              f"largest step between samples {step_peak[k][0]:.3f} px at f{step_peak[k][1]}")
    print("  frame  " + "  ".join(f"{k[:15]:>15s}" for k in regions))
    for row in rows[:: max(1, len(rows) // 12)]:
        print(f"  {row[0]:5d}  " + "  ".join(f"{row[1 + 3 * i]:+7.3f},{row[2 + 3 * i]:+7.3f}" for i in range(len(regions))))


if __name__ == "__main__":
    main()
