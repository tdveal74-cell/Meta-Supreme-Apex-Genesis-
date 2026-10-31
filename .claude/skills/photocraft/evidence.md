# PhotoCraft — evidence table for SKILL.md

App: PhotoCraft · repo `storytold/photocraft` · inspected at tag **v0.10.0**, commit **8407d9ccb125af52944fca9d228383459f94aaef** (2026-10-17) · date 2026-10-18.
Installed bundle `/Applications/PhotoCraft.app` reports 0.10.0 (`Contents/Info.plist`) — the checkout matches the shipped release.
Method: static reading of the repo (no build, no GUI launch); every row below is a file I opened and read unless marked otherwise. Status: **implemented** = code path exists and is wired; **partial** = exists with named gaps; **claimed** = prose/docs only, not confirmed in code; **not implemented** = absent and documented as such.

## Capability claims (20)

| # | Claim in SKILL.md | Evidence (repo-relative) | Status |
|---|---|---|---|
| 1 | Clean-room Photoshop reimplementation, pure Rust (MIT/Apache-2.0, org `storytold`); native egui/eframe+wgpu, and the same code builds for WebAssembly | `README.md:13-16,428-429`; `AGENTS.md`; `Cargo.toml` (`wasm-release` profile); `apps/photocraft-web/` | implemented |
| 2 | Early alpha: ~76% feature breadth, ~45% "ready for real work", 953 open issues (last measure) | `ROADMAP.md:3-47`, `docs/target-app-parity.md` | claimed (dated estimates; docs lag code) |
| 3 | 67 tools; Art History Brush missing (1 of Photoshop's 68) | `crates/ui-egui/src/state.rs:141-209` (`pub const ALL: [Tool; 67]`); `docs/gaps.md` G6 | implemented / partial |
| 4 | 16 adjustment-layer commands (`layer.newAdjustmentLayer.*`) | grep of `crates/engine/src/` yields exactly 16 ids | implemented |
| 5 | 10 layer-effect kinds, several instances per kind | `crates/doc/src/effects.rs:261-293` (`pub enum Effect`); blend modes: `crates/color/src/blend.rs:13-46` (PassThrough + 27 Photoshop + 6 Paint.NET) | implemented |
| 6 | Layers, groups, clipping, pixel/vector masks, fill layers, smart objects + smart filters, alpha channels, Quick Mask, comps, artboards | `README.md:188-191`; `crates/doc/src/`; `crates/engine/src/` | implemented (some rows partial — `docs/scorecard.md` FILE-215-*, e.g. FILE-215-3 smart-filter mask painting missing) |
| 7 | Type on a path is implemented (`type.attachToPath`/`type.detachFromPath`) even though older docs say it is missing | `crates/engine/src/type_extra_cmds.rs:695-703` | implemented — docs drift; code wins |
| 8 | `.pcraft` native format: zip or directory, `manifest.json` v1 + BLAKE3/zstd content-addressed tiles/blobs + previews; incremental/atomic saves; crash-recovery autosaves | `crates/format/src/lib.rs:3-19,50`; `crates/format/src/manifest.rs:18`; `crates/format/src/autosave.rs` | implemented |
| 9 | PSD/PSB read **and** write (layers, effects, text, smart objects, alpha channels) | `crates/io/src/lib.rs:1-27,418-446`; `psd_import.rs`, `psd_export.rs`; `crates/psd` | implemented |
| 10 | PSD fidelity is the blocking gap: floors 188/256 Photoshop oracles, 249/309 psd-tools, 148/170 io corpus; re-saved PSD not byte-identical; no third-party re-open test | `crates/io/tests/corpus.rs:151-159`; `docs/scorecard.md` File compatibility; `README.md:217`; scorecard FILE-216-4 "missing" | partial (G1 blocks beta) |
| 11 | Flat codecs read+write: PNG 8/16, JPEG, TIFF 8/16/32f+BigTIFF, WebP (lossless + own lossy VP8), GIF, BMP, TGA, ICO, Netpbm, QOI, OpenEXR, HDR, FITS, DPX 8/10/12/16 | `crates/codecs/README.md` capability matrix; dispatch `crates/io/src/lib.rs:447-451` | implemented |
| 12 | Read-only imports: PDN3, Krita `.kra/.krz`, Affinity `.af*`, DDS, Cineon, HEIC (feature `heif`), SVG as shape layers; layered TIFF write leaves extra alpha channels/Quick Mask out | `crates/io/src/lib.rs:1-25,392-400`; `crates/codecs/README.md`; `docs/scorecard.md` FILE-215-7 | implemented (import-only writers refuse with a naming error) |
| 13 | Camera raw: DNG (incl. lossy-JPEG), CR2, NEF/ARW/PEF, Nikon compressed NEF, Sony cRAW, RW2, uncompressed ORF/RAF; CR3 sensor data no (preview + orientation only) | `crates/raw/src/lib.rs:31-37,89-98,241`; `crates/raw/src/cr3.rs:1-3`; `crates/raw/tests/dng.rs` `lossy_jpeg_*` | partial (per-variant limits, embedded-preview fallback) |
| 14 | PDF write only: one flattened RGB/Gray/CMYK page with ICC; no PDF import | `crates/io/src/pdf.rs:8`; `docs/file-format-parity.md` FILE-215-10 | partial |
| 15 | Export As = png/jpg/webp/tif/tga/ico; Save for Web = gif/png8/png24/jpeg/wbmp; Quick Export as PNG | `crates/engine/src/export_preset_cmds.rs:13`; `crates/engine/src/web_cmds.rs:46-59`; `crates/engine/src/shell_commands.rs` | implemented |
| 16 | Every Photoshop menu item wired — 631/631 live, `FLOOR = 631` — but wiring ≠ behaviour | `crates/ui-egui/src/parity.rs:10`; `docs/parity-checklist.md` | implemented (wiring only; docs say so) |
| 17 | CLI: 8 subcommands (convert/info/run/batch/droplet/commands/mcp/serve); strict flag parsing; exit 0/1/2 | `apps/photocraft-cli/src/lib.rs:14-203` (`USAGE`, `SUBCOMMANDS`, `parse`, `run`) | implemented |
| 18 | Control channel: loopback-only JSON lines, token auth on the first frame, 60 s timeout; automation refuses ambient filesystem commands (`file.open/save/saveAs/saveACopy`, `pattern.import`, smart-object file ops, `edit.colorSettings`, …) | `docs/control-protocol.md`; `apps/photocraft/src/control_server.rs`; `crates/automation/src/workspace.rs:683-702` (`filesystem_commands_fail_closed`) | implemented |
| 19 | MCP headless or bridged; tools `command_list/command_run/command_batch/doc_inspect/render_preview/ui_inspect/ui_screenshot`; no filesystem authority without roots | `docs/mcp.md`; `crates/automation/src/headless.rs`; `crates/automation/tests/agent_tasks.rs` (header: 10 MCP tasks) + `agent_tasks_more.rs` | implemented |
| 20 | No AI/generative features; no native `.8BF`/CEP/UXP host — only the Wasm plug-in ABI v1 (`plugin.*`, wasmi sandbox) | no `ml` crate in `crates/`; `docs/roadmap.md` M10 "ML backend not started"; `crates/ui-egui/src/panels.rs:1309` "Generative Expand is not offered"; `docs/plugins.md` | not implemented (AI, native plug-ins) / implemented (Wasm ABI) |

## Operational facts used in "How to operate"

| Fact | Evidence |
|---|---|
| App options `--control`, `--control-token[-file]`, `--automation-*-root`, `--safe-gpu`, `--new-instance`, `--present-mode`, …; env equivalents; bad values are usage errors (exit 2) | `apps/photocraft/src/main.rs:3-31,168-198` |
| The `.app` bundle contains no CLI (only `Contents/MacOS/PhotoCraft`); macOS CLI ships as `photocraft-cli-<ver>-macos-universal.zip` | `ls /Applications/PhotoCraft.app/Contents/MacOS`; `README.md:284-290` |
| Bundle registers `.pcraft` (`ai.storyteller.photocraft.document`), min macOS 11.0, version 0.10.0 | `/Applications/PhotoCraft.app/Contents/Info.plist` (`PlistBuddy`) |
| Documents are tabs in one window (`window.document.<index>`); second launches on Win/Linux hand files to the running instance; `--control`/`--new-instance` start a separate process | `docs/control-protocol.md`; `apps/photocraft/src/main.rs:13-15` |
| Settings dir `~/Library/Application Support/Photocraft/` (`preferences.json`, `Presets/`, `Recovery/`, `ui.ron`); `PHOTOCRAFT_CONFIG_DIR`; portable mode `PhotoCraftData/` | `apps/photocraft/src/app_dirs.rs:1-23,461-470`; `apps/photocraft/src/services.rs:274-280` |
| Autosave default 10 min, preference `fileHandling.autosaveMinutes` 1–240; recovery entries `<key>.pcraft` + `<key>.json`, deleted only on save/close | `crates/engine/src/prefs.rs:439-470,1108`; `crates/format/src/autosave.rs` |
| Shortcuts `Cmd+F` Search…, `Cmd+J` Layer via Copy, `Cmd+D` Deselect, `Cmd+O/S/Shift+S`, `Cmd+Alt+Shift+W` Export As, `F5/F6/F7`; `.kys` import/export via `edit.keyboardShortcuts` | `crates/engine/src/shell_commands.rs:16-60`; `crates/ui-egui/src/menu_catalog.rs:17,91,257,507`; `crates/automation/src/workspace.rs:719-724` |
| Performance shortfall: 3 of 58 scenarios within budget, 22 over budget/failing (P12 crash at 150 layers); 26 of 168 preferences do nothing | `docs/scorecard.md` Performance + Workspace summaries (baseline 2026-10-05) |
| Print = one flattened PDF page via `lp`/CUPS-IPP/portal (`file.print`, `file.printOneCopy`) | `docs/printing.md` |
| Wasm plug-in limits (no WASI/FS/net, 32 MiB module, 512 MiB memory, 50M fuel, 60 s) | `docs/plugins.md` |
| Timeline/video early (`timeline.create`, `file.export.renderVideo` = PNG sequence/GIF) | `crates/engine/src/timeline_cmds.rs:137`; `video_cmds.rs:406`; `docs/roadmap.md` M12 "HDR, timeline pending" |
| MCP `command_batch` is not atomic; `image.duplicate`/`history.newDocument` create safe working copies; automation saves never fire script events | `docs/mcp.md`; `docs/control-protocol.md` |

## Verification notes and honest gaps

- **Docs vs code drift.** `ROADMAP.md`/`docs/roadmap.md` carry measurements predating v0.10.0 and still list pre-release states (e.g. "no type on a path", `docs/scorecard.md` FILE-215-11 "lossy DNG unsupported"). Code at HEAD contradicts them (`type_extra_cmds.rs:695`; `crates/raw/tests/dng.rs:739`). SKILL.md follows the code and flags the drift rather than repeating stale docs.
- **PSD oracle counts.** `crates/io/tests/corpus.rs` gives `corpus/photoshop`: 256 files, pass floor 188, round-trip floor 258 — the round-trip unit differs from the file count; SKILL.md repeats the numbers as the code states them without reinterpreting them.
- **Command count.** `docs/parity-checklist.md` proves 631/631 Photoshop menu items are wired, but I did not count every registry id at HEAD (286 `CommandSpec` literals plus module `specs()` builders). The README's "500+ commands" is quoted as a README claim, not asserted as measured.
- **Not verified live.** The GUI was not launched and no command executed; every behavioural claim rests on source and docs. Untested at runtime: actual save/open round trips, control-channel latency, screenshots, autosave timing.
- **Uncertain / not traced.** Which 26 preferences "do nothing" (scorecard gives the count, not the list where I read it); the exact semantic coverage of `export.quickExportFormat` beyond its spellings (`crates/engine/src/prefs.rs:1081`); the exact `.atn` event count (~112 from `ROADMAP.md`/`docs/gaps.md` G11, not counted in code).
