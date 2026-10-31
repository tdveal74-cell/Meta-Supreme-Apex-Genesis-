# FilmCraft — evidence table (for orchestrator review)

App: **FilmCraft**, repo `storytold/filmcraft`, inspected at **tag v0.9.0 / commit `4a69a038d32761f604b3c7e4845b21fb40b3cbe4`**
(`git rev-parse HEAD`), date **2026-10-18**. The installed `/Applications/FilmCraft.app` reports the same commit
(`Contents/Info.plist → FilmCraftBuildCommit = 4a69a038d32761f604b3c7e4845b21fb40b3cbe4`, version 0.9.0), so the
installed build is the inspected build. Paths below are repo-relative.

| # | Claim in SKILL.md | Evidence | Tier |
|---|---|---|---|
| 1 | Clean-room reimplementation of Premiere Pro; pure Rust; no FFmpeg inside | `README.md:14`, `README.md:69`, `README.md:170`; `AGENTS.md` §2; `ffmpeg` only as an external test oracle (`crates/testkit`) | implemented |
| 2 | Headless engine; every feature is a command; CLI + control channel + MCP drive the same ids | `docs/architecture.md:1-19` (design principles), `crates/engine/src/commands.rs` (`command_specs`, `build()` at :1137), `crates/ui-egui/src/menus.rs`, `apps/filmcraft-cli/src/main.rs` | implemented |
| 3 | Desktop flags `--control/--control-input-only/--demo/--empty/--recover/--no-recover/--data-dir/--graphics/--version/-h` | `apps/filmcraft/src/args.rs:7-26` (`USAGE`), parser at `:63-119`; tests `:174-324` | implemented |
| 4 | CLI subcommands `exec/run/commands/describe/inspect/import/export/render/probe/bench-decode/mcp` + options | `apps/filmcraft-cli/src/main.rs:53-121` (`HELP`), dispatch `:282-497`; parser `apps/filmcraft-cli/src/args.rs` | implemented |
| 5 | Export format list (h264, hevc*, av1*, prores, dnxhr, apv, mjpeg, png/tiff/bmp/jpg/tga/dpx/exr, gif, wav, aiff, aac, flac, mxf-op1a, mxf-opatom) | `crates/export/src/lib.rs:66-133` (`enum Format`), `:134-165` (`from_name`/`id`) | implemented (`hevc`/`av1` = hardware-gated: `Format::available`, `register_encoder`) |
| 6 | ~44 built-in export presets incl. ProRes family, DNxHR, MXF, image sequences, audio-only | `crates/export/src/presets.rs:97-190` (`builtin_presets`), finding by name `:193` | implemented |
| 7 | Export queue, quick export, jobs with progress/ETA/cancel | `crates/engine/src/export_tools.rs:1-22` (module doc lists `export.queue.*`, `export.quick`), `jobs.list`/`jobs.cancel` in `crates/engine/src/commands.rs:1608-1620` | implemented |
| 8 | Import extension lists (stills/audio/video) | `crates/media/src/lib.rs:175-179`; `is_importable` `:181-184` | implemented |
| 9 | Containers/codecs decoded (MP4/MOV, MKV/WebM, MXF, Ogg, MPEG-TS/PS, AVI, Y4M, stills, audio) | `crates/codecs/src/lib.rs:135-137` (`openers()`), `:190-215` (stills/animated/WAV fallbacks), `crates/avi/README.md`, `crates/codecs/src/avi.rs:1-12` | implemented — **contradicted by `docs/file-format-parity.md:47`** which still says AVI has no demuxer (see note 1) |
| 10 | `.fcproj` = UTF-8 JSON, `schema_version` 13, migrations from v1, newer files refused | `crates/format/src/lib.rs:66` (`SCHEMA_VERSION = MIGRATIONS.len()+1`), `:103`, `:166`, `:205`; `docs/project-files.md:8-86` | implemented |
| 11 | Atomic saves; auto-save ring; crash-recovery journal restored after a crash | `crates/format/src/atomic.rs`, `crates/format/src/autosave.rs`, `docs/project-files.md:88-99`, `:113-173` | implemented |
| 12 | Offline media renders a "MEDIA NOT FOUND" slate instead of failing the open; relink/proxy/ingest commands | `crates/render/src/offline.rs`, `crates/engine/src/relink.rs:606+`, `crates/engine/src/proxies.rs:498+`, `docs/project-files.md:261-409` | implemented |
| 13 | Interchange import+export: EDL, FCP7 XML, FCPXML 1.9–1.11, OTIO, AAF, OMF, ALE | `crates/interchange/src/lib.rs:1-12` (module doc), `:84-130` (names/extensions/detect), `crates/engine/src/aaf_omf.rs:390,423`; command ids in `crates/engine/src/project_tools.rs:233` | implemented; AAF/OMF **never validated in Avid/Pro Tools** (`docs/gaps.md` G15) |
| 14 | Captions: SRT/VTT/SCC/MCC/STL/TTML read+write, burn-in, caption tracks CEA-608/708/Teletext | `crates/captions/src/{srt,vtt,scc,mcc,stl,ttml,cea608,burn}.rs`; `crates/engine/src/captions.rs:491-509` (`captions.import`/`captions.export` params); `docs/captions.md` | implemented |
| 15 | 93 video effects in 16 folders; 53 audio effects; transitions catalogue | test `premiere_26_video_effects_catalogue` asserts `n == 93` and 16 folders (`crates/project/src/effect/vfx.rs:1250-1270`); `premiere_audio_set_is_complete_and_foldered` (`crates/project/src/effect/audio.rs`); `premiere_26_transition_tree` (`crates/project/src/vtransition.rs:413`); `docs/target-app-parity.md:51-55` | implemented |
| 16 | 27 blend modes | `crates/project/src/effect.rs:144-172` (`BLEND_MODES`, includes "Normal") | implemented |
| 17 | Keyboard presets: FilmCraft Default, Premiere Pro Compatible, Final Cut Pro, Avid | `crates/engine/src/shortcuts.rs:59-63`, `crates/engine/src/shortcut_presets.rs` (`PREMIERE`, `FINAL_CUT`, `AVID`); parity notes `docs/keyboard.md` | implemented |
| 18 | Workspaces Editing/Assembly/Color/Effects/Audio/Captions and Graphics/All Panels; 28 panel kinds | `crates/ui-egui/src/menus.rs:110-120`, `crates/ui-egui/src/dock.rs:14-46` | implemented |
| 19 | Control channel methods (engine.execute, ui.*, perf.stats) and MCP tool set | `docs/control-protocol.md:24-43`, `crates/ui-egui/src/control.rs:103+`, `crates/automation/src/server.rs:311-551`, `docs/agents.md:57-77`, `.mcp.json` | implemented |
| 20 | GPU compositor (wgpu) with CPU reference path; trim mode/dynamic trimming; multicam | `crates/gpu/` (`composite.wgsl`, `export_renderer.rs`), `docs/architecture.md` principle 5; `crates/engine/src/trim.rs`, `docs/control-protocol.md:126-130`; `crates/engine/src/multicam.rs` | implemented |
| 21 | Web/WASM build and its JS API | `apps/filmcraft-web/` (`Cargo.toml` wasm-only deps), `docs/web.md` (`window.filmcraft` table), `cargo xtask web` | implemented (single-threaded; export/preview limitations listed in `docs/web.md`) |
| 22 | Loudness meters to BS.1770/EBU R128 agreed with ffmpeg `ebur128`; audio-clock playback | `README.md:153`, `README.md:157`; `crates/audio-dsp` (meter tests), `crates/engine/src/mixer.rs` | implemented (authors' measurement; not re-run here) |
| 23 | Speech-to-text, neural TTS, Whisper unavailable in shipped builds | `apps/filmcraft/Cargo.toml` (`features: default = []`, `whisper`, `neural-voices`), `apps/filmcraft-cli/Cargo.toml` (`whisper`), `packaging/macos/package.sh:61` (`cargo build --release … ` with no `--features`), `crates/engine/src/transcript.rs:61` (explicit error string), `docs/gaps.md` G19 | implemented-as-gated / **not in releases** |
| 24 | `.prproj` cannot be opened or written | `grep -ri prproj crates apps` → no matches; `docs/gaps.md` G2; `docs/file-format-parity.md` project table | not implemented (roadmap) |
| 25 | No plugin hosting (VST3/AU/OpenFX) | `docs/gaps.md` G11; Settings ▸ Plugins is a stub (`docs/project-files.md:239`) | not implemented |
| 26 | No HEVC/AV1 software export; camera RAW other than DNG unsupported; 10-bit 4:2:2 needs hardware | `crates/export/src/lib.rs:71-83` (doc comments), `docs/gaps.md` G3/G10/G13, `docs/file-format-parity.md` stills table | not implemented |
| 27 | One project per app instance | `crates/engine/src/project_tools.rs:88-92` (`file.closeAllOtherProjects` returns "only one project is open"; its test at `crates/engine/src/project_tools_tests.rs:170-171`) | implemented (deliberate limit) |
| 28 | YouTube/Vimeo/TikTok/Instagram/FTP export **destinations** shown in the README image do not exist in code | `README.md:197` (image alt text only); `grep -rn 'TikTok\|Instagram' crates apps` → README only; `crates/ui-egui/src/panels/export_mode.rs:204` registers the single destination `export.destination.mediaFile` | claimed (docs) / **not implemented** |
| 29 | "more than 650 engine commands" | `README.md:226`; static count: 203 `cmd!` + 16 `query!` in `crates/engine/src/*.rs` plus hundreds of `spec(...)` registrations assembled by `build()` (`crates/engine/src/commands.rs:1137-3428`); the only assertion in code is `> 90` (`crates/engine/src/tests.rs:618`) | claimed — exact count uncertain, enumerate with `filmcraft-cli commands` |
| 30 | macOS installer ships only the GUI; `filmcraft-cli` is a separate asset | `ls /Applications/FilmCraft.app/Contents` (only `MacOS/FilmCraft`, `Resources/{FilmCraft.icns, OFL-*.txt}`); `docs/agents.md:40-55`; `packaging/macos/package.sh` builds an app dmg and a separate `filmcraft-cli-…zip` | implemented (packaging) |

## Notes the orchestrator should spot-check

1. **Doc drift (AVI).** `docs/file-format-parity.md:47` says AVI has no demuxer; the code has a full clean-room
   demuxer plus a codec source and an engine import test (`crates/avi/README.md`, `crates/codecs/src/avi.rs`,
   `crates/engine/src/avi_import_tests.rs:36`). The README's own codec table also lists AVI as read. The skill
   flags this contradiction rather than picking a side silently.
2. **README image vs code (export destinations).** The v0.9.0 README screenshot advertises five delivery
   destinations that do not exist in the code; the presets with those names (e.g. "YouTube 1080p Full HD") are
   encoding presets, not upload targets.
3. **Feature gating.** Both automation-ish AI features (`whisper`, `neural-voices`) are off by default and the
   release packaging passes no `--features`, which is why the skill tells an agent not to promise transcription
   from the installed app.
4. **Verification depth.** The project's own readiness estimate is "~56%"; the parity docs state no automated
   fidelity comparison against Premiere exists yet (`docs/gaps.md` G1). The skill's Verification protocol is
   written for that reality.
5. **Nothing was executed.** The repo was read-only for this task (no build, no app launch); all claims are
   static-code evidence plus the bundle's `Info.plist`. Runtime numbers quoted (fps, PSNR, MB/s) are attributed
   to the repo's own measurements, not re-measured here.

## How to re-verify quickly

```sh
cd <filmcraft checkout>            # at 4a69a038d32761f604b3c7e4845b21fb40b3cbe4
git rev-parse HEAD
sed -n '175,179p' crates/media/src/lib.rs            # import extension lists
sed -n '66,133p' crates/export/src/lib.rs            # export formats
sed -n '7,26p' apps/filmcraft/src/args.rs            # desktop flags (USAGE)
grep -n 'n, 93' crates/project/src/effect/vfx.rs     # the 93-effect assertion
/usr/libexec/PlistBuddy -c 'Print FilmCraftBuildCommit' /Applications/FilmCraft.app/Contents/Info.plist
```
