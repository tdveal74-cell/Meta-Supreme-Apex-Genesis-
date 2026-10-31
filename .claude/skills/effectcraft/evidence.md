# EffectCraft — evidence table

Checkout: `storytold/effectcraft` at tag `v0.11.1`, commit
`2a01226894c6bc58ae4fadcc24a10198d693acaa` (2026-10-18). Installed bundle reports 0.11.1 and the
same `EffectCraftBuildCommit`. No GUI was launched.

Tiers: **implemented** = code path exists and is wired into UI/CLI/commands; **partial** = exists
with named limits; **claimed** = docs/README say it but code could not be found; **not
implemented** = no code path.

| # | Capability claim | Evidence | Tier |
|---:|---|---|---|
| 1 | Native project `.ecproj` is versioned JSON (schema 2) with `savedBy`, `activeComp`/`openComps`, items, render queue; save validates by reading back and writes atomically | `crates/project/src/lib.rs:34-103,1350-1364,1510-1528`; `crates/engine/src/lib.rs:143`; `docs/architecture.md:94-103` | implemented |
| 2 | `.ecprojx` is a lossless XML copy of the project, opened and saved like `.ecproj` | `crates/engine/src/xml_project.rs:1-25`; `crates/engine/src/commands/file.rs:47-48,86-91` | implemented |
| 3 | Autosave, crash recovery, increment-and-save, and open-time repair of out-of-range project values | `crates/engine/src/autosave.rs`; `docs/preferences.md:45-49`; `crates/project/src/limits.rs:16-29`; `crates/engine/src/commands/file.rs:49-65,114-119` | implemented |
| 4 | Render Queue writes 13 formats: H.264, HEVC, AV1, ProRes, uncompressed MOV, WebM, PNG/JPEG/TIFF/EXR sequences, GIF, WAV, AIFF | `crates/project/src/render_queue.rs:499-545` | implemented |
| 5 | Lottie import/export for `.json` and `.lottie`, with a warnings list for inexpressible features | `crates/engine/src/commands/lottie.rs:9-51`; `crates/lottie/src/lib.rs:1-20` | implemented |
| 6 | Timeline interchange in FCP7 XML, FCPXML, OTIO, EDL, AAF and OMF; native `.prproj` explicitly rejected; optional ProRes 4444 pre-render | `crates/interchange/src/lib.rs:1-18,66-72`; `crates/engine/src/commands/timeline.rs:25-31,132-150` | implemented (pre-render fidelity depends on `prerender`) |
| 7 | 307 registered effects, 3032 parameters, 280 GPU-capable, all 32-bit float, 21 categories, 0 marked partial | `docs/effects.md:6-10`; `crates/effects/src/lib.rs:485-529`; `crates/engine/src/commands/query.rs:181-202` | implemented |
| 8 | 38 blend modes and 9 Layer Styles plus Blending Options/Global Light | `crates/color/src/blend.rs:52`; `crates/project/src/styles.rs:1-40` | implemented |
| 9 | Layer kinds and 3D: footage, precomp, solid, text, shape, null, camera, light, 3D model, primitive; Classic 3D and Advanced 3D renderers | `crates/project/src/lib.rs:335-339,600-607,655-714`; `crates/gpu/src/lib.rs:1-20` | implemented |
| 10 | Keyframes (linear/Bezier/hold, ease/velocity, roving), Graph Editor, time remap/stretch/reverse/freeze | `crates/keyframe/src/lib.rs:23-46,429-437`; `crates/engine/src/commands/prop.rs:1288-1310`; `crates/engine/src/commands/layer_time.rs:1-4,253` | implemented |
| 11 | JavaScript expressions with the AE object model, and `.jsx`/`.js` scripting with ScriptUI panels | `crates/expr/src/lib.rs:1-25`; `crates/script/src/lib.rs`; `docs/scripting-parity.md:15-33` | implemented; partial vs AE (no `.jsxbin`, startup/shutdown scripts, script shortcuts) |
| 12 | Motion/mask/face tracking, Warp Stabilizer, 3D Camera Tracker, Roto Brush, Object Matte, Content-Aware Fill, Auto-trace | `crates/engine/src/commands/{mask_interp,warp_cmds,camera_cmds,roto_cmds,content_fill,autotrace}.rs`; `crates/engine/src/models.rs:404-453` | implemented (AE fidelity unmeasured) |
| 13 | GPU compositor on wgpu (Metal/Vulkan/Direct3D 12/WebGPU); CPU reference; app defaults to GPU, headless CLI to CPU | `crates/gpu/src/lib.rs:1-34`; `docs/architecture.md:266-277`; `apps/effectcraft-cli/src/main.rs:350-371` | implemented |
| 14 | CLI with 12 subcommands and JSON output, headless by default | `apps/effectcraft-cli/src/main.rs:1-38,92-192` | implemented |
| 15 | MCP server with 36 tools (27 headless, 9 bridge-only) and two resources | `crates/automation/src/tools.rs:93-105,542-980`; `docs/mcp.md:3-52` | implemented |
| 16 | Localhost JSON control channel for the live UI, no authentication | `apps/effectcraft/src/control_server.rs:27`; `docs/control-protocol.md:9-25` | implemented |
| 17 | WebAssembly build with browser storage and `window.effectcraft` | `apps/effectcraft-web`; `docs/web.md:1-20,379-410` | implemented (not the installed macOS app) |
| 18 | `.aep` / `.aepx` import | `README.md:227`; `docs/file-format-parity.md:21-26`; no reader found by `rg` over `crates/` and `apps/` | **not implemented** |
| 19 | After Effects SDK plug-ins, `.ffx` presets, `.mogrt` templates | `README.md:228`; `docs/plugins.md:12-23`; `docs/file-format-parity.md:27-29` | **not implemented** (only `.wasm` plug-ins and `.ecpreset`/`.ectemplate`) |
| 20 | Hardware video decode/encode and pro output formats (16-bpc, AVI, MXF, DNxHR, DPX/TGA/PSD sequences, ProRes RAW) | `docs/gaps.md:74,81`; `docs/file-format-parity.md:99-106` | **not implemented / partial** (pure-Rust encoders only) |

## Docs-vs-code discrepancies at this tag

| Claim in docs | What the code shows | Evidence |
|---|---|---|
| `docs/gaps.md` gap 18: "no relink when a project moves" | `footage.relink`, `file.relinkFootage`, and automatic moved-project candidate search exist | `crates/engine/src/commands/relink_moved.rs:1-18`; `relink.rs:184-190` |
| `README.md` advertises 306 effects | Registry and `app.capabilities` report 307 | `README.md:121`; `docs/effects.md:6`; `crates/engine/src/commands/query.rs:181-202`; `crates/effects/src/lib.rs:485-529` |
| Bundle declares a QOI image type | `STILL_EXTENSIONS` does not include `qoi`; no code path references it | `packaging/macos/Info.plist.in:112-123`; `crates/media/src/lib.rs:62-63` |

## Environment checks

| Check | Result | Evidence |
|---|---|---|
| Installed version / build | 0.11.1, commit `2a01226894c6bc58ae4fadcc24a10198d693acaa` | `/Applications/EffectCraft.app/Contents/Info.plist` (`CFBundleShortVersionString`, `EffectCraftBuildCommit`) |
| Architecture / minimum OS | universal `x86_64` + `arm64`; macOS 11.0 | `file` on `Contents/MacOS/EffectCraft`; `LSMinimumSystemVersion` |
| CLI inside the bundle | absent — only `EffectCraft` in `Contents/MacOS` | bundle listing; `docs/agents.md` macOS row |
| GUI launched during authoring | no | — |

## How to spot-check

```sh
git rev-parse HEAD
rg -n "pub const SCHEMA_VERSION|SCHEMA_VERSION" crates/project/src/lib.rs
rg -n "pub const ALL: \[OutputFormat; 13\]" crates/project/src/render_queue.rs
rg -n "307 registered|307 effects" docs/effects.md crates/engine/src/commands/query.rs
rg -n "name: \"|bridge_only: true" crates/automation/src/tools.rs
rg -n "aep|aepx|mogrt|ffx" crates apps --glob '!**/tests/**'
```
