---
name: effectcraft
description: >-
  EffectCraft is a macOS motion-graphics, compositing and VFX app — a clean-room, pure-Rust
  reimplementation of Adobe After Effects — for compositions, layers, keyframes, effects, text,
  shapes, 3D, tracking and rendering. Trigger this skill whenever the user mentions EffectCraft,
  .ecproj/.ecprojx/.ectemplate/.ecpreset files, effectcraft-cli, asks what it can do, which file
  formats or shortcuts it has, or wants to troubleshoot it; or asks to create, edit, animate,
  composite, render, convert, inspect, verify or automate a motion graphic, title card, logo
  animation, green-screen composite or VFX shot — even when they do not name the app ("make a
  title card", "animate this logo", "render this comp", "export a ProRes", "export Lottie",
  "open this .aep"). Also use it when choosing between EffectCraft and FilmCraft, or when
  preparing or verifying assets for EffectCraft.
---

## Overview

EffectCraft is a free, open-source, clean-room reimplementation of Adobe After Effects 2026 for
motion graphics and visual effects: compositions, layers, keyframes, effects, text, shapes, masks,
3D, tracking, a render queue and Lottie interchange, written in pure Rust (`README.md`). It is
**alpha**: its own estimate is ≈91% feature breadth but only ≈45% "ready for real work"
(`README.md:237-238`, `docs/gaps.md:15-28`). It is the compositor of the ArtCraft family; FilmCraft
is the editing/NLE sibling, not this app.

Source: `github.com/storytold/effectcraft`, MIT OR Apache-2.0. This skill was written against
**v0.11.1**, commit `2a01226894c6bc58ae4fadcc24a10198d693acaa`, which is also the installed
`/Applications/EffectCraft.app` (bundle `ai.storyteller.effectcraft`, universal, macOS 11+; its
`EffectCraftBuildCommit` matches this commit).

Three entry points drive the same engine commands: the CLI (`effectcraft-cli`), an MCP server, and a
localhost JSON control channel for the live GUI (`docs/agents.md`). Everything the UI does is an
engine command with an id and JSON params (`crates/engine/src/commands/mod.rs`).

## Capabilities (verified)

### Project and document model

- **Native `.ecproj`** is versioned, pretty-printed JSON, headed by `savedBy` and `schema`
  (currently 2), with `activeComp`/`openComps`, `settings`, `items`, `nextId`, `renderQueue`,
  `renderTemplates` and `renderPrefs` (`crates/project/src/lib.rs:34-103,1350-1364`). Saving
  re-reads the text before writing and writes atomically, so a save cannot produce a file the app
  cannot open (`crates/project/src/lib.rs:1510-1528`, `crates/engine/src/lib.rs:143`).
- **XML project copy `.ecprojx`** is the same data as `EffectCraftProject` XML;
  `File ▸ Save As ▸ Save a Copy As XML…` writes it and `file.open` reads it back; Save/Save As keep
  the file's format (`crates/engine/src/xml_project.rs:1-25`, `crates/engine/src/commands/file.rs:47-48,86-91,720-730`).
- **Autosave, crash recovery and headless checkpoints** with interval, max versions and custom
  folder; MCP adds `mcp --autosave` (`crates/engine/src/autosave.rs`, `docs/preferences.md:45-49`,
  `docs/agents.md` §Keeping headless work). Out-of-range values (size > 30,000 px, zero frame rate,
  bad pixel aspect) are repaired on open and reported, not rejected
  (`crates/project/src/limits.rs:16-29`, `crates/engine/src/commands/file.rs:49-65`).

### Composition, animation, effects

- **Compositions** use exact rational frame rates and integer `Tick` time; `comp.new` defaults to
  1920×1080, 29.97 fps, 10 s, with `renderer: classic3D|advanced3D`
  (`crates/engine/src/commands/comp.rs:96-120`).
- **Every AE layer kind**: footage, precomp, solid, text, shape, null, camera, light, 3D model and
  parametric primitive; adjustment layers are solids with the adjustment switch. Parenting, track
  mattes, all **38 blend modes** and motion blur are in the document model
  (`crates/project/src/lib.rs:655-714`, `crates/color/src/blend.rs:9-52`, `README.md:93-94`).
- **Keyframes**: linear/Bezier/hold, per-side speed and influence (Easy Ease), auto/continuous
  Bezier, roving keys, Keyframe Velocity/Interpolation, and a Graph Editor with value and speed
  graphs (`crates/keyframe/src/lib.rs:23-46,429-437`, `crates/engine/src/commands/prop.rs:1288-1310`,
  `crates/ui-egui/src/state.rs:383-402`). Time remap/stretch/reverse/freeze are `layer_time`
  commands (`crates/engine/src/commands/layer_time.rs:1-4,253`).
- **Expressions** run on `boa` with the AE object model (`thisComp`, `thisLayer`, `wiggle`, `loopOut`,
  `valueAtTime`, `sampleImage`, text style API) and AE legacy array maths (`crates/expr/src/lib.rs:1-25`).
- **Text, shapes and masks**: point/paragraph text with character/paragraph runs and text animators;
  shape operators (trim, repeater, round corners, offset, zig zag, twist, wiggle, merge, gradient
  stroke); masks with modes, feather, expansion, vertex editing and Mask Interpolation
  (`crates/engine/src/commands/layer.rs:135-200`, `text_edit.rs`, `text_anim.rs`,
  `crates/project/src/build.rs:493-604`, `crates/engine/src/commands/mask.rs`, `mask_interp.rs`).
- **307 registered effects** (3032 parameters, 280 GPU-capable, all 32-bit float, 21 categories,
  0 marked partial) plus 9 Layer Styles (`docs/effects.md:6-10`, `crates/effects/src/lib.rs:485-529`,
  `crates/project/src/styles.rs:1-40`). The README's "306" is one behind the registry;
  `app.capabilities` reports 307 (`crates/engine/src/commands/query.rs:181-202`).
- **54 built-in animation presets** (8 text, 23 backgrounds, 23 transitions) and `.ecpreset`
  save/apply (`crates/engine/presets/*.json`, `crates/engine/src/commands/animation.rs:16-18,474-482`).

### 3D, tracking, roto and paint

- **Classic 3D and Advanced 3D**: 3D layers, one/two-node cameras with depth of field,
  Parallel/Spot/Point/Ambient/Environment lights, ray-cast shadows; Advanced 3D adds PBR materials,
  cube/sphere/plane/torus/cone/cylinder primitives, imported models and environment lighting
  (`crates/project/src/lib.rs:335-339,600-607`, `crates/gpu/src/lib.rs:1-20`,
  `crates/engine/src/commands/model3d.rs:384-390`).
- **Tracking**: point/transform tracking, stabilize, mask tracking (including face outline/detailed
  features), Warp Stabilizer, and a 3D Camera Tracker that creates cameras, solids, nulls and text
  (`crates/engine/src/commands/mask_interp.rs:19-25`, `warp_cmds.rs`, `camera_cmds.rs`).
- **Roto Brush and Object Matte**: stroke/propagate/freeze with optional MobileSAM or classical
  fallback; `objectMatte.apply/propagate/freeze` for click/box segmentation. Paint strokes/clone
  source, Liquify and all five puppet pin kinds (Position, Advanced, Bend, Starch, Overlap) are
  commands too (`crates/engine/src/commands/roto_cmds.rs`, `models.rs:404-453`, `paint.rs`,
  `liquify.rs`, `puppet.rs`, `crates/effects/src/puppet/mod.rs:1-15`).
- **Content-Aware Fill, Auto-trace and Scene Edit Detection** are background-job commands
  (`crates/engine/src/commands/content_fill.rs`, `autotrace.rs`, `scene_detect.rs`).

### Import formats (only what the code registers)

| Kind | Extensions / route | Evidence |
|---|---|---|
| Stills | `png jpg jpeg gif webp tif tiff bmp exr tga hdr psd psb svg pdf ai eps` | `crates/media/src/lib.rs:62-63` |
| Film scans | `dpx cin` (8/10/12/16-bit; log shown as stored) | `crates/media/src/dpx.rs:1-21` |
| Video | `mp4 m4v mov mkv webm mxf`; H.264, HEVC, VP9, AV1, ProRes, DNxHD, MPEG-2, MJPEG | `crates/media/src/lib.rs:10-14,67` |
| Audio | FilmCraft `AUDIO_EXTENSIONS`; documented WAV, AIFF, MP3, AAC/M4A, FLAC, Ogg, Opus | `crates/media/src/lib.rs:65`, `docs/file-format-parity.md:72-73` |
| 3D models | `gltf glb obj stl fbx` (FBX 7.x; no animation/skinning/cameras/lights) | `crates/media/src/lib.rs:70`, `docs/file-format-parity.md:79-81` |
| Data | `json csv tsv` as data footage | `crates/engine/src/commands/file.rs:552-570` |
| Lottie | `.json`, `.lottie` via `file.importLottie` | `crates/engine/src/commands/lottie.rs:29-51` |
| Timelines | `.xml` (FCP7), `.fcpxml`, `.otio`, `.edl`, `.aaf`, `.omf` | `crates/interchange/src/lib.rs:1-18,66-72` |
| Fonts | installed fonts + folders in `EFFECTCRAFT_FONT_DIRS` | `docs/agents.md` §Text |

`.json` through plain `file.import` is **data footage**, not Lottie — use `file.importLottie`
(`crates/engine/src/commands/file.rs:274-280`). PSD/PDF/AI/EPS import as footage or as a composition
(`importAs`); PSD groups become precomps, text becomes editable, effects map best-effort to Layer
Styles (`crates/engine/src/psd_import.rs:1-12`, `crates/engine/src/vector.rs:1-4`).

### Export formats

The Render Queue writes **13 formats** (`crates/project/src/render_queue.rs:499-545`):

| Family | Formats |
|---|---|
| Video | H.264 MP4 (+AAC), HEVC MP4 (`hvc1`, Main/Main 10), AV1 MP4 (`av01`), ProRes MOV (Proxy→4444 XQ; 4444 with alpha), uncompressed 8-bit MOV, WebM (VP9 or AV1 + Opus) |
| Stills | PNG, JPEG, TIFF, OpenEXR (32-bit float) sequences; animated GIF |
| Audio | WAV, AIFF (16-bit PCM) |

Render Settings/Output Modules cover quality, resolution, time span, frame rate, proxy use,
effects/solo/guide overrides, color depth, field rendering + 3:2 pulldown, motion blur, skip
existing frames, storage overflow, crop/ROI/resize, extra outputs, post-render actions and logs
(`crates/project/src/render_queue.rs:324-360,1264-1295`, `crates/engine/src/commands/render_queue.rs:998-1048`).

- **Lottie** `.json`/`.lottie` with a `warnings` list for what Lottie cannot express
  (`crates/engine/src/commands/lottie.rs:9-27`, `crates/lottie/src/lib.rs:1-20`).
- **Timeline interchange** `.xml` (FCP7 default), `.fcpxml`, `.otio`, `.edl`, `.aaf`, `.omf`;
  `prerender: none|unsupported|all` chooses what becomes ProRes 4444 media instead of clips
  (`crates/engine/src/commands/timeline.rs:132-150`, `crates/interchange/src/lib.rs:1-18`).
- **Essential Graphics template `.ectemplate`** is a ZIP (`manifest.json`, `project.ecproj`,
  `media/`, `poster.png`); **animation preset `.ecpreset`** is JSON tagged
  `effectcraftAnimationPreset` (`crates/engine/src/commands/essential.rs:1-12,807-860`,
  `crates/engine/src/commands/animation.rs:16-18`).

### Automation and platform

- **CLI** `effectcraft-cli`: `info/commands/exec/run/props/get/set/render-frame/render/bench/script/mcp`
  with `--json`, `--project`, `--demo`, `--empty`, `--save`, `--save-as`, `--bridge`, `--gpu`
  (`apps/effectcraft-cli/src/main.rs:1-38,92-192`).
- **MCP** over stdio: 36 tools (27 headless, 9 bridge-only: `screenshot`, `ui_*`, `control`) plus
  `effectcraft://document`/`commands` resources (`crates/automation/src/tools.rs:93-105,542-980`,
  `docs/mcp.md:3-52`).
- **Control channel**: `effectcraft --control <port>` exposes `engine.execute`, `ui.menu.invoke`,
  `render.frame`, `ui.inspect`, `ui.elements`, `ui.click`, `ui.drag`, `ui.key`, `ui.type`, `ui.set`,
  `ui.playback`, `app.quit` as newline JSON on `127.0.0.1` (`apps/effectcraft/src/control_server.rs:27`,
  `docs/control-protocol.md`).
- **Scripts/ScriptUI**: `.jsx`/`.js` with the AE object model, dockable panels, `script.run`,
  `file.runScript` (`docs/plugins.md:29-52`, `crates/script/src/lib.rs`).
- **WebAssembly plug-ins**: `.wasm`/`.wat`, API v1, sandboxed in `wasmi`; the settings `Plug-ins`
  folder loads at startup (`crates/plugin/src/lib.rs:1-30`, `apps/effectcraft/src/main.rs:219-223`).
- **Web build** (`apps/effectcraft-web`) runs the same engine/UI as WASM with browser storage and
  `window.effectcraft`; it is not the installed macOS app. The wgpu compute compositor covers
  Metal/Vulkan/Direct3D 12/WebGPU; CPU is the reference, desktop defaults to GPU, and headless CLI
  is CPU unless `--gpu` (`docs/web.md:1-20,379-410`, `crates/gpu/src/lib.rs:1-34`,
  `docs/architecture.md:266-277`, `apps/effectcraft-cli/src/main.rs:350-371`).

## Known limitations and not-implemented

- **After Effects projects will not open.** No `.aep`/`.aepx` reader, no `.ffx` presets, no `.mogrt`
  templates, no AE SDK plug-ins (`.aex`/`.plugin`). Only `.ecproj`/`.ecprojx`, `.ecpreset` and
  `.ectemplate` are native (`README.md:227-228`, `docs/file-format-parity.md:21-34`, `docs/gaps.md`).
- **Fidelity against After Effects is mostly unmeasured.** One live comparison exists (scalar ease,
  168 samples); everything else is self-graded (`docs/gaps.md:23-28`, `docs/fidelity/`). Never
  promise AE-identical renders.
- **No hardware video decode/encode** (VideoToolbox, NVENC, Quick Sync, VA-API). HEVC/AV1 have no
  B-frames, multi-reference or SAO/CDEF, so files are larger (`docs/gaps.md:74,81`,
  `docs/file-format-parity.md:99-106`).
- **Output/import gaps**: no 16-bpc uncompressed, AVI, lossless single-file video, MXF, DNxHR,
  DPX/Targa/Photoshop sequences or ProRes RAW; no USD/USDZ, Substance `.sbsar`, camera raw,
  HEIF/AVIF, BRAW/R3D/ARRIRAW. AVI is listed in the Media Browser but has no demuxer
  (`docs/file-format-parity.md:54-106`, `docs/gaps.md:72-76`).
- **FBX/DPX/PDF caveats**: FBX is 7.x only, with no animation, skinning, cameras or lights; DPX/
  Cineon log values are shown as stored (no log-to-linear); PDF/AI/EPS import lacks JPX/JBIG2 and
  Illustrator procset EPS (`crates/media/src/dpx.rs:1-12`, `docs/file-format-parity.md:46,79-81`).
- **Scripting gaps**: no `.jsxbin`, no Startup/Shutdown script folders, no script shortcuts, no
  Legacy ExtendScript engine mode (`docs/scripting-parity.md:17-30`, `docs/plugins.md:14-23`).
- **Alpha stability**: open crash reports remained at 12 Oct 2026; Linux/Windows lag macOS
  (`ROADMAP.md`, `docs/roadmap.md:9-20`, `README.md:231-242`).
- **The macOS `.app` contains no CLI** — `Contents/MacOS` holds only `EffectCraft`; get the universal
  `effectcraft-cli` from its separate release zip or build it (`docs/agents.md`, `README.md`).
- **The control channel has no authentication**, binds `127.0.0.1`, and lets anyone who reaches it
  run commands, read the project and take screenshots (`docs/control-protocol.md:9-25`).
- **Docs drift — trust code/runtime.** `docs/gaps.md` gap 18 says no relinking, but
  `footage.relink`/`file.relinkFootage` and moved-project search exist
  (`crates/engine/src/commands/relink_moved.rs:1-18`, `relink.rs`). `README.md:121` says 306 effects;
  the registry says 307 (`crates/engine/src/commands/query.rs:181-202`). The bundle declares QOI,
  which `STILL_EXTENSIONS` omits (`packaging/macos/Info.plist.in:112-123`, `crates/media/src/lib.rs:62-63`).

## How to operate

### Launch (macOS)

```sh
open -a EffectCraft                                  # empty Untitled Project (not the demo)
open -a EffectCraft /path/to/Project.ecproj          # open a project
open -a EffectCraft clip.mov plate.exr               # import media into a new project
open -a EffectCraft --args --control 9877 --demo     # agent-driven window + demo project
/Applications/EffectCraft.app/Contents/MacOS/EffectCraft --control 9877 --demo --home
```

Flags: `--control <1-65535>`, `--demo`, `--empty`, `--home`, `--version`; after `--` every
argument is a file. Unknown options exit 1 before the window opens
(`apps/effectcraft/src/main.rs:64-123`). The app starts **empty** by default, unlike most one-shot
CLI commands, which start with the demo (`apps/effectcraft/src/main.rs:7-8,236-238`).

### CLI

`effectcraft-cli` is a separate macOS release zip (signed/notarized) or
`cargo build --release -p effectcraft-cli`; it is **not** inside the `.app`. Verify with
`effectcraft-cli --version`; this bundle is 0.11.1. If the launcher updated the app, check
`plutil -p /Applications/EffectCraft.app/Contents/Info.plist` and re-read `commands`.

- `<comp>` is an id, name or `-` (active comp); `<layer>` is an id, `#n` or name; values are JSON
  (`50`, `[960,540]`, `"#ff0000"`) or bare strings (`apps/effectcraft-cli/src/main.rs:37-38,253-264`).
- **Most commands open the demo project** unless you pass `--project F.ecproj`, a positional
  `*.ecproj`, or `--empty`. `commands`, `script` and `mcp` start empty; `bench` opens the demo
  unless given a project (`apps/effectcraft-cli/src/main.rs:334-348,495-645`).
- `--save` writes back to the opened project, `--save-as F` writes a copy; without either, headless
  edits are memory-only (`apps/effectcraft-cli/src/main.rs:374-384`).
- `--json` prints one compact JSON document; errors become `{"error": …}` and exit 1; usage errors
  exit 2 before running (`apps/effectcraft-cli/src/main.rs:273-312`).
- `--gpu` attaches the GPU compositor; CPU is the default (`apps/effectcraft-cli/src/main.rs:350-371`).
- `--autosave` is MCP-only. `--bridge PORT` drives `effectcraft --control PORT`, cannot be combined
  with `--project`/`--demo`, and `render` refuses bridge mode
  (`apps/effectcraft-cli/src/main.rs:334-340,446-448,686-690`).
- `render` needs `--out` (or `--queue`); a relative `--out` is against the **working directory**,
  while queued outputs resolve against the project folder. `render --comp …` renders exactly one
  item (unchecking the rest); `render --queue` uses the project's queue settings
  (`apps/effectcraft-cli/src/main.rs:678-772`).
- `render-frame` writes `frame.png` by default; accepts `--time`, `--frame`, `--max-side`,
  `--scale`, `--transparent` (`apps/effectcraft-cli/src/main.rs:586-619`).
- `--template T.ectemplate --values values.json` renders one Essential Graphics instance; it cannot
  combine with `--project`, `--demo`, `--bridge`, `--queue` or `--comp` (`apps/effectcraft-cli/src/template.rs:13-59`).

### Document model and workflow

One project per app process in one window; compositions open as tabs and are restored with the
project (`crates/project/src/lib.rs:52-67`, `docs/architecture.md:94-103`). Panels follow After
Effects (Project, Composition, Timeline, Effect Controls, Properties, Effects & Presets, Character,
Paragraph, Align, Info, Preview, Audio, Render Queue) and dock/float (`README.md:86-90`). Each
layer carries a property tree addressed by paths such as `transform/position`,
`effects/#1/blurriness` or `@<uid>`.

1. Create a composition (`comp.new`) and add layers (`layer.new*`, `file.import`).
2. Animate (`prop.set`/`prop.addKey`) and ease (`keys.select` + `keys.easyEase` in one session).
3. Apply effects (`effect.apply`) and edit their `effects/#1/...` paths.
4. Preview (`render_frame`/`render-frame`) and save (`save_project`/`file.save`).
5. Export via `renderQueue.add` + `renderQueue.render`, or Lottie/timeline/template commands.

```sh
effectcraft-cli exec comp.new '{"name":"Main","width":1920,"height":1080,"frameRate":30,"duration":3}' \
  --empty --save-as main.ecproj
effectcraft-cli exec layer.newText '{"text":"Hello","name":"Title","size":160,"fill":"#ffffff"}' main.ecproj --save
effectcraft-cli run main.ecproj \
  prop.addKey '{"layer":"Title","path":"transform/position","time":0,"value":[-400,540]}' \
  prop.addKey '{"layer":"Title","path":"transform/position","time":1,"value":[960,540]}' \
  keys.select '{"keys":[{"layer":"Title","path":"transform/position","time":0},{"layer":"Title","path":"transform/position","time":1}]}' \
  keys.easyEase '{"which":"both"}' --save
effectcraft-cli render main.ecproj --comp Main --out title.mp4 --format h264
```

Each headless CLI invocation is a new session: edits survive only if saved, and editor state such as
key selection never does; group selection-dependent steps in one `run` (or one MCP session).

### Open / save / export, exact formats

- **Open** `.ecproj`, `.ecprojx`, or `.xml` whose root is `EffectCraftProject`; `file.importProject`
  merges an `.ecproj`/`.ecprojx` instead (`crates/engine/src/commands/file.rs:43-83`).
- **Save** `.ecproj`, or XML when the path is `.ecprojx`; Save a Copy As XML and Increment and Save
  exist (`crates/engine/src/commands/file.rs:86-119`, `crates/engine/src/commands/app_more.rs:672`).
- **Export** the 13 Render Queue formats, Lottie `.json`/`.lottie`, timeline formats, `.ectemplate`,
  `.ecpreset`. A `.xml` path is ambiguous: `file.open` expects an EffectCraft XML project, while
  `file.importTimeline` expects FCP7 XML — use `.ecprojx` for projects.

### Keyboard shortcuts (only verified ones)

`Cmd+N` New Composition, `Cmd+Alt+N` New Project, `Cmd+O` Open, `Cmd+S` Save, `Cmd+Shift+S` Save As,
`Cmd+M` Add to Render Queue, `Cmd+I` Import, `Cmd+K` Composition Settings, `Cmd+Shift+X` Trim Comp
to Work Area, `Cmd+Alt+;` Settings, `F9` Easy Ease (`Shift+F9` in, `Cmd+Shift+F9` out), `Cmd+Alt+K`
Keyframe Interpolation, `Cmd+Shift+K` Keyframe Velocity, `Cmd+Alt+H` Toggle Hold, `Cmd+Alt+T` Enable
Time Remapping (`crates/engine/src/commands/file.rs:720-730`, `comp.rs:278-290`, `prop.rs:1288-1310`,
`crates/engine/src/menus.rs:492`). Property reveals `A/P/S/R/T/M/F/E/L/U`, their double presses and
`Alt+Shift+A/P/S/R/T` keying are in `docs/agents.md` §Timeline. For anything else, read
`effectcraft-cli commands --json`; do not invent shortcuts.

## Working with an AI agent

### Choose the surface

- **Headless (preferred)**: `effectcraft-cli exec/run` for one-shots or `effectcraft-cli mcp` for a
  persistent session. Headless MCP starts empty; add `--demo` or `--project`; `mcp --autosave`
  checkpoints dirty work (`docs/agents.md` §MCP setup).
- **Live app**: start `effectcraft --control 9877`, then `mcp --bridge 9877` or the raw control
  channel. Bridge mode adds `screenshot`/`ui_*`; the CLI cannot drive UI (`docs/control-protocol.md`).
- **Web**: no TCP channel; use `window.effectcraft` (`execute`, `request`, `renderFrame`, `addFile`,
  `files`, `saveToBrowser`) (`docs/web.md:379-410`).

### Prepare inputs

- Convert unsupported sources: camera raw/AVI/BRAW/R3D/USDZ/Substance → H.264/ProRes/WebM or
  PNG/EXR/TIFF sequences; 3D → glTF/GLB/OBJ/STL/FBX 7.x; audio → WAV/AIFF; data → JSON/CSV/TSV.
- Image sequences: pass one numbered file with `sequence: true` (or import the folder) so the run is
  one footage item; missing numbers become color bars. Keep media next to the project: stored paths
  are absolute, and relative paths resolve against the project folder on open
  (`docs/footage.md:20-58`, `crates/engine/src/doc_path.rs:1-60`).
- Query `list_fonts`/`text.fonts` first and use a listed family and style; extra fonts come from
  `EFFECTCRAFT_FONT_DIRS` (`docs/agents.md` §Text).

### Inspect and repair project files

- `.ecproj` is documented by the code, not a public spec: `savedBy`, `schema`, `settings`, `items`,
  `nextId`, `renderQueue` (`crates/project/src/lib.rs:1350-1364`). Item, layer and property ids
  share one counter; keep `nextId` above every id. Never bump `schema`; a newer schema is refused
  rather than rendered wrongly (`crates/project/src/lib.rs:1545-1549`).
- Prefer commands over JSON surgery: `info`, `props`, `get` and `exec` validate through the same
  reader the app uses. After a hand edit, reopen and check for the "values outside limits were
  corrected" report (`crates/engine/src/commands/file.rs:49-65`).
- For moved media: `footage.missing`, `footage.relink {item, path}` (also relinks other missing files
  in the same place) or `file.relinkFootage {folder, dryRun}`; do not rewrite paths blindly
  (`crates/engine/src/commands/relink_moved.rs:1-18`, `relink.rs:184-190`).
- `.ectemplate` (ZIP) and `.ecpreset` (tagged JSON) are inspectable, but re-export through the app
  after edits (`crates/engine/src/commands/essential.rs:10-12,807-860`,
  `crates/engine/src/commands/animation.rs:16-18`).

### Verify exports

- Read the result: `renderQueue.render` returns per-item statuses; CLI `render` exits 1 if any item
  failed, and `exec`/`run` treat a failed render as an error
  (`apps/effectcraft-cli/src/main.rs:656-669,796-815`).
- Re-import the output and render a frame (`file.import`, `file.newCompFromSelection`, `render_frame`)
  to prove it decodes; use `--transparent`/`transparent: true` for alpha (`docs/agents.md` §Cookbook).
- Lottie: inspect `warnings` and confirm what a player will omit (`crates/engine/src/commands/lottie.rs:24-26`).
- Timeline: inspect `warnings`, `missing` and `prerendered`; `prerender: none` omits layers a
  timeline cannot represent, `unsupported` (default) pre-renders those to ProRes 4444, and `all`
  pre-renders every visual layer (`crates/interchange/src/lib.rs:1-18`).
- Odd comp sizes: H.264/HEVC dimensions round down to even (`crates/project/src/render_queue.rs:599-604`).

### Do not

- Try to open `.aep`/`.aepx`/`.aex`/`.ffx`/`.mogrt`/`.prproj`; there is no reader. Convert timelines
  to FCP7 XML in Premiere first; expect only `.wasm` plug-ins, `.ecpreset` and `.ectemplate`
  (`crates/engine/src/commands/timeline.rs:25-31`, `docs/plugins.md:12-23`).
- Drive the GUI without `--control`: there is no documented UI-scripting fallback, and coordinate
  clicks are fragile. Discover widgets with `ui.elements` (`docs/control-protocol.md`).
- Edit a `.ecproj` the app has open; it holds the project in memory and will overwrite your changes.
- Expose the control port; it has no authentication (`docs/control-protocol.md:9-25`).

### Concurrency and safety

- Save early; `open_project`/`file.newProject` replaces a dirty project without a prompt. Without
  `--autosave`, MCP work is memory-only (`docs/agents.md` §Keeping headless work, §Pitfalls).
- After a broken bridge connection, mutating calls have an **unknown outcome**; inspect before
  retrying (`docs/agents.md` §MCP setup).
- `batch` is atomic and rolls back on a failing step; `command_batch` stops at the first error by
  default (`docs/mcp.md:29-31`, `crates/engine/src/commands/batch.rs`).
- Scripts may read files only in the project's folder and cannot write or use the network unless
  Settings ▸ Scripting & Expressions allows it (`docs/agents.md` §CLI).
- Confine agent file access with `--automation-read-root` / `--automation-write-root` when running
  MCP on untrusted work (`docs/mcp.md:6-17`).

## Verification protocol

Alpha-software discipline; run this for every delegated task.

1. **Copy first.** Work on a scratch `.ecproj` (`--save-as` / Save a Copy), never the only copy;
   update the app only between projects.
2. **Round-trip in a fresh process.** New → comp/layers/keyframes/effects → save → reopen via
   `info --project` (or `exec file.open`) → render a frame and a short movie. A save that cannot be
   read back is a bug; report it.
3. **Check both artifacts.** A `render-frame` PNG at a known time and the final MP4/MOV/sequence;
   confirm dimensions, duration/frame count, audio and alpha, and for sequences every `#####` frame.
   Read `renderQueue.render` statuses or the CLI `done:` lines; check `last_output` is a non-zero file.
4. **Check the time span.** Queued items default to **Work Area**; CLI `render` defaults to the whole
   comp unless `--work-area`. An empty render is usually this, not a codec failure
   (`crates/project/src/render_queue.rs:362-379`, `apps/effectcraft-cli/src/main.rs:711-719`).
5. **Check format constraints.** H.264/HEVC even dimensions; ProRes 4444 for alpha; WebM VP9 for VP9
   alpha; WAV/AIFF are 16-bit PCM; EXR is 32-bit float (`crates/project/src/render_queue.rs:499-604`).
6. **Interchange and Lottie:** inspect warnings/missing/prerendered, re-import the result, and open
   Lottie in an independent player if available. Record versions and `savedBy` before delivery.
7. **Report, don't hide.** Give the exact command, version, file and observed result. Fidelity
   differences against After Effects are expected and are the most useful report.

## Sources & evidence

- Repository: `https://github.com/storytold/effectcraft`; inspected tag `v0.11.1`, commit
  `2a01226894c6bc58ae4fadcc24a10198d693acaa` (`git rev-parse HEAD`, 2026-10-18).
- Installed app: `/Applications/EffectCraft.app`, version 0.11.1, bundle
  `ai.storyteller.effectcraft`, build commit `2a01226894c6bc58ae4fadcc24a10198d693acaa`, universal
  `x86_64`+`arm64`, macOS 11+. Written 2026-10-18; no GUI was launched.
- Read: `README.md`, `Cargo.toml`, `ROADMAP.md`, `AGENTS.md`; `docs/{agents,mcp,control-protocol,architecture,file-format-parity,gaps,roadmap,preferences,footage,plugins,scripting-parity,web,effects}.md`;
  `apps/effectcraft-cli/src/{main,template}.rs`, `apps/effectcraft/src/{main,control_server}.rs`;
  `crates/project/src/{lib,render_queue,styles,limits}.rs`;
  `crates/engine/src/commands/{file,comp,layer,prop,render_queue,lottie,timeline,essential,animation,import_project,relink,relink_moved,roto_cmds,camera_cmds,warp_cmds,model3d}.rs`;
  `crates/engine/src/xml_project.rs`, `crates/media/src/{lib,dpx,layered}.rs`,
  `crates/interchange/src/lib.rs`, `crates/lottie/src/lib.rs`, `crates/effects/src/lib.rs`,
  `crates/color/src/blend.rs`, `crates/keyframe/src/lib.rs`, `crates/expr/src/lib.rs`,
  `crates/automation/src/tools.rs`, `crates/plugin/src/lib.rs`,
  `crates/ui-egui/tests/ui_agent_audit.rs`; source, generated docs, tests and bundle metadata only.
