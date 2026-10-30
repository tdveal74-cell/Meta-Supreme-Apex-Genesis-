"""Align an edited still to its native frame and measure what moved.

Run from a throwaway virtual environment, never the project's own, because
OpenCV is not pinned by this repository:

    python3 -m venv /tmp/<scratch>/cvenv
    /tmp/<scratch>/cvenv/bin/pip install opencv-python-headless numpy
    /tmp/<scratch>/cvenv/bin/python align_still.py NATIVE.png EDITED.png OUT_PREFIX \
        --boxes "scarf=760,250,960,460" "lobby=150,0,560,560"

Prints the registration of three static regions before and after an affine
alignment, writes OUT_PREFIX_aligned.png and OUT_PREFIX_diffheat.jpg, and
reports the shift of every named box. Box coordinates are x0,y0,x1,y1 in the
native frame. A phase-correlation response below about 0.3 means the shift is
not trustworthy, usually because the content inside the box changed.
"""

import argparse

import cv2
import numpy as np

STATIC_REGIONS = {
    "skyline": (0, 300, 700, 1500),
    "lobby_left": (0, 600, 0, 380),
    "right_lamp": (0, 700, 1650, 1920),
}


def gray(image):
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0


def shift(native, other, x0, y0, x1, y1):
    a = gray(native)[y0:y1, x0:x1]
    b = gray(other)[y0:y1, x0:x1]
    window = cv2.createHanningWindow(a.shape[::-1], cv2.CV_32F)
    (dx, dy), response = cv2.phaseCorrelate(a, b, window)
    return dx, dy, response


def report(label, native, other):
    print(label)
    for name, (y0, y1, x0, x1) in STATIC_REGIONS.items():
        dx, dy, response = shift(native, other, x0, y0, x1, y1)
        print(f"  {name:12s} dx={dx:+.3f} dy={dy:+.3f} response={response:.2f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("native")
    parser.add_argument("edited")
    parser.add_argument("prefix")
    parser.add_argument("--boxes", nargs="*", default=[], help="name=x0,y0,x1,y1")
    args = parser.parse_args()

    native = cv2.imread(args.native, cv2.IMREAD_COLOR)
    edited = cv2.imread(args.edited, cv2.IMREAD_COLOR)
    if native is None or edited is None:
        raise SystemExit("could not read one of the images")
    height, width = native.shape[:2]
    print(f"native {width}x{height}, edited {edited.shape[1]}x{edited.shape[0]}")
    if abs(edited.shape[1] / edited.shape[0] - width / height) > 0.001:
        print("edited still is not the native aspect ratio; aligning, not stretching")

    resized = cv2.resize(edited, (width, height), interpolation=cv2.INTER_AREA)
    report("plain resize", native, resized)

    scale = 0.5
    small_native = cv2.resize(gray(native), None, fx=scale, fy=scale)
    small_edited = cv2.resize(gray(resized), None, fx=scale, fy=scale)
    warp = np.eye(2, 3, dtype=np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-7)
    correlation, warp = cv2.findTransformECC(
        small_native, small_edited, warp, cv2.MOTION_AFFINE, criteria, None, 5
    )
    warp[:, 2] /= scale
    print(f"affine correlation {correlation:.4f}, warp {np.round(warp, 5).tolist()}")
    aligned = cv2.warpAffine(
        resized,
        warp,
        (width, height),
        flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
        borderMode=cv2.BORDER_REPLICATE,
    )
    report("after affine alignment", native, aligned)
    cv2.imwrite(f"{args.prefix}_aligned.png", aligned)

    difference = cv2.absdiff(native, aligned).max(axis=2).astype(np.float32)
    blurred = cv2.GaussianBlur(difference, (0, 0), 6)
    heat = cv2.applyColorMap(np.clip(blurred * 4, 0, 255).astype(np.uint8), cv2.COLORMAP_JET)
    cv2.imwrite(f"{args.prefix}_diffheat.jpg", cv2.addWeighted(native, 0.45, heat, 0.55, 0))

    for box in args.boxes:
        name, _, coords = box.partition("=")
        x0, y0, x1, y1 = (int(value) for value in coords.split(","))
        dx, dy, response = shift(native, aligned, x0, y0, x1, y1)
        print(f"  box {name:20s} dx={dx:+.2f} dy={dy:+.2f} response={response:.2f}")


if __name__ == "__main__":
    main()
