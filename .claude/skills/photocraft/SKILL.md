---
name: photocraft
description: PhotoCraft is the ArtCraft clean-room, pure-Rust reimplementation of Adobe Photoshop — layers, masks, adjustment layers, layer styles, live type, vectors, smart objects and real PSD read/write, with every action exposed as an engine command that the UI, a headless CLI, a JSON control channel and an MCP server all drive. Trigger this skill whenever the user mentions PhotoCraft, asks what it can or cannot do, which file formats it reads or writes, its keyboard shortcuts, how to script, automate or batch it, how to prepare assets for it, how to inspect, verify or repair a .pcraft or PSD it produced, or how to troubleshoot it — and also when they never name the app but describe the job, such as "edit this photo", "open this PSD", "make a transparent PNG", "batch-resize a folder of images", "remove the background with a quick selection" or "check what is in this layered file". It is early alpha — never promise Photoshop-grade PSD fidelity, AI features or a stable UI, and prefer the headless CLI and MCP over driving the GUI blind.
---

# PhotoCraft

## Overview

PhotoCraft is an open-source, native image editor: "Image editing; an open-source, clean-room reimplementation of Adobe Photoshop, rebuilt in pure Rust" (`README.md:13`), dual-licensed MIT/Apache-2.0, from the `storytold` org (repo `storytold/photocraft`). The desktop app is egui/eframe on wgpu with a CPU compositor as the reference oracle; the same Rust compiles to WebAssembly for the browser build (`apps/photocraft-web`, `Cargo.toml` `wasm-release` profile, `cargo xtask wasm`). Everything user-visible is an engine command, so the UI, `photocraft-cli`, the JSON control channel and the MCP server run the same code (`README.md:221-242`, `crates/engine/src/commands.rs`). Maturity is **early alpha**: ~76% feature breadth, ~45% "ready for real work", 953 open issues at the last measurement (`ROADMAP.md:3-45`, `docs/target-app-parity.md`). The source inspected here is tag `v0.10.0` (commit `8407d9ccb125af52944fca9d228383459f94aaef`), which is exactly the installed `/Applications/PhotoCraft.app` 0.10.0.

## Capabilities (verified)

### Editing core

- **Documents and colour**: RGB, Grayscale, CMYK and Lab at 8/16/32-bit float, plus Bitmap, Indexed, Duotone and Multichannel; ICC colour management in pure Rust with Assign/Convert to Profile, rendering intents, black point compensation, soft proofing (`view.proofSetup`, `view.proofColors`) and Gamut Warning (`README.md:194-199`, `crates/cms`, `crates/engine/src/*_cmds.rs`).
- **Layers, done properly**: pixel layers, groups, clipping masks, pixel and vector masks, fill layers (solid/gradient/pattern), adjustment layers, live smart objects with smart filters and lossless transforms/warps, alpha channels, Quick Mask, layer comps, artboards (`README.md:188-191`, `crates/doc`, `crates/engine`, `docs/scorecard.md` FILE-215 rows).
- **16 adjustment-layer commands**: `layer.newAdjustmentLayer.{blackWhite, brightnessContrast, channelMixer, colorBalance, curves, exposure, gradientMap, hueSaturation, invert, levels, photoFilter, posterize, selectiveColor, threshold, vibrance}` (grep of `crates/engine/src/`; 16 ids).
- **10 layer effects**, several instances per kind allowed: DropShadow, InnerShadow, OuterGlow, InnerGlow, Stroke, ColorOverlay, GradientOverlay, PatternOverlay, Satin, BevelEmboss (`crates/doc/src/effects.rs:261`).
- **Blend modes**: PassThrough (groups) + 27 Photoshop blend modes + 6 Paint.NET variants (`crates/color/src/blend.rs`).
- **67 tools** including Remove, Spot/Healing Brush, Patch, Content-Aware Move, Mixer Brush, Magnetic Lasso, Object/Quick Selection, Select Subject, Pen/Freeform/Curvature Pen, Convert Point, shapes, Type and Type Mask, Frame, Slice (`crates/ui-egui/src/state.rs:141` — `pub const ALL: [Tool; 67]`).
- **Selections**: marquee/lasso/wand, `select.quick`, `select.object`, `select.subject`, `select.sky`, `select.colorRange`, `select.focusArea`, `select.refineEdge`; Select and Mask opens a dialog for `select.refineEdge` (`crates/engine/src/smartselect_cmds.rs`, `crates/ui-egui/src/menus.rs:473`).
- **Filters** with live in-dialog preview: `crates/engine/src/filters.rs`, `filters_ext.rs`, `gallery_cmds.rs`; filters on a smart object become re-editable smart filters (`README.md:144-150`).
- **Type**: point and paragraph text edited on canvas, Character/Paragraph controls, `type.warpText`, OpenType features, `type.resolveMissingFonts`; **type on a path is implemented** (`type.attachToPath` / `type.detachFromPath`, `crates/engine/src/type_extra_cmds.rs:695-703`) even though older roadmap prose still lists it as missing.
- **Vectors**: Pen/Freeform/Curvature tools, insert/delete/convert anchor, paths panel, work paths, shape layers, path-to-selection; SVG opens as editable shape layers or a vector smart object (`crates/io/src/svg.rs`).
- **Actions**: record/replay, `actions.play`, Photoshop `.atn` import/export mapping ~112 Photoshop events (`crates/engine/src/atn_cmds.rs`, `docs/development.md`).
- **Print**: File › Print renders one flattened PDF page and hands off via `lp`/CUPS-IPP/portal (`file.print`, `file.printOneCopy`, `docs/printing.md`).
- **Video-lite**: `timeline.create` and `file.export.renderVideo` (PNG sequence / animated GIF) (`crates/engine/src/timeline_cmds.rs:137`, `video_cmds.rs:406`).

### Files — read / write

- **Native**: `.pcraft` (zip of STORE entries or a directory) = `manifest.json` (format version 1, migrations in `crates/format/src/migrate.rs`) + content-addressed BLAKE3/zstd `tiles/` and `blobs/` + `thumb.png` + `composite/preview.png`; incremental saves, atomic writes, crash-recovery autosaves (`crates/format/src/lib.rs:3-19`, `crates/format/src/autosave.rs`). Registered macOS type `ai.storyteller.photocraft.document` (bundle Info.plist).
- **Read + write**: PSD and PSB (layers, groups, masks, vector masks, adjustment and fill layers, effects, text, shapes, smart objects, alpha channels; streaming) — `crates/io/src/psd_import.rs`, `psd_export.rs`, `crates/psd`; OpenRaster `.ora` with layers/groups/blend modes — `crates/io/src/ora.rs`; layered TIFF (Photoshop layer data, both byte orders; extra alpha channels and a Quick Mask are not written) — `crates/io/src/tiff_layers.rs`; and via `photocraft-codecs`: PNG (8/16-bit), JPEG, TIFF (8/16/32f, BigTIFF), WebP (lossless + own lossy VP8 encoder), GIF, BMP, TGA, ICO, Netpbm (PBM/PGM/PPM/PAM/PFM), QOI, OpenEXR (f16/f32), Radiance HDR, FITS, DPX (8/10/12/16-bit) (`crates/codecs/README.md` capability matrix; export dispatch `crates/io/src/lib.rs:390-452`).
- **Read-only imports**: Paint.NET PDN3 (editable layers, 14 blend modes), Krita `.kra`/`.krz`, Affinity `.af`/`.afdesign`/`.afphoto`/`.afpub`, DDS textures, Cineon, SVG (as shape layers), HEIC/HEIF (official builds enable the `heif` feature), and camera raws — `crates/io/src/pdn.rs`, `kra.rs`, `affinity.rs`, `svg.rs`, `crates/codecs/README.md`, `crates/raw/src/lib.rs:31-37`.
- **Camera raw decode**: DNG (uncompressed, deflate, lossless-JPEG, lossy-JPEG and JPEG XL, CFA and LinearRaw), CR2, TIFF/EP raws (NEF, ARW, PEF), Nikon compressed NEF, Sony cRAW, Panasonic RW2, uncompressed Olympus ORF, uncompressed Fujifilm RAF (Bayer and X-Trans); everything else reports Unsupported, and CR3 gives only its embedded JPEG preview + orientation, not sensor data (`crates/raw/src/lib.rs:31-37,241`, `cr3.rs`).
- **PDF**: write only, one flattened RGB/Gray/CMYK page with ICC — Save As / Save a Copy / CLI and print (`crates/io/src/pdf.rs:8`, `docs/file-format-parity.md` FILE-215-10).
- **Export As** formats: `png`, `jpg`, `webp`, `tif`, `tga`, `ico` (`crates/engine/src/export_preset_cmds.rs:13`). **Save for Web**: `gif`, `png8`, `png24`, `jpeg`, `wbmp` (`crates/engine/src/web_cmds.rs:46-59`). Quick Export as PNG (`crates/engine/src/shell_commands.rs`).
- **Depth honesty**: `caps(format)` and `fidelity_warnings` report what an export will lose before it is written; CLI and desktop surface those as warnings (`crates/codecs/README.md`).

### Automation surfaces

- **One command registry**: every Photoshop menu item in the catalog is wired — 631/631 live, enforced by `FLOOR = 631` (`crates/ui-egui/src/parity.rs:10`, `docs/parity-checklist.md`). Wiring is not behaviour; check `enabled`/`disabledReason`/`needsDocument` per command (`docs/control-protocol.md`).
- **CLI `photocraft-cli`** — 8 subcommands, all flags enforced (an unknown flag is a usage error, exit 2): `convert`, `info`, `run`, `batch`, `droplet`, `commands`, `mcp`, `serve` (`apps/photocraft-cli/src/lib.rs:14-100`).
- **Control channel**: `photocraft --control <port>` serves authenticated JSON lines on `127.0.0.1` only; first frame must be `{"id":"auth","method":"auth","params":{"token":"<64 hex>"}}`; 60-second reply timeout. Methods include `engine.execute`, `engine.commands`, `ui.inspect`, `ui.set`, `ui.menu.invoke/list`, `ui.pointer`, `ui.click`, `ui.move`, `ui.key`, `ui.type`, `ui.dialog.*`, `ui.screenshot`, `ui.window.open/close`, `app.open`, `app.save`, `app.quit` (`docs/control-protocol.md`, `apps/photocraft/src/control_server.rs`, `crates/ui-egui/src/control.rs`).
- **MCP**: `photocraft-cli mcp` runs headless; `--bridge 127.0.0.1:<port>` wraps a running app. Tools: `command_list`, `command_run`, `command_batch`, `doc_inspect`, `render_preview`, `ui_inspect`, `ui_screenshot` (+ session/job tools); resources `photocraft://document`, `photocraft://commands` (`docs/mcp.md`).
- **Headless server**: `photocraft-cli serve` (stdio or `--port`) answers `doc.open/new/place/save/exportLayers/exportDataSets/importDataSets/inspect/render/select/close`, `engine.execute`, `batch`, `session.list`, `jobs.list/cancel` (`apps/photocraft-cli/src/lib.rs:46-51`).
- **Plug-ins**: WebAssembly ABI v1 — `plugin.install/run/remove/reload/list`, wasmi sandbox, no WASI/filesystem/network, 50M-instruction fuel and 60 s budget per run (`docs/plugins.md`).
- **Batch/droplets**: `photocraft-cli batch` applies an actions JSON, an Actions set, or a `.atn` file to a folder; `.pcdroplet` droplets run via `file.automate.runDroplet` with a Unix `.command` shim (`crates/engine/src/automate_cmds.rs:313-566`). MCP acceptance: 10 scripted agent tasks + more in `crates/automation/tests/agent_tasks.rs`, `agent_tasks_more.rs`.

### Platform

- macOS, Windows, Linux, FreeBSD natives and a WebAssembly web build (`README.md` Downloads; `Cargo.toml` `wasm-release`; `cargo xtask wasm`).
- GPU compositor on wgpu (Metal/Vulkan/DX12/WebGPU) with CPU fallback, `--safe-gpu`, automatic driver-crash fallback and `ui.gpu.simulateLoss` for testing (`apps/photocraft/src/gpu_startup.rs`, `docs/control-protocol.md`).
- Pen tablets: pressure/tilt/rotation on macOS (isolated AppKit monitor crate), Windows (`WM_POINTER` via winit), Linux X11 (XInput2), web (Pointer Events); Wayland native tablet-v2 still open (`AGENTS.md`, `crates/tablet`, `docs/roadmap.md` M6).

## Known limitations and not-implemented

Read this before assigning work — several of these are the reason agents should not promise Photoshop behaviour.

- **Alpha, by measurement**: ~45% "ready for real work" and 953 open issues at last count (`ROADMAP.md:42-47`); the committed performance baseline has 3 of 58 scenarios within budget, 22 over budget or failing (including a GPU validation crash at 150 layers, P12), 24 not yet measured or tracked (`docs/scorecard.md` Performance).
- **PSD fidelity is the blocking gap (G1)**: enforced corpus floors are *minimums* — Photoshop-authored oracles 188/256 render-pass with 258 round trips, psd-tools 249/309, io corpus 148/170 (`crates/io/tests/corpus.rs:151-159`, `docs/scorecard.md`). A re-saved PSD is **not byte-identical** to its source (README PSD section), and there is no test that a third-party editor re-opens our exports (FILE-216-4, missing). User reports of Photoshop refusing our files exist (#1281, #2469; `docs/gaps.md` G1).
- **No AI/generative features**: no `ml` crate in the workspace; `docs/roadmap.md` M10 says "ML backend not started"; the code deliberately declines Generative Expand (`crates/ui-egui/src/panels.rs:1309`). No Neural Filters, no generative fill/expand, no sky replacement ML.
- **No native Photoshop plug-ins**: `.8BF`, CEP and UXP are not hosted; only the Wasm plug-in ABI (`docs/plugins.md`).
- **Missing tool**: Art History Brush — 1 of Photoshop's 68 (`docs/gaps.md` G6; `crates/ui-egui/src/state.rs:141`).
- **Workspaces that are dialogs, not workspaces (G7)**: Select and Mask opens a filter dialog (`crates/ui-egui/src/menus.rs:473`); no Content-Aware Fill sampling workspace, no Vanishing Point plane editor.
- **Formats absent or partial**: no PDF import (#2541); AVIF read missing and AVIF write only behind the non-default `avif` build feature; JPEG XL, JP2, DICOM, PCX, PICT, Scitex CT, Photoshop Raw and Cloud PSD unsupported (`crates/codecs/README.md`, `docs/file-format-parity.md`). Affinity and Krita are import-only; PDN is import-only (`crates/io/src/lib.rs:392-400`). GIF opens first-frame-only (use New Video Layer from File for frames); APNG keeps the first frame; per-frame delays are not persisted (`docs/file-format-parity.md`).
- **Camera raw partial**: unsupported variants fall back to the embedded JPEG preview; "lossy after split" NEF no; no `.xmp` sidecars; CR3 sensor data no (`crates/raw/src/lib.rs`, `docs/file-format-parity.md`).
- **Dead preferences**: 26 of 168 settings do nothing (`docs/scorecard.md`).
- **Localization**: UI strings are translated (10+ languages) but engine messages stay English; Hindi, Arabic and Vietnamese are 0% (`ROADMAP.md`).
- **Windows**: PSB files over 4 GB fail (#375).
- **Wayland**: no drag-and-drop (winit 0.30 limit) and XWayland fractional scaling is blurred (`README.md:282`).
- **Timeline/video and HDR are early, and the plug-in/scripting ecosystem is thin** (`docs/roadmap.md` M12 "print, HDR, timeline pending"; `docs/gaps.md` G16 plug-in compatibility and scripting).
- Docs lag code between releases (the roadmap still carries pre-0.10 numbers; the scorecard regenerates). Verify against the installed version before asserting a feature is missing.

## How to operate

### Launch (macOS)

```sh
open -a PhotoCraft                        # normal GUI launch
open -a PhotoCraft /path/to/file.psd      # open a file in the running instance
open -a PhotoCraft --args --control 7878 --control-token-file "$HOME/.photocraft/control.token" \
     --automation-read-root "$PWD" --automation-write-root "$PWD"
```

- Binary: `/Applications/PhotoCraft.app/Contents/MacOS/PhotoCraft`; the app bundle contains **no CLI** — get `photocraft-cli` from the release zip (`photocraft-cli-<ver>-macos-universal.zip`, signed and notarized) or build it.
- App options (verified in `apps/photocraft/src/main.rs:168-198`): `-h/--help`, `--version`, `--safe-gpu`, `--in-window-menus`, `--new-instance`, `--present-mode <fifo|autovsync|novsync>`, `--frame-latency <1..3>`, `--stroke-trace <stderr|file.csv>`, `--control <port>`, `--control-token <64-hex>`, `--control-token-file <path>`, `--automation-read-root <dir>`, `--automation-write-root <dir>`, `--`. Env equivalents exist (`PHOTOCRAFT_CONTROL_PORT`, `PHOTOCRAFT_CONTROL_TOKEN`, …, `PHOTOCRAFT_CONFIG_DIR`).
- If no token is given, a fresh one is generated and printed to stderr; a token file is created with mode 0600. Treat it as a credential.
- Do not launch the GUI just to inspect a file: use the CLI (below). macOS does not render occluded windows, so live screenshots steal focus (`ui.screenshot` raises the window by default; `docs/development.md`).

### Headless CLI

Build or run from source: `cargo run -p photocraft-cli -- <subcommand>` (or `cargo build --release -p photocraft-cli`).

```sh
photocraft-cli convert in.psd out.pcraft [--format <ext>] [--quality 1-100] [--tiff-layers] [--tga-bits 24|32] [--dpx-bits 8|10|12|16]
photocraft-cli info out.pcraft [--compact]                 # JSON: size, mode, depth, layer tree, warnings
photocraft-cli run in.png --cmd layer.new.layer --params '{"name":"Ink"}' \
                        --cmd filter.blur.gaussianBlur --params '{"radius":3}' \
                        --out out.psd [--format <ext>] [--quality 1-100] [--tiff-layers]
photocraft-cli run --new '{"width":800,"height":600,"background":"white"}' --cmd document.inspect --out new.pcraft
photocraft-cli batch --actions actions.json [--action <name>] --in ./raw --out ./graded [--format jpg] [--in-place]
photocraft-cli droplet job.pcdroplet ./images [--out ./done]
photocraft-cli commands [--json] [--filter blur]
photocraft-cli mcp [--bridge 127.0.0.1:7878] [--control-token-file <path>] \
                   [--automation-read-root <dir>] [--automation-write-root <dir>]
photocraft-cli serve [--port <port>] [--control-token-file <path>] [--automation-read-root <dir>] [--automation-write-root <dir>]
```

Behaviour that bites: each `--params` must follow its `--cmd`; `run` needs exactly one of `<file>` or `--new <json>`; every command's JSON result is one line on stdout while warnings go to stderr; exit codes are 0 ok / 1 failure / 2 usage; `batch` refuses an `--out` equal to `--in` unless `--in-place`, and refuses to overwrite a same-named output; `--quality` on `convert` means JPEG and lossy WebP (without it WebP is lossless) (`apps/photocraft-cli/src/lib.rs`).

### Document and window model

One window holds the open documents as tabs (the control channel exposes them as `window.document.<index>` in tab order); `ui.window.open` adds an extra window for a document. On Windows and Linux a second launch hands its files to the running instance as new tabs; `--new-instance` and any `--control` launch start a separate process (macOS relies on LaunchServices). (`apps/photocraft/src/main.rs:13-15`, `docs/control-protocol.md`.)

### Open / save / export flow

- Open: File › Open (`Cmd+O`), drag-and-drop, or `photocraft-cli`. Save (`Cmd+S`) writes back to the document's own `.psd`, `.psb` or `.pcraft`; Save As (`Cmd+Shift+S`) picks the format from the file extension — `.pcraft` for the lossless native bundle, PSD/PSB for Photoshop handoff, any writable codec extension for flat output, and `.pdf` writes one flattened page.
- Over the control channel or MCP use `app.open` / `app.save` with paths **relative to the automation roots** — `file.open`, `file.openAs`, `file.save`, `file.saveAs`, `file.saveACopy`, `file.export.saveForWebLegacy`, `pattern.import` and smart-object file commands are refused by automation (`crates/automation/src/workspace.rs:683-702`).
- Export As (`Cmd+Alt+Shift+W`) offers png/jpg/webp/tif/tga/ico; Save for Web offers gif/png8/png24/jpeg/wbmp; Quick Export as PNG is one menu item away (`crates/engine/src/export_preset_cmds.rs:13`, `web_cmds.rs:46-59`, `shell_commands.rs`).
- Keyboard shortcuts: the authoritative tables are `crates/engine/src/shell_commands.rs` (shell + tool defaults) and `crates/ui-egui/src/menu_catalog.rs` (menu items). Verified examples: `Cmd+F` Search…, `Cmd+J` Layer via Copy, `Cmd+D` Deselect, `Cmd+O`/`Cmd+S`/`Cmd+Shift+S`, `Cmd+Alt+Shift+W` Export As, `F7` Layers, `F6` Color, `F5` Brush Settings. Photoshop shortcut sets import/export through `edit.keyboardShortcuts` (`.kys`).

### State on disk

- macOS settings dir: `~/Library/Application Support/Photocraft/` — `preferences.json`, `Presets/`, `ui.ron`, and crash recovery next to it in `Recovery/`. Override with `PHOTOCRAFT_CONFIG_DIR`; portable mode (a `portable.txt` or `PhotoCraft.portable` marker beside the executable) keeps everything in `<exe dir>/PhotoCraftData/` (`apps/photocraft/src/app_dirs.rs`).
- Recovery autosaves are `<Recovery>/<key>.pcraft` directory bundles plus `<key>.json` metadata; the entry is deleted only when the document is saved or closed, and recovery is offered at the next launch (Preferences › File Handling › Recover on launch). Autosave interval: preference `fileHandling.autosaveMinutes`, default 10, valid 1–240 (`crates/format/src/autosave.rs`, `crates/engine/src/prefs.rs:439-470,1108`).

## Working with an AI agent

Preferred ladder — use the highest rung that answers the question:

1. **Headless CLI** for convert/inspect/batch; it needs no GUI and no token.
2. **MCP headless** (`photocraft-cli mcp --automation-read-root … --automation-write-root …`) when the task is a sequence of engine commands with inspection; without roots it has no file authority (by design).
3. **Control channel on a live app** when UI state, dialogs, pointer gestures or screenshots are genuinely required.
4. **GUI pointer events last** — `ui.pointer`/`ui.key` are validated and replayable, but they depend on window focus on macOS.

Legitimate work:

- **Prepare inputs**: convert any supported source to `.pcraft`/PSD/PNG, resize/grade via `batch`, generate actions JSON or droplets, pre-export assets for other Craft apps.
- **Read and interpret documents**: `photocraft-cli info <file>` JSON (size, mode, depth, layer tree, warnings) or `document.inspect`, `layer.list`, `document.pixel` over MCP/control. `.pcraft` `manifest.json` is plain JSON and can be read directly.
- **Verify exports**: reopen with `photocraft-cli info`, read stderr warnings, probe pixels (`document.pixel`), compare size/alpha. Do not byte-compare a re-saved PSD to its source: PhotoCraft rewrites image resources, layer records and the composite on save (unknown PSD blocks are carried through verbatim), so only reopening the file tells you it is right.
- **Repair by regeneration, not by hand**: `.pcraft` tiles/blobs are content-addressed (BLAKE3) zstd objects — never edit them in place. Rebuild from the source image, an earlier bundle, or the app: a bundle written by a newer format version is refused with a clear error (`crates/format/src/lib.rs:58`, `migrate.rs`).
- **Batch safely**: `batch` will not silently overwrite; MCP `command_batch` is not atomic (earlier steps stay applied), so inspect history afterwards and undo per history entry.

Do not: assign the app AI/generative work, expect Photoshop to always open its PSD exports, assume a format is supported because Photoshop has it, drive the GUI blind when a headless command exists, run two instances that share one recovery folder, apply whole-Preferences updates over the control channel (change individual keys with `prefs.set`), or rely on doc statements that the code contradicts (docs lag by weeks — trust the source).

## Verification protocol

PhotoCraft is alpha: verify every artefact, never trust a silent export.

1. **Round-trip smoke test** before trusting any output:
   `photocraft-cli run --new '{"width":64,"height":64,"background":"white"}' --cmd layer.new.layer --out /tmp/t.pcraft`
   then `photocraft-cli info /tmp/t.pcraft`, then `photocraft-cli convert /tmp/t.pcraft /tmp/t.png` and open `/tmp/t.png` in another viewer. For edits, add a command between `--new` and `--out` and read the per-command JSON lines.
2. **Read warnings.** Fidelity warnings (bit-depth reduction, CMYK→RGB, dropped layers, missing fonts) print to stderr on `convert`/`run`/`batch` and appear in `info`/`app.save` `warnings`. An export without a warning is the only export you should believe.
3. **Version projects.** Keep the `.pcraft` for lossless re-edits and hand Photoshop the PSD/PSB; keep the original source. PhotoCraft's re-saved PSD is not byte-identical and older/newer formats migrate on load.
4. **Update only between projects.** The app updates through the ArtCraft Launcher; a version bump can change how files save. This skill documents 0.10.0 (`v0.10.0`, HEAD `8407d9c`); if the installed app differs, re-verify format and command claims against the new build (`photocraft --version` prints version, commit and build date).
5. **Prefer reversible operations.** Work on copies (`image.duplicate` or `history.newDocument` creates a new active document), inspect `document.inspect` history, and remember automation saves never fire script events.

## Sources & evidence

- Repo: https://github.com/storytold/photocraft — inspected at tag `v0.10.0`, HEAD commit `8407d9ccb125af52944fca9d228383459f94aaef` (2026-10-17); date of inspection 2026-10-18.
- Installed app: `/Applications/PhotoCraft.app` — `CFBundleShortVersionString` 0.10.0, bundle id `ai.storyteller.photocraft`, minimum macOS 11.0 (read from `Contents/Info.plist`; the app was not launched).
- Key files read: `README.md`, `ROADMAP.md`, `Cargo.toml`, `AGENTS.md`, `apps/photocraft/src/main.rs`, `apps/photocraft/src/app_dirs.rs`, `apps/photocraft-cli/src/lib.rs`, `crates/format/src/lib.rs`, `crates/format/src/autosave.rs`, `crates/io/src/lib.rs`, `crates/io/tests/corpus.rs`, `crates/codecs/README.md`, `crates/raw/src/lib.rs`, `crates/doc/src/effects.rs`, `crates/color/src/blend.rs`, `crates/ui-egui/src/state.rs`, `crates/ui-egui/src/parity.rs`, `crates/ui-egui/src/menus.rs`, `crates/engine/src/commands.rs`, `crates/engine/src/type_extra_cmds.rs`, `crates/engine/src/export_preset_cmds.rs`, `crates/automation/src/workspace.rs`, `crates/automation/tests/agent_tasks.rs`, `docs/control-protocol.md`, `docs/mcp.md`, `docs/scorecard.md`, `docs/gaps.md`, `docs/roadmap.md`, `docs/development.md`, `docs/file-format-parity.md`, `docs/parity-checklist.md`, `docs/plugins.md`, `docs/printing.md`.
- Shared libraries: `storytold/craft-libs` (pinned by git revision in `Cargo.toml`: `craft-ui`, `craft-print`, `craft-docpath`); consulted only to confirm it is a pinned external dependency here, not for app behaviour.
