---
name: filmcraft
description: "FilmCraft is an open-source, clean-room reimplementation of Adobe Premiere Pro in pure Rust (video editing, colour, audio, export) for macOS/Windows/Linux and the web. Trigger this skill whenever the user mentions FilmCraft (or \"fcproj\", \"filmcraft-cli\", the FilmCraft control channel/MCP server), asks what it can or cannot do, which formats it reads or writes, how to script or automate it, how to prepare or convert media for it, how to verify or repair its exports and project files, or troubleshoot it \u2014 and also when they never name the app but describe the job: \"cut this footage\", \"make a rough cut\", \"export an H.264 MP4\", \"grade this clip\", \"add captions to this video\", \"hand an EDL/AAF to an editor\", \"drive a video editor from an agent\". Prefer this skill over generic NLE knowledge for anything FilmCraft touches; do not assume Premiere-only capabilities (e.g. `.prproj` import) exist here."
---

# FilmCraft

## Overview

FilmCraft is a non-linear video editor: an open-source, **clean-room reimplementation of Adobe Premiere Pro**, written from scratch in pure Rust (README.md:14, README.md:69). Native on macOS, Windows, Linux, FreeBSD and in the browser via WebAssembly (`apps/filmcraft-web`, `docs/web.md`). Same panels/workspaces/shortcut conventions as Premiere, but new from the bitstream up: its own H.264, HEVC, VP8/VP9, AV1, ProRes, DNxHR, AAC and Opus codecs plus its own containers (MP4/MOV, Matroska, MXF, MPEG-TS, AVI, Ogg) — MP3, FLAC, ALAC and Vorbis decode through the `symphonia` crate for now (README.md:184), and no FFmpeg is linked or bundled (`Cargo.toml`, `crates/codecs/src/lib.rs`).

Architecture: a layered Cargo workspace (~45 crates + 3 apps) with a **headless engine** — every feature is an engine command reachable without a window (`docs/architecture.md` §1). The egui UI, the CLI, a JSON-lines control channel and an MCP server all dispatch the same command ids (`crates/ui-egui/src/menus.rs`, `apps/filmcraft-cli/src/main.rs`, `crates/automation/src/server.rs`).

**Maturity: alpha.** The project's own parity assessment (2026-10-10, against Premiere Pro 26.5.2) is **~86% feature breadth, ~56% "ready for real work"** (`docs/target-app-parity.md`, `README.md:287-300`). Treat every export and every project file as needing verification.

Source: GitHub `storytold/filmcraft`. This skill was written from tag **v0.9.0**, commit `4a69a038d32761f604b3c7e4845b21fb40b3cbe4`, which is the commit recorded in the installed app bundle (`/Applications/FilmCraft.app/Contents/Info.plist` → `FilmCraftBuildCommit = 4a69a038…`, `CFBundleShortVersionString = 0.9.0`) — the installed build is this build. App id `ai.storyteller.filmcraft`; minimum macOS 11.0.

Deep detail lives in `references/cli-and-protocol.md` (CLI + control channel + MCP) and `references/formats.md` (import/export tables, useful command ids).

## Capabilities (verified)

### Editing (implemented)

- Three-point editing: Source monitor In/Out → `source.insert` (`,`) / `source.overwrite` (`.`); `sequence.lift` (`;`) / `sequence.extract` (`'`) (`crates/engine/src/commands.rs:2576-2577`, `:2080`, `:2086`).
- Trim tools and modes: ripple, roll, slip, slide, rate stretch, razor; trim mode + Trim Monitor + deterministic dynamic trimming (`trim.shuttle`/`trim.tick`/`trim.shuttleStop` — `docs/control-protocol.md`, `crates/engine/src/trim.rs`).
- Add Edit (`sequence.addEdit`, ⌘K), ripple delete / close gap, nesting, markers with colours/names/durations (`crates/engine/src/commands.rs:2056`), `markers.exportCsv` (UTF-8 CSV, 100 000-marker / 16 MiB caps — `crates/engine/src/marker_export.rs:10-12`).
- **Exact integer time**: 254 016 000 000 ticks per second; 23.976/29.97-DF/59.94 are exact (`docs/architecture.md`; every command accepts `ticks`, `seconds`, `frame` or `timecode`).
- Unlimited undo/redo on copy-on-write snapshots; new projects keep 200 undo steps (`crates/engine/src/commands.rs:1144`, inside `file.newProject`).
- Multicam source sequences + live angle switching, sync/merge clips (`crates/engine/src/multicam.rs`), scene edit detection, subclips, Replace With Clip (`docs/roadmap.md` M3/M12 sections).
- Keyboard Shortcuts editor with four presets: FilmCraft Default, Premiere Pro Compatible, Final Cut Pro, Avid Media Composer Compatible (`crates/engine/src/shortcuts.rs:59-63`, `crates/engine/src/shortcut_presets.rs`).
- Workspaces: Editing, Assembly, Color, Effects, Audio, Captions and Graphics, All Panels (`crates/ui-egui/src/menus.rs:110-120`). 28 dockable panel kinds (`crates/ui-egui/src/dock.rs:14-46`); docking/floating is scriptable (`window.dockPanel`, `window.floatPanel`, `window.dockAction` — `docs/control-protocol.md`).

### Colour, effects, motion (implemented; some effects approximate)

- Lumetri-style colour: Basic Correction, Creative looks, RGB + hue/sat/luma curves, three-way colour wheels, HSL Secondary, Vignette; LUT import/export (`.cube`, `.3dl`, 1D/3D/shaper) via `lut.*`/`lumetri.*` (`docs/control-protocol.md` "Colour", `crates/engine/src/color.rs`).
- **93 video effects across 16 folders**, asserted by test `premiere_26_video_effects_catalogue` (`crates/project/src/effect/vfx.rs:1250-1270`); 53 audio effects and the transition catalogue are checked by their own tests (`docs/target-app-parity.md:51-55`).
- Blend modes: 27 entries including Normal (`BLEND_MODES`, `crates/project/src/effect.rs:144-172`).
- Keyframes: linear, Bezier, auto/continuous Bezier, hold, ease in/out; keyframable effect parameters and masks (`crates/project/src/keyframe.rs`, `crates/engine/src/masks.rs`).
- Compositing: wgpu GPU compositor (Metal/Vulkan/DX12/WebGPU) with a CPU reference renderer the GPU path is tested against (`crates/gpu/`, `docs/architecture.md` principle 5).
- **Approximate, not exact**: Warp Stabilizer is 2-D, Morph Cut has no face tracking, object masks (Premiere 26 AI) do not exist (`docs/gaps.md` G18, G12).

### Audio (implemented)

- Loudness meters to ITU-R BS.1770 / EBU R128 (momentary/short-term/integrated + true peak) and a reported agreement with ffmpeg's `ebur128` (`README.md:153`).
- Own DSP effects (EQ, filters, dynamics, limiter, delay, reverb, DeNoise, DeHummer, pitch shift), keyframable (`crates/audio-dsp`).
- Track Mixer / Clip Mixer, submixes, sends, five insert slots per track, Read/Latch/Touch/Write automation recorded during playback; everything scriptable (`mixer.*`, `clipMixer.*` — `docs/control-protocol.md:77-89`).
- Essential Sound panel (Dialogue/Music/SFX/Ambience, loudness auto-match, ducking that writes keyframes) via `essentialSound.*` (`crates/engine/src/essential_sound.rs`).
- Audio-clock playback (sound card is master) (`README.md:157`).
- Voice-over recording with punch-in (`crates/engine/src/voiceover.rs`; microphone usage string in the bundle's Info.plist).

### Titles, graphics, captions, transcripts (implemented, with one build caveat)

- Text engine (OpenType shaping, kerning, ligatures, bidi), Type/Shape/Pen tools, graphic clips, `.fcgt` graphics templates (`crates/text`, `crates/engine/src/graphics.rs`, `crates/engine/src/graphic_templates.rs`).
- Caption tracks in Subtitle / CEA-608 / CEA-708 / Teletext. Import and export **SRT, WebVTT, SCC, MCC, EBU STL, TTML/DFXP** frame-exactly, and **burn captions into exports** (`docs/captions.md`, `crates/captions/src/{srt,vtt,scc,mcc,stl,ttml,cea608,burn}.rs`).
- Text-based editing: `transcript.*` commands (generate, search, select, extract/lift, removeFillers, removePauses, createCaptions) — **but recognition itself needs a `whisper` build**; official releases are built without it, so `transcript.generate` returns "speech-to-text is not available in this build (built without the `whisper` feature); import a transcript with transcript.set instead" (`crates/engine/src/transcript.rs:61`, `packaging/macos/package.sh:61` builds with no `--features`).
- Text-to-speech narration: `tts.*` with built-in **Basic Female/Basic Male** formant voices (no download). Kokoro-82M neural voices need the `neural-voices` feature (off in releases) plus a 336 MB download (`crates/tts/README.md`, `apps/filmcraft/Cargo.toml`).
- Interface localisation: English + 11 catalogues (de, es, fr, id, it, ja, ko, pt-BR, ru, uk, zh-CN); uk/ru partial, errors/CLI stay English (`crates/ui-egui/README.md`, `crates/ui-egui/src/i18n/`).

### Import and open (implemented — exact lists)

- Extension lists are code, not docs: `STILL_EXTENSIONS`, `AUDIO_EXTENSIONS`, `VIDEO_EXTENSIONS` (`crates/media/src/lib.rs:175-179`).
- Openers registered in order: MP4/MOV, Matroska/WebM, MXF, Ogg, MPEG-TS/PS + MPEG-1/2 ES, APV, AVI, Y4M, standalone audio; then stills/animated images/WAV (`crates/codecs/src/lib.rs:135-137`, `:190-215`).
- Video codecs decoded: H.264, HEVC (Main/Main 10), VP8, VP9, AV1, ProRes, DNxHD/HR, MPEG-2/1, MJPEG, APV, uncompressed. Audio: AAC, AC-3/E-AC-3, Opus, Vorbis, MP1/MP2/MP3, FLAC, ALAC, PCM (`docs/codec-parity.md`, `crates/*/README.md`).
- Stills incl. EXR, DPX, Targa, DNG/CinemaDNG, Radiance HDR; animated GIF/APNG as clips (`crates/media/src/still/`, `crates/media/src/animated.rs`).
- Image sequences: `file.importImageSequence`, CLI `probe --image-sequence` (`crates/engine/src/image_sequence_tests.rs`, `apps/filmcraft-cli/src/probe.rs`).
- **AVI is implemented** (AVI 1.0 + OpenDML; MJPEG/H.264/HEVC/uncompressed + PCM/MP3/MP2/AC-3) — `crates/avi/README.md`, `crates/codecs/src/avi.rs:1-12`, `crates/engine/src/avi_import_tests.rs:36`. **Note the contradiction**: `docs/file-format-parity.md:47` still says "AVI … no (extension listed, no demuxer, #598)". Trust the code; treat that doc line as stale.

### Native project format and durability (implemented)

- `.fcproj` = UTF-8 JSON with `format: "filmcraft.project"` and an explicit `schema_version`, currently **13**; every version from 1 is migrated on load; newer files are refused, not half-read (`crates/format/src/lib.rs:66`, `docs/project-files.md:1-37`, `:79-86`).
- Media is referenced by path (never embedded); items carry a size+first/last-MiB identity fingerprint for relinking (`docs/project-files.md:254-259`).
- **Atomic saves** (temp file → fsync → rename → fsync dir) for projects, auto-saves, recovery snapshots and preferences (`docs/project-files.md:88-99`).
- Auto-save ring (`Auto-Save/<name>-<timestamp>.fcproj`, default every 5 min, 20 versions) **plus** a crash-recovery journal written ~1 s after each edit, restored after a crash with Recover/Not Now/Discard (`docs/project-files.md:113-173`).
- Offline media never blocks opening: missing files render an "MEDIA NOT FOUND" slate, audio is silent, and the Link Media dialog appears (`docs/project-files.md:261-316`).
- Proxies (ProRes Proxy/LT or H.264 presets), ingest (copy/transcode/createProxies), Project Manager collect/consolidate (`docs/project-files.md:318-409`).

### Export (implemented)

- Export formats are the `Format` enum (`crates/export/src/lib.rs:66-133`): H.264, HEVC (hardware only), AV1 (hardware only), ProRes, DNxHR, APV, MJPEG, PNG/TIFF/BMP/JPEG/Targa/DPX/EXR sequences, GIF, WAV, AIFF, AAC (`.m4a` or ADTS `.aac`), FLAC, MXF OP1a, MXF OP-Atom.
- ~44 built-in presets ("Match Source – Adaptive High Bitrate" default, YouTube/Vimeo/4K, ProRes family, DNxHR, APV, MXF, image sequences, GIF, audio-only) with user presets in `<data dir>/export-presets.json` (`crates/export/src/presets.rs:98-190`, `crates/engine/src/export_tools.rs:1-22`).
- Export queue as background jobs with progress/ETA/cancel; Quick Export (`export.queue.*`, `export.quick`, `jobs.list`, `jobs.cancel`).
- Options include `burnCaptions`, `captionSidecar: "srt"|"vtt"`, `alpha`, `exrCompression`, `loudnessLufs`, `sdr` (HDR→SDR tone map), `hardwareEncoding`, `range: entire|inOut|workArea|custom` (`crates/engine/src/commands.rs:1599-1607`).
- Offline media in an export is reported, not hidden: result lists `offlineMedia`, stderr names each item, exit status 1 unless `--allow-offline` (`apps/filmcraft-cli/src/main.rs:531-552`, `docs/agents.md:223-230`).

### Interchange (implemented; partly unvalidated)

- Import **and** export: CMX 3600 EDL, Final Cut Pro 7 XML (`xmeml`), FCPXML 1.9–1.11, OpenTimelineIO JSON, AAF (Edit Protocol, embedded/consolidated audio), OMF 2.0 (export), Avid Log Exchange (export) (`crates/interchange/src/lib.rs:1-12`, `:84-105`; commands `file.exportEdl`, `file.exportFcp7Xml`, `file.exportFcpxml`, `file.exportOtio`, `file.importAaf`, `file.exportAaf`, `file.exportOmf`, `file.exportAle`).
- Every importer returns a report of what could not be represented, and merges as one undoable step (`crates/interchange/src/lib.rs:12-17`).
- **Unvalidated in the wild**: AAF/OMF have never been opened in Media Composer/Pro Tools; FCP7 XML import of a Premiere sequence was measured at 97 s for 3 media files (`docs/gaps.md` G15).

### Automation surface (implemented)

- CLI `filmcraft-cli` with `exec`, `run`, `commands`, `describe`, `inspect`, `import`, `export`, `render`, `probe`, `bench-decode`, `mcp` (`apps/filmcraft-cli/src/main.rs:53-121`).
- Control channel: `filmcraft --control <port>` (or `FILMCRAFT_CONTROL_PORT`), JSON per line on 127.0.0.1 — engine commands, UI inspection (`ui.inspect`, `ui.elements`), synthetic input (`ui.click`, `ui.drag`, `ui.key`, `ui.type`), screenshots, `perf.stats` (`apps/filmcraft/src/control_server.rs`, `crates/ui-egui/src/control.rs`, `docs/control-protocol.md`).
- MCP server on stdio, headless or via `--bridge` to the running app; tools `command_list`, `command_run`, `command_batch`, `doc_inspect`, `render_preview`, `project_inspect`, `sequence_inspect`, `media_import`, `render_frame`, `ui_inspect`, `ui_elements`, `ui_click`, `ui_drag`, `ui_key`, `ui_type`, `ui_screenshot`, `ui_control`; resources `filmcraft://document`, `filmcraft://commands` (`crates/automation/src/server.rs:311-551`, `docs/agents.md:57-77`, `.mcp.json`).
- Command **id** convention: dotted and namespace-consistent (`file.*`, `timeline.*`, `sequence.*`, `clip.*`, `effects.*`, `lumetri.*`, `mixer.*`, `captions.*`, `transcript.*`, `markers.*`, `media.*`, `export.*`, `prefs.*`, `tool.*`, `window.*`). Enumerate with `filmcraft-cli commands [filter]` / `--json`; a single command with `filmcraft-cli describe <id>`.
- Web build exposes the same engine as JS promises: `window.filmcraft.{execute,request,commands,inspect,screenshot,importFiles,importUrl,openProject,files,readFile,info}` (`docs/web.md`).

## Known limitations and not-implemented

Do not assign these to FilmCraft; they are absent from the code.

- **`.prproj` cannot be opened or written** (`grep -ri prproj crates apps` finds nothing; `docs/gaps.md` G2). Import Premiere work through FCP7 XML, AAF or OTIO instead.
- **No plugin hosting**: no VST3/Audio Units, no OpenFX, no Premiere/AE plug-in APIs (`docs/gaps.md` G11).
- **Delivery codecs**: H.264 is the only software delivery encoder. H.265 export needs a hardware encoder (NVENC/VideoToolbox); there is **no HEVC or AV1 software encoder** and no AV1 export path at all (`crates/export/src/lib.rs:71-79`, `docs/gaps.md` G13). No MPEG-2/DVD/Blu-ray/DCP, no MP3 or WMV/FLV writes.
- **Camera RAW is DNG only**: no R3D, ARRIRAW, Sony RAW/X-OCN, Canon RAW, BRAW, ProRes RAW, JPEG 2000/XS MXF (`docs/file-format-parity.md`, `docs/gaps.md` G10).
- **10-bit / 4:2:2 camera H.264 and HEVC decode only through OS hardware**; Windows (Media Foundation) and Linux (VA-API/NVDEC) decline them with no software fallback (`docs/gaps.md` G3, `crates/platform/README.md`).
- **Stills that will not open**: PSD, HEIF/HEIC, AI/EPS, ICO; EXR only the listed compressions (no PIZ/B44/DWA/tiled/deep) (`docs/file-format-parity.md`).
- **No caption codecs embedded in the video stream** (CEA-608/708 in H.264 SEI or MXF) — burn-in and sidecar export only (`docs/file-format-parity.md`, captions table).
- **One project at a time.** `file.closeAllOtherProjects` exists only to report "only one project is open" (`crates/engine/src/project_tools.rs:90-92`). Sequences, however, open in Timeline tabs.
- **Speech to text is off in official builds** (`docs/gaps.md` G19); the Text panel's Transcript tab can still import a transcript via `transcript.set`.
- **Kokoro neural TTS voices are off in official builds** (`neural-voices` feature); only the formant voices ship.
- **Export destinations beyond "Media File" do not exist.** The README screenshot alt text (README.md:197) advertises YouTube, Vimeo, TikTok, Instagram and FTP destinations; the code has exactly one destination, `export.destination.mediaFile` (`crates/ui-egui/src/panels/export_mode.rs:204`). "YouTube 1080p Full HD" etc. are **presets**, not upload destinations.
- **AI features are minimal**: no Object Mask, no Generative Extend, no media-intelligence search, no caption translation, no model-based Enhance Speech (`docs/gaps.md` G12).
- **UI fidelity gaps** (`docs/gaps.md` G8): no on-monitor transform handles for Motion, no filmstrip thumbnails, no marquee selection in the Project panel, Effect Controls lacks keyframe zoom/row lines, transition editing controls limited.
- **Windows and Linux are far less tested than macOS**; open reports include Linux playback stutter and Wayland/menu issues (`docs/gaps.md` G9).
- **Performance**: Lumetri, keys and export rendering run on the CPU; GPU compositing is partial (`README.md:294`).
- No work area bar; no Productions; no Production or Search panels; Effect Controls has no effect-selection state (`docs/keyboard.md:46-64`).
- **Claimed but unverified in code**: "more than 650 engine commands" (README.md:226). Static counting finds ~200 `cmd!`/`query!` registrations plus several hundred `spec(...)` registrations across `crates/engine/src/*`; the exact number is uncertain — use `filmcraft-cli commands` on a built binary.
- **Documented contradiction**: `docs/file-format-parity.md:47` says AVI has no demuxer while `crates/avi` and `crates/codecs/src/avi.rs` implement one (see above). Verify against your installed version before repeating either statement.

## How to operate

**Launch (macOS).** `open -a FilmCraft` or `open -a FilmCraft "/path/to/edit.fcproj"`. Binary: `/Applications/FilmCraft.app/Contents/MacOS/FilmCraft`. Bundle id `ai.storyteller.filmcraft`, version 0.9.0 (`Contents/Info.plist`). A `.fcproj` handed to the app opens as a project; any other file argument is imported as media; the extension match is case-insensitive, so `CUT.FCPROJ` works (`apps/filmcraft/src/args.rs:120-141`).

**Desktop flags** (abridged from the real `USAGE` string in `apps/filmcraft/src/args.rs:7-26`; every flag below is accepted, and an unknown option is an error, not a file name):

```
filmcraft [options] [project.fcproj | media files...]
  --control <port>      localhost JSON-lines control server   (FILMCRAFT_CONTROL_PORT)
  --control-input-only  accept widget input only from the control server (needs --control)
  --demo | --empty      demo project or empty project
  --recover | --no-recover
  --data-dir <dir>      auto-save, crash recovery and logs    (FILMCRAFT_DATA_DIR)
  --graphics <mode>     default | dx12 (Windows) | software (Windows, Linux)
  --version             print version   -h/--help  print help
```

Unknown options are **errors** (exit 2), not file names. The app opens without stealing focus when started with `--control` (`docs/control-protocol.md:54-58`).

**Data directory (macOS):** `~/Library/Application Support/FilmCraft` — holds `preferences.json`, `Auto-Save/`, `Recovery/`, `Logs/filmcraft.log`, `Media Cache/`, user export and effect presets (`docs/project-files.md:141`, `:170-173`, `:236`).

**The CLI is not inside the .app.** On macOS `filmcraft-cli` ships as a separate release asset (`filmcraft-cli-<version>-macos-<arch>.zip`) — `docs/agents.md:40-55` — or build it: `cargo run --release -p filmcraft-cli -- commands`. On Windows it is installed next to the app, on Linux at `/usr/bin/filmcraft-cli`. It is not on `PATH` on macOS by default.

**CLI shape** (full reference: `references/cli-and-protocol.md`):

```sh
filmcraft-cli commands razor                    # find command ids
filmcraft-cli describe timeline.razor           # one command: menu, shortcut, params, enabled now
filmcraft-cli --demo inspect sequence           # project/sequence as JSON, no window
filmcraft-cli --project p.fcproj --save exec timeline.razor seconds=3.5
filmcraft-cli --project p.fcproj --save import a.mov b.wav
filmcraft-cli --project p.fcproj export out.mp4 --preset "YouTube 1080p Full HD" --start 0 --end 10
filmcraft-cli export --list-presets prores
filmcraft-cli --project p.fcproj render --seconds 2.5 --out frame.png
filmcraft-cli --bridge 127.0.0.1:9876 exec window.workspace.color   # drive the running app
filmcraft-cli mcp --demo                                            # MCP on stdio, headless
```

Values are parsed as JSON when they can be (`3.5`, `true`, `[1,2]`), else strings; dotted keys nest (`color.r=1`). Exit status: 0 success, 1 a command failed or offline media was drawn without `--allow-offline`, 2 usage error. `--save` writes back to `--project`; `--save-as` elsewhere; in `--bridge` mode saving happens in the app.

**Document model.** One project per running app; sequences are the timelines and open in Timeline tabs (multiple sequences can be open at once — `file.close` closes the active sequence, `view.open_sequences` persists them; `docs/project-files.md:23-30`). Panels dock/float; 28 panel kinds; workspaces are named layouts.

**Core workflow.** Import media (`File ▸ Import`, ⌘I, or the CLI/`media_import`) → build a sequence (`file.newSequence`, 3 video / 3 audio tracks by default) → edit on the timeline (tools `V/A/Shift+A/B/N/R/C/Y/U/P/H/Z/T`) → save `.fcproj` (⌘S; ⇧⌘S Save As; ⌥⌘S Save a Copy) → export (`File ▸ Export ▸ Media…` or `export.quick`). Key ids: `Cmd+Z`/`Cmd+Shift+Z` undo/redo, `Cmd+K` Add Edit, `Cmd+,` Settings, `⌥⌘K` Keyboard Shortcuts, `⌘⌥A` add caption track, `⌘⌥C` add caption at playhead, `⌥⇧1..6` workspaces.

**Time.** Ticks everywhere: 254 016 000 000 per second. Commands accept `ticks`, `seconds`, `frame` or `timecode`.

## Working with an AI agent

Legitimate and effective:

- **Headless round trips** with `filmcraft-cli` (no window, no GUI state): import → edit via `exec`/`run` → `export` → verify. Use `filmcraft-cli run script.jsonl` for multi-step edits; each line is `{"id": ..., "params": {...}}`, `#` comments allowed, `--keep-going` continues past failures (`apps/filmcraft-cli/src/main.rs:347-374`).
- **Drive the live app** through `--control <port>` or `filmcraft-cli mcp --bridge 127.0.0.1:9876`: run commands, inspect `ui.elements` for automation ids (`timeline.clip.<id>`, `tools.Razor`, `program.transport.playback.toggle`, …), click/drag/type, screenshot the window or one panel, then `edit.undo` if wrong. Element ids come from the previously rendered frame; after a layout change retry on the next frame (`docs/agents.md:186`).
- **Enumerate before you guess**: never invent command ids, parameter names or shortcuts. `commands`, `describe <id>`, and the `command_list` MCP tool are authoritative; `enabled`/enablement reasons come back with each command.
- **Prepare and convert inputs**: generate test media with ffmpeg and hand it to FilmCraft (ffmpeg is allowed as an external tool/oracle — it is never linked into the app, `AGENTS.md` §2); convert unsupported sources (`.prproj`, WMV, HEIC, PSD, R3D…) into something FilmCraft reads: FCP7 XML/AAF/OTIO for timelines, ProRes/H.264 MP4 or image sequences for media.
- **Interpret and repair project files**: `.fcproj` is documented JSON (`docs/project-files.md`) with a migration chain and atomic writes — you can read it, diff it, and reason about it. Repair by relinking media through commands (`media.findMissing`, `media.relink`, `media.autoRelink`, `media.search`), not by editing paths by hand while the app has the project open.
- **Verify exports outside the app**: `ffprobe`/`ffmpeg -i` for streams, duration, frame count, A/V sync; check exit status, the `offlineMedia` array, and the written path (the format may change the extension: `out.mp4` exported as APV becomes `out.mp4.mov` — `apps/filmcraft-cli/src/main.rs:500-516`).
- **Batch production**: `export.queue.add … start=true wait=true` for several deliverables; `jobs.list` for progress/ETA; `jobs.cancel` to stop.

Must not attempt:

- Do not assume `.prproj`, Premiere projects, plugins, YouTube/FTP upload destinations, Whisper transcription or Kokoro voices exist in the installed build.
- Do not drive the GUI "blind": always read `ui.elements`/`ui.inspect` before clicking by id, and take a screenshot to confirm. The window may stay behind other windows (by design).
- Do not leave the control port open when idle: it is **loopback-only but has no authentication**, and 16 connections are served at once (`docs/control-protocol.md:9-17`). A non-JSON line closes that connection by design.
- Do not hand-edit a `.fcproj` to look like a newer schema or copy a `schema_version` forward; older builds refuse newer files, and corrupted fields become "a damaged file" errors (`docs/project-files.md:31-37`, `:79-86`).
- Do not expect the headless MCP server to be sandboxed: it can read and write wherever the user can; there are no confinement flags (`docs/agents.md:17-19`).
- Do not commit screenshots of Adobe products or use Adobe artwork when producing documentation assets (repo rule `AGENTS.md` §1); FilmCraft-only screenshots with openly licensed media.

## Verification protocol

FilmCraft is alpha and explicitly estimates itself "~56% ready for real work". Assume every step can silently produce a wrong-but-valid file:

1. **Throwaway round trip first.** New project → import one clip → place → `file.exportMedia` (or `filmcraft-cli export`) → `ffprobe` the output → reopen the project in a second process (`filmcraft-cli --project …` or `file.open`) and check the sequence inspect matches. Only then touch real work.
2. **Never trust a silent export.** Check the exit status, the `offlineMedia` list and the message naming the written files. `filmcraft-cli export` exits 1 when it drew placeholder frames for offline media unless you passed `--allow-offline`; an export that "succeeded" may still contain a red "MEDIA NOT FOUND" slate (`apps/filmcraft-cli/src/main.rs:531-552`).
3. **Read the result as media, not as a file.** Check duration, frame count, frame rate, audio channels and a couple of decoded frames; H.264/AAC output from FilmCraft's own encoders decodes in ffmpeg (README claims no warnings) but do not take that on faith for a deliverable.
4. **Version and back up per session.** Keep the previous `.fcproj` before a bulk edit — auto-save (`Auto-Save/`) and the recovery journal are safety nets, not backups. `file.saveAs` / `file.saveCopy` before risky operations.
5. **Mind the schema.** A project saved by a newer build cannot be opened by an older one (it is refused). Update apps only *between* projects, and keep the `<name> (schema vN backup).fcproj` the first save-over creates.
6. **Do not trust parity docs over the code.** They drift (the AVI entry is already stale). When a doc and the code disagree, the code in this repo wins; when both are silent, write "uncertain" and test.
7. **Record the exact build** you tested (version + commit, e.g. 0.9.0 / `4a69a038…`) — bug reports with real footage and a build id are what the project asks for.

## Sources & evidence

- Repo: https://github.com/storytold/filmcraft — inspected at **tag v0.9.0, commit `4a69a038d32761f604b3c7e4845b21fb40b3cbe4`** (`git rev-parse HEAD`), 2026-10-18. Same commit as the installed `/Applications/FilmCraft.app` (`FilmCraftBuildCommit` in its Info.plist), so no "installed build may be older" caveat applies to this skill.
- Files read: `README.md`, `Cargo.toml`, `AGENTS.md`, `CLAUDE.md`, `ROADMAP.md`, `.mcp.json`, `apps/filmcraft/Cargo.toml`, `apps/filmcraft/src/{args.rs,main.rs,file_filters.rs,native_menu.rs}`, `apps/filmcraft-cli/{Cargo.toml,src/args.rs,src/main.rs,src/probe.rs}`, `apps/filmcraft-web/Cargo.toml`, `docs/{agents,control-protocol,project-files,architecture,keyboard,gaps,target-app-parity,file-format-parity,captions,transcripts,web}.md`, `crates/engine/src/{commands.rs,project_tools.rs,transcript.rs,marker_export.rs,export_tools.rs,shortcuts.rs,shortcut_presets.rs}`, `crates/export/src/{lib.rs,presets.rs}`, `crates/interchange/src/lib.rs`, `crates/media/src/lib.rs`, `crates/codecs/src/{lib.rs,avi.rs}`, `crates/avi/README.md`, `crates/format/src/lib.rs`, `crates/project/src/effect.rs`, `crates/project/src/effect/vfx.rs`, `crates/captions/src/*`, `crates/platform/README.md`, `crates/tts/README.md`, `crates/speech/README.md`, `crates/ui-egui/README.md`, `crates/ui-egui/src/{menus.rs,dock.rs,control.rs}`, `crates/ui-egui/src/panels/export_mode.rs`, `crates/automation/src/server.rs`, `packaging/{env.sh,macos/package.sh}`, `/Applications/FilmCraft.app/Contents/Info.plist`.
- Shared library consulted: `storytold/craft-libs` (`docpath` — the stored-path policy FilmCraft uses via `craft-docpath`, `crates/engine/src/doc_path.rs`; `ui` — shared egui docking/theme components).
- See `evidence.md` in this directory for the claim → evidence table, and `references/` for the CLI/control-channel reference and the format tables.
