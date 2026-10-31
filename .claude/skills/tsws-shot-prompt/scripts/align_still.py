"""Align an edited still to its native frame and measure what moved.

Run it with the Python of a throwaway virtual environment in the session
scratchpad, never the project's own, because OpenCV is not pinned by this
repository. With SCRATCH set to the scratchpad directory:

    python3 -m venv "$SCRATCH/cvenv"
    "$SCRATCH/cvenv/bin/pip" install opencv-python-headless numpy
    "$SCRATCH/cvenv/bin/python" .claude/skills/tsws-shot-prompt/scripts/align_still.py \
        NATIVE.png EDITED.png OUT_PREFIX --boxes "scarf=760,250,960,460"

It resizes the edited still to the native size, fits an affine to the whole
frame (people included), and prints the shift of each static region before and
after that fit. It writes OUT_PREFIX_aligned.png and OUT_PREFIX_diffheat.jpg and
reports the shift of every named box. It prints numbers only and passes no
verdict. No pass or fail tolerance for a still has been ruled, so compare the
numbers with the notes under "Checking a still" in SKILL.md, report the worst
region, and put accept or reject to Tee on a card.

Every region and box is x0,y0,x1,y1 in native pixels. The built-in static
regions were drawn on the 1920x1080 Episode 1 street plate (SH020 native frames
0 and 191) so that no person stands in them in either frame. They hold only for
that plate, so the script refuses any other native size, and says which set it
used, unless --regions names the regions for the plate in hand. A region with a
person in it measures the person, and a region that spans two surfaces the edit
moved differently can read near zero, so keep each region on one surface.

Each shift is read twice. Phase correlation with a Hanning window gives a first
answer and a response, but on known shifts of SH020 frame 191 it pulled
sub-pixel shifts toward the nearest whole pixel by up to 0.30 px. A translation
ECC seeded with that answer read every known shift from 0.1 to 19 px within
0.03 px, so the ECC figure is printed when it converges and "phase" is printed
when it does not. A low response means the content inside the box changed and
the shift is not trustworthy; compare it with the static regions' responses on
the same run rather than with a fixed number.
"""

import argparse

import cv2
import numpy as np

STREET_SIZE = (1920, 1080)
STATIC_REGIONS = {
    "skyline": (700, 0, 1500, 190),
    "lobby": (0, 0, 380, 280),
    "right_lamp": (1680, 0, 1920, 430),
}
MIN_SIDE = 16


def gray(image):
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0


def parse_box(text, width, height):
    name, sep, coords = text.partition("=")
    parts = coords.split(",")
    if not sep or not name or len(parts) != 4:
        raise SystemExit(f"bad box {text!r}: write name=x0,y0,x1,y1")
    try:
        x0, y0, x1, y1 = (int(value) for value in parts)
    except ValueError:
        raise SystemExit(f"bad box {text!r}: coordinates must be whole pixels") from None
    if x1 <= x0 or y1 <= y0:
        raise SystemExit(f"box {text!r} is empty or reversed: x1 must exceed x0 and y1 exceed y0")
    if not (0 <= x0 and x1 <= width and 0 <= y0 and y1 <= height):
        raise SystemExit(f"box {text!r} is outside the {width}x{height} native frame")
    if x1 - x0 < MIN_SIDE or y1 - y0 < MIN_SIDE:
        raise SystemExit(f"box {text!r} is under {MIN_SIDE} px on a side")
    return name, (x0, y0, x1, y1)


def shift(native, other, box):
    x0, y0, x1, y1 = box
    a = np.ascontiguousarray(gray(native)[y0:y1, x0:x1])
    b = np.ascontiguousarray(gray(other)[y0:y1, x0:x1])
    window = cv2.createHanningWindow(a.shape[::-1], cv2.CV_32F)
    # phaseCorrelate with a window can modify its inputs in place, so it gets copies.
    (dx, dy), response = cv2.phaseCorrelate(a.copy(), b.copy(), window)
    warp = np.float32([[1, 0, dx], [0, 1, dy]])
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 500, 1e-8)
    try:
        _, warp = cv2.findTransformECC(a, b, warp, cv2.MOTION_TRANSLATION, criteria, None, 5)
    except cv2.error:
        return dx, dy, response, "phase"
    return float(warp[0, 2]), float(warp[1, 2]), response, "ecc"


def report(label, native, other, regions):
    print(label)
    for name, box in regions.items():
        dx, dy, response, how = shift(native, other, box)
        print(f"  {name:12s} dx={dx:+.3f} dy={dy:+.3f} response={response:.2f} {how}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("native")
    parser.add_argument("edited")
    parser.add_argument("prefix")
    parser.add_argument("--boxes", nargs="*", default=[], help="name=x0,y0,x1,y1")
    parser.add_argument(
        "--regions",
        nargs="+",
        help="name=x0,y0,x1,y1 static regions, required for any plate but the street plate",
    )
    args = parser.parse_args()

    native = cv2.imread(args.native, cv2.IMREAD_COLOR)
    edited = cv2.imread(args.edited, cv2.IMREAD_COLOR)
    if native is None or edited is None:
        raise SystemExit("could not read one of the images")
    height, width = native.shape[:2]
    print(f"opencv {cv2.__version__}, numpy {np.__version__}")
    print(f"native {width}x{height}, edited {edited.shape[1]}x{edited.shape[0]}")
    if args.regions:
        regions = dict(parse_box(text, width, height) for text in args.regions)
        print("static regions: from --regions")
    elif (width, height) == STREET_SIZE:
        regions = STATIC_REGIONS
        print("static regions: built-in, drawn for the SH020 street plate only")
    else:
        raise SystemExit(
            f"the built-in static regions are for the {STREET_SIZE[0]}x{STREET_SIZE[1]} "
            "street plate; pass --regions drawn on people-free background of this frame"
        )
    boxes = [parse_box(text, width, height) for text in args.boxes]
    if abs(edited.shape[1] / edited.shape[0] - width / height) > 0.001:
        print(
            "edited still is not the native aspect ratio; resizing to native, then fitting an affine"
        )

    resized = cv2.resize(edited, (width, height), interpolation=cv2.INTER_AREA)
    report("plain resize", native, resized, regions)

    scale = 0.5
    small_native = cv2.resize(gray(native), None, fx=scale, fy=scale)
    small_edited = cv2.resize(gray(resized), None, fx=scale, fy=scale)
    warp = np.eye(2, 3, dtype=np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-7)
    try:
        correlation, warp = cv2.findTransformECC(
            small_native, small_edited, warp, cv2.MOTION_AFFINE, criteria, None, 5
        )
    except cv2.error:
        raise SystemExit(
            "the affine fit did not converge; the edit may not show the same frame"
        ) from None
    warp[:, 2] /= scale
    print(f"affine correlation {correlation:.4f}, warp {np.round(warp, 5).tolist()}")
    aligned = cv2.warpAffine(
        resized,
        warp,
        (width, height),
        flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
        borderMode=cv2.BORDER_REPLICATE,
    )
    report("after affine alignment", native, aligned, regions)
    cv2.imwrite(f"{args.prefix}_aligned.png", aligned)

    difference = cv2.absdiff(native, aligned).max(axis=2).astype(np.float32)
    blurred = cv2.GaussianBlur(difference, (0, 0), 6)
    heat = cv2.applyColorMap(np.clip(blurred * 4, 0, 255).astype(np.uint8), cv2.COLORMAP_JET)
    cv2.imwrite(f"{args.prefix}_diffheat.jpg", cv2.addWeighted(native, 0.45, heat, 0.55, 0))

    for name, box in boxes:
        dx, dy, response, how = shift(native, aligned, box)
        print(f"  box {name:20s} dx={dx:+.2f} dy={dy:+.2f} response={response:.2f} {how}")


if __name__ == "__main__":
    main()
