"""Read advance widths for the ARIAL table's keys out of a TrueType file.

    python3 -I n8n/tqo-v5/live-thumb-layout/liberation_widths.py \
        /usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf \
        n8n/tqo-v5/live-thumb-layout/after.js > liberation_sans_widths.json

Liberation Sans is metric compatible with Arial, which is what GraphicsMagick
draws the thumbnail headline in. The widths come from the font's own cmap, hhea,
head and hmtx tables, with no font library, so the fixture this writes is a
second source for the table in after.js rather than a copy of it. CI never runs
this script; thumb_layout.test.mjs reads the fixture it wrote.
"""

import hashlib
import json
import re
import struct
import sys


def table_offsets(font):
    count = struct.unpack(">H", font[4:6])[0]
    out = {}
    for i in range(count):
        tag, _, offset, _ = struct.unpack(">4sIII", font[12 + 16 * i:28 + 16 * i])
        out[tag.decode()] = offset
    return out


def unicode_subtable(font, cmap):
    count = struct.unpack(">H", font[cmap + 2:cmap + 4])[0]
    for i in range(count):
        platform, encoding, sub = struct.unpack(">HHI", font[cmap + 4 + 8 * i:cmap + 12 + 8 * i])
        if platform == 3 and encoding == 1 and struct.unpack(">H", font[cmap + sub:cmap + sub + 2])[0] == 4:
            return cmap + sub
    raise SystemExit("the font has no Windows Unicode format 4 cmap")


def glyph_lookup(font, cmap):
    s = unicode_subtable(font, cmap)
    seg2 = struct.unpack(">H", font[s + 6:s + 8])[0]
    seg = seg2 // 2
    ends = struct.unpack(">%dH" % seg, font[s + 14:s + 14 + seg2])
    starts = struct.unpack(">%dH" % seg, font[s + 16 + seg2:s + 16 + 2 * seg2])
    deltas = struct.unpack(">%dh" % seg, font[s + 16 + 2 * seg2:s + 16 + 3 * seg2])
    ranges_at = s + 16 + 3 * seg2
    ranges = struct.unpack(">%dH" % seg, font[ranges_at:ranges_at + seg2])

    def glyph(code):
        for k in range(seg):
            if starts[k] <= code <= ends[k]:
                if ranges[k] == 0:
                    return (code + deltas[k]) & 0xFFFF
                at = ranges_at + 2 * k + ranges[k] + 2 * (code - starts[k])
                g = struct.unpack(">H", font[at:at + 2])[0]
                return (g + deltas[k]) & 0xFFFF if g else 0
        return 0

    return glyph


def main(font_path, after_path):
    font = open(font_path, "rb").read()
    at = table_offsets(font)
    units = struct.unpack(">H", font[at["head"] + 18:at["head"] + 20])[0]
    metrics = struct.unpack(">H", font[at["hhea"] + 34:at["hhea"] + 36])[0]
    glyph = glyph_lookup(font, at["cmap"])

    def advance(g):
        g = min(g, metrics - 1)
        return struct.unpack(">H", font[at["hmtx"] + 4 * g:at["hmtx"] + 4 * g + 2])[0]

    block = re.search(r"const ARIAL = \{([\s\S]*?)\};", open(after_path, encoding="utf-8").read()).group(1)
    keys = []
    for quoted, double, bare in re.findall(r"'((?:\\'|[^'])+)'\s*:|\"([^\"]+)\"\s*:|\b([A-Za-z_])\s*:", block):
        keys.append((quoted or double or bare).replace("\\'", "'"))
    widths = {}
    for key in keys:
        g = glyph(ord(key))
        if not g:
            raise SystemExit("the font has no glyph for " + repr(key))
        widths[key] = round(advance(g) * 1000 / units)
    print(json.dumps({
        "font": font_path.rsplit("/", 1)[-1],
        "sha256": hashlib.sha256(font).hexdigest(),
        "unitsPerEm": units,
        "read": "cmap 3/1 format 4, hhea, head and hmtx, rounded to thousandths of an em",
        "widths": widths,
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
