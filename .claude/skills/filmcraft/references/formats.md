# FilmCraft file formats — what the code actually reads and writes

Version: repo tag **v0.9.0**, commit `4a69a038d32761f604b3c7e4845b21fb40b3cbe4` (inspected 2026-10-18).
Every list below is read out of the code, not the marketing docs.

## Import extension lists (authoritative)

`crates/media/src/lib.rs:175-179`:

```rust
STILL_EXTENSIONS = ["png","jpg","jpeg","gif","webp","tif","tiff","bmp","tga","dpx","exr","hdr","dng"]
AUDIO_EXTENSIONS = ["wav","wave","bwf","aif","aiff","mp3","mp2","m4a","aac","flac","ogg","opus"]
VIDEO_EXTENSIONS = ["mp4","m4v","mov","mkv","webm","avi","mxf","mts","m2ts","m2t","ts","mpg","mpeg",
                    "vob","mod","tod","m2v","m1v","mpv","3gp","y4m","apv"]
```

`crates/media/src/lib.rs:181-184` — `is_importable()` is exactly membership in those three lists (the Media
Browser and drag/drop filter on it). Files that fail to open still import with an error per file.

Container openers, in the order they are tried (`crates/codecs/src/lib.rs:135-137`):
`mp4` (MP4/MOV), `mkv` (Matroska/WebM), `mxf` (OP1a/OP-Atom), `ogg`, `mpeg` (TS/PS/ES), `apv`, `avi`, `y4m`,
`audio` (standalone compressed audio). Then, in `filmcraft_media::open_bytes` (`crates/media/src/lib.rs:190-214`):
OpenEXR sniff, Radiance HDR sniff, WAV, animated GIF/APNG, else generic stills.

## Video codecs

| Codec | Decode | Encode | Evidence |
|---|:--:|:--:|---|
| H.264/AVC | yes (8-bit 4:2:0; High 10/4:2:2 only via OS hardware) | yes (own encoder; profiles/b-frames/CABAC, CRF/CBR/VBR/2-pass per README) | `crates/h264`, `crates/h264enc`, `docs/gaps.md` G3 |
| HEVC/H.265 | yes (Main, Main 10) | **hardware only** (NVENC/VideoToolbox; no software encoder) | `crates/hevc`, `crates/export/src/lib.rs:71-79` |
| AV1 | yes (Main profile) | none | `crates/av1`, `crates/export/src/lib.rs:80-83` |
| VP8 / VP9 | yes | none | `crates/vp8`, `crates/vp9` |
| Apple ProRes | yes (Proxy…4444 XQ) | yes (422 all flavours, 4444/4444XQ in the UI presets) | `crates/prores`, `crates/export/src/presets.rs` |
| Avid DNxHD/HR | yes (ST 2019-1) | yes (DNxHR) | `crates/dnx` |
| APV (RFC 9924) | yes | yes | `crates/apv` |
| MJPEG | yes | yes | `crates/codecs/src/avi.rs`, `crates/export` |
| MPEG-1 / MPEG-2 video | yes | none | `crates/mpeg2v`, `crates/codecs/src/mpeg.rs` |
| Uncompressed RGB/YUV | yes (AVI) / Y4M | via Y4M only | `crates/codecs/src/{avi,y4m}.rs` |
| DNG / CinemaDNG | yes (TIFF container, uncompressed + lossless JPEG) | none | `crates/dng` |

Not decodable: DivX/Xvid (MPEG-4 Part 2), DV/DVCPRO, camera RAW other than DNG, HEIF/HEIC, PSD, JPEG 2000.

## Audio codecs

Decode: AAC-LC, AC-3, E-AC-3 (MP4/MOV/MKV/TS), Opus (SILK/CELT/hybrid/multistream), Vorbis, MP1/MP2/MP3,
FLAC, ALAC, PCM, WAV/BWF.
Encode (`crates/export/src/lib.rs`): AAC-LC (MP4/MOV, `.m4a`, ADTS `.aac`), PCM (WAV/AIFF/MOV/MXF),
FLAC, and the audio inside H.264/HEVC/ProRes/DNxHR/APV/MJPEG exports.
MP3 is **read-only** (`docs/file-format-parity.md` audio table).

## Still images and sequences

Read: PNG, JPEG, GIF, WebP, TIFF, BMP, TGA (incl. RLE/colour maps), DPX (luma/RGB/RGBA, 8–16-bit, packed
10/12-bit, Y'CbCr), OpenEXR (scan-line: none/RLE/ZIPS/ZIP/PXR24, half/float/uint), Radiance HDR, DNG.
Animated GIF and APNG import as clips with transparency (`crates/media/src/animated.rs`).
Write (as numbered sequences): PNG, TIFF, BMP, JPEG, TGA, DPX (10-bit), OpenEXR (half float, linear; must be
uncompressed/RLE/ZIPS/ZIP, or `alpha: true` for RGBA), plus animated GIF (`Format` enum, `crates/export/src/lib.rs:95-127`).
No PSD, PIZ/B44/DWA EXR, HEIC.

## Captions and subtitles

`crates/captions/src/`: `srt.rs`, `vtt.rs`, `scc.rs`, `mcc.rs` (608+708), `stl.rs` (EBU STL), `ttml.rs`
(TTML/IMSC1/DFXP), `cea608.rs`, `burn.rs` (layout + burn-in).
`captions.import` auto-detects by extension and content; `captions.export` takes
`format: "srt|vtt|scc|mcc|stl|ttml|dfxp"` or infers it from the path, plus `track` and `dropFrame`
(`crates/engine/src/captions.rs:491-509`). CEA-608/708 embedded in a video stream are **not** read or written;
use burn-in (`burnCaptions: true`) or a sidecar (`captionSidecar: "srt"|"vtt"`).

## Project file — `.fcproj`

- UTF-8 JSON envelope: `{"format": "filmcraft.project", "schema_version": 13, "generator": …, "project": {…}, "view": {…}}`
  (`crates/format/src/lib.rs`, `docs/project-files.md:8-16`). Compact on write (~1.4 MB for 2 000 clips).
- Reading: migrations `MIGRATIONS[i]` upgrade v*i+1* → v*i+2*; the current build reads **every version from 1 to 13**;
  newer versions are refused with an explicit message (`docs/project-files.md:79-86`).
- `view` (open sequences, active sequence, zoom/scroll/playhead per sequence) sits beside the project, is not
  undoable and does not dirty the project.
- Media is by path only; each item also stores a size + first/last-MiB fingerprint (`MediaClip::identity`) used
  by relinking.
- Writes are atomic (temp in the same directory → fsync → rename → fsync dir) — projects, auto-saves, recovery
  snapshots, preferences (`docs/project-files.md:88-99`).
- Stored paths from documents are opened only when local or on the document's own network share
  (`crates/engine/src/doc_path.rs`, built on `craft-docpath`); other paths become offline items.

Related files: auto-saves `Auto-Save/<name>-YYYY-MM-DD_HH-MM-SS.fcproj`; recovery
`Recovery/<started>-<pid>[-n]/{snapshot.fcproj,session.json,lock}`; preferences `<data dir>/preferences.json`
(schema version 2); effect presets `<data dir>/effect-presets.json`
(`{"format":"filmcraft.effect-presets","version":1,…}`); user export presets `<data dir>/export-presets.json`;
graphics templates `.fcgt`; label colour presets `<data dir>/Label Presets/*.json`.

## Interchange

| Format | Extensions | Import | Export | Module |
|---|---|:--:|:--:|---|
| Final Cut Pro 7 XML (`xmeml` v4/v5) | `.xml` | yes | yes | `crates/interchange/src/fcp7.rs` |
| FCPXML 1.9–1.11 | `.fcpxml`, `.fcpxmld` | yes | yes | `fcpxml.rs` |
| OpenTimelineIO | `.otio` | yes | yes | `otio.rs` |
| CMX 3600 EDL | `.edl` | yes | yes | `edl.rs` |
| AAF (Edit Protocol, MS-CFB) | `.aaf` | yes | yes | `aaf/` (`crates/cfb`) |
| OMF Interchange 2.0 | `.omf`, `.omfi` | yes | yes | `omf/` |
| Avid Log Exchange | `.ale` | no | yes | `ale.rs` |
| Markers CSV | `.csv` | – | yes | `crates/engine/src/marker_export.rs` |

Format detection sniffs content (AAF/OMF structured storage, `<xmeml`/`<fcpxml` headers) before trusting the
extension (`crates/interchange/src/lib.rs:95-130`). Imports merge as one undoable step and return a report of
everything that could not be represented.

## Export formats (`crates/export/src/lib.rs:66-133`)

`h264`, `hevc*`, `av1*`, `prores`, `dnxhr`, `apv`, `mjpeg`, `png`, `tiff`, `bmp`, `jpg`, `tga`, `dpx`, `exr`,
`gif`, `wav`, `aiff`, `aac`, `flac`, `mxf-op1a`, `mxf-opatom` — `*` = offered only when a platform hardware
encoder registers one (`Format::available`, `register_encoder`). Container by format: MP4/MOV (H.264, HEVC,
AV1, ProRes, DNxHR, APV, MJPEG), MXF OP1a (DNxHR, ProRes, H.264 + PCM, start timecode), MXF OP-Atom
(picture + one mono PCM file per channel), numbered stills, GIF, WAV/AIFF/AAC/FLAC.

A format may change the output extension: exporting `out.mp4` as APV writes `out.mp4.mov`
(`apps/filmcraft-cli/src/main.rs:500-516`) — always read the returned `path`.

## Proxies, ingest, Project Manager

Proxy presets (`docs/project-files.md:329-333`): `prores_proxy_quarter` (default), `prores_proxy_half`,
`prores_lt_half`, `h264_quarter`, `h264_half`; written to `<media folder>/Proxies/<name>_Proxy.<ext>`.
Ingest actions: `copy`, `transcode`, `createProxies`, `copyAndCreateProxies` (`project.ingestSettings`).
Project Manager modes `collect` and `consolidate` with `handles` (frames) and transcode presets
`prores_lt`, `prores_hq`, `h264`; `dryRun` returns the plan and disk estimate.
`Export always uses full resolution`, never the proxy (`docs/project-files.md:343`).
