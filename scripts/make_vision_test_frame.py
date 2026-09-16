#!/usr/bin/env python3
"""Generate the one frame that is allowed to live in `var/vision-inbox`.

Ruled 2026-09-16. `.gitignore` keeps every frame out of this public repository
because a frame is whatever was on somebody's screen. This one is the named
exception, and it earns that by being GENERATED rather than captured: every
pixel comes from the code below, so there is nothing in it that was ever on a
screen.

It exists because a deployed container has no other way to get a frame. Nothing
writes into `var/vision-inbox` at runtime, and a Railway container's disk is
wiped on each deploy, so without a committed fixture the deployed
`vision.describe` has nothing to read and the OpenRouter key stays unproven.

The output is deterministic to the byte, which `test_devon_vision_fixture.py`
asserts by regenerating it and comparing. That is what stops the file being
quietly swapped for a real screenshot later.

    python3 scripts/make_vision_test_frame.py

Writes `var/vision-inbox/devon-vision-test.png` and prints its digest.
"""

from __future__ import annotations

import hashlib
import pathlib
import struct
import zlib

WIDTH, HEIGHT = 480, 240
BACKGROUND = (24, 26, 31)
FOREGROUND = (236, 232, 225)
ACCENT = (196, 122, 64)

TARGET = pathlib.Path("var/vision-inbox/devon-vision-test.png")

#: A 5x7 bitmap font, carrying only the glyphs this frame draws.
GLYPHS = {
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "G": ["01110", "10001", "10000", "10111", "10001", "10001", "01111"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    " ": ["00000"] * 7,
}


def _draw(pixels, text, origin_x, origin_y, scale, colour):
    cursor = origin_x
    for character in text:
        glyph = GLYPHS.get(character)
        if glyph is None:
            cursor += 6 * scale
            continue
        for row_index, row in enumerate(glyph):
            for column_index, bit in enumerate(row):
                if bit != "1":
                    continue
                for dy in range(scale):
                    for dx in range(scale):
                        y = origin_y + row_index * scale + dy
                        x = cursor + column_index * scale + dx
                        if 0 <= y < HEIGHT and 0 <= x < WIDTH:
                            pixels[y][x] = colour
        cursor += 6 * scale


def _chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return (
        struct.pack(">I", len(payload))
        + body
        + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
    )


def render() -> bytes:
    """The frame, as PNG bytes. Same input, same output, every time."""
    pixels = [[BACKGROUND for _ in range(WIDTH)] for _ in range(HEIGHT)]

    _draw(pixels, "DEVON VISION", 40, 54, 5, FOREGROUND)
    _draw(pixels, "TEST FRAME 3", 40, 118, 4, ACCENT)

    # A solid bar, so a describer has a shape to report and not only text.
    for y in range(186, 200):
        for x in range(40, 260):
            pixels[y][x] = ACCENT

    raw = b"".join(
        b"\x00" + b"".join(bytes(pixels[y][x]) for x in range(WIDTH))
        for y in range(HEIGHT)
    )
    header = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(raw, 9))
        + _chunk(b"IEND", b"")
    )


def main() -> int:
    data = render()
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_bytes(data)
    print(f"{TARGET}  {len(data)} bytes  sha256 {hashlib.sha256(data).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
