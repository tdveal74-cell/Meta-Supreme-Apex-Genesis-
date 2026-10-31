# FilmCraft CLI, control channel and MCP — reference

Everything below is transcribed from the v0.9.0 source at commit `4a69a038…`. Nothing here is invented; where a
value comes from a doc rather than code, the path is given.

## 1. `filmcraft-cli`

Source of truth for the flags: the `HELP` const in `apps/filmcraft-cli/src/main.rs:53-121`. Parser:
`apps/filmcraft-cli/src/args.rs` (options may appear anywhere; `--` ends options; `-V` in the subcommand
position is a version query).

```
filmcraft-cli [OPTIONS] <SUBCOMMAND> [ARGS]

SUBCOMMANDS
  exec <id> [key=value ...]     run one command; prints its result as JSON
  exec <id> '<json params>'     same, params as one JSON object
  run <script.jsonl | ->        run commands, one {"id","params"} per line (# comments ok)
  commands [filter] [--json]    list commands (id, label, shortcut, params)
  describe <id>                 one command as JSON (menu, shortcut, params, enabled now)
  inspect [project|sequence]    project tree or active sequence as JSON (default: both)
  import <file>...              import media into the project
  export <out> [--preset name] [--format f] [--range r] [--start s --end s]
         [--settings json] [--gpu-rendering auto|off] [--scale f] [--quality 0-100]
         [--no-audio] [--queue] [--allow-offline]
  export --list-presets [query] list export presets (name, category, format) as JSON
  render --seconds S --out f.png [--scale 0.5] [--allow-offline]
  probe <media> [--image-sequence]      media info as JSON (MXF/Ogg/BWF/image-sequence details)
  bench-decode <media> [--frames N]
  mcp                                   MCP server on stdio (headless, or --bridge)
  help | --version

OPTIONS
  --project <p.fcproj>   open this project first (headless)
  --demo                 open the built-in demo project (headless)
  --save                 save the project back to --project when done
  --save-as <p.fcproj>   save to this path when done
  --bridge <127.0.0.1:PORT>  send commands to the running app (`filmcraft --control PORT`)
  --data-dir <dir>       FilmCraft data directory for user export presets (headless)
  --keep-going           `run`: report failing lines and continue
  --compact              one-line JSON output
```

Notes:

- Export formats accepted by `--format`: `h264|hevc|prores|dnxhr|apv|mjpeg|mxf-op1a|mxf-opatom|png|tiff|bmp|jpg|tga|dpx|exr|gif|wav|aiff|aac|flac`.
  Without `--format`, `--preset` wins; otherwise the format is guessed from the output extension
  (`mp4|m4v`→h264, `mov`→prores, `mxf`→mxf-op1a, `png`, `gif`, `wav`, `tif|tiff`, `bmp`, `aif|aiff`, `m4a|aac`) —
  `apps/filmcraft-cli/src/main.rs:204-219`. An unknown extension without `--format` is a usage error.
- `--start`/`--end` imply `range: "custom"` and are forwarded as `startSeconds`/`endSeconds`.
- `--no-audio` sets `audio: false`; `--queue` uses `export.queue.add` with `start: true` instead of a direct export.
- Exit status: `0` success; `1` a command failed, saving failed, or export/render drew offline media without
  `--allow-offline`; `2` usage error. A closed stdout (`| head`) is not an error: the remaining work still runs
  (`apps/filmcraft-cli/src/main.rs:123-141`, `:258-264`).
- `--bridge` refuses `--project`/`--demo` ("open projects there (exec file.open path=…)").
- `render` is headless-only; with `--bridge` use the MCP `render_frame` tool or `exec ui.*` commands.
- `mcp` accepts only `--bridge`, `--project`, `--demo`, `--data-dir`; any other option is a usage error.
- `probe` needs `--image-sequence` to treat its argument as the first numbered still of a sequence.

## 2. Desktop control channel

`filmcraft --control 9876` (or `FILMCRAFT_CONTROL_PORT=9876`) — loopback only, JSON object per line in,
one JSON reply per line out. Full table: `docs/control-protocol.md:24-43`; transport
`apps/filmcraft/src/control_server.rs`; handlers `crates/ui-egui/src/control.rs`.

| Method | Params | Notes |
|---|---|---|
| `engine.execute` / `ui.menu.invoke` | `{command, params}` | any engine or UI command id |
| `engine.commands` / `ui.menu.list` | – | registry / menu tree |
| `ui.inspect` | – | tool, workspace, dock, timeline view, playback, fps, settings draft, panels… |
| `ui.elements` | `{prefix?}` | every on-screen interactive element: id, label, rect |
| `ui.set` | `{tool, workspace, mode, theme, focused, playbackRes, timeline:{pps,scroll,fit,thumbnails}, program:{…}, source:{…}, clipDialog:{…}, menuDialog:{…}, panels:{scopes,timecode,reference,events,progress}, export:{…}, projectPanel:{…}, mediaBrowser:{…}, keyframeSelection:[…], settings, gfxTemplates, tts}` | merges into UI state |
| `ui.panel.show` / `ui.panel.close` | `{panel}` | |
| `ui.click` / `ui.move` | `{id}` or `{x,y}`, `button`, `count`, `modifiers` | synthetic pointer input |
| `ui.drag` | `{from, to, steps, modifiers}` | press–move–release |
| `ui.scroll` | `{id|x,y, dx, dy, modifiers}` | wheel/trackpad |
| `ui.key` / `ui.type` | `{key}` (`Cmd+K`, `Space`) / `{text}` | keyboard |
| `ui.timeline.hit` / `ui.timeline.locate` | `{x,y,modifiers?}` / `{clip, edge?}` | hit-testing; `kind` is the trim a press would start |
| `ui.playback` | `{action: play\|stop\|toggle, speed?}` | |
| `ui.screenshot` | `{path?, panel?}` | PNG of the window or one panel; fails after 10 s with no presented frame |
| `ui.resize`, `app.quit` | `{width,height}` / `{}` | `app.quit` quits without the save prompt (unsaved changes stay in the journal) |
| `ui.focus` | `{}` / `{id}` | `{}` activates the OS window; `{id}` focuses a widget |
| `perf.stats` | – | decode/playback/frames/monitor/ui/process counters (cumulative — diff two readings) |

Rules of thumb (`docs/control-protocol.md:9-17`, `:54-75`):

- A line that is not a JSON object with a string `method` gets one error reply and the connection is closed.
- Max 16 concurrent connections; **no authentication** — enable the port only while you need it.
- Started with `--control`, the app opens without activating itself and UI requests bring the window forward
  without making it key; only `ui.focus {}` activates it. `--control-input-only` (needs `--control`) ignores real
  keyboard, pointer, file drops and menu commands — the mode for unattended automation.
- Commands that act on a selection are disabled until something is selected, unless you name targets
  (`clips`/`clip`, `items`/`item`); naming targets leaves the selection alone.
- Tracks are ids or names (`"V1"`, `"A2"`); naming a missing track is an error, never a fallback track.

## 3. MCP server

`filmcraft-cli mcp` (stdio). Headless: `--demo` or `--project p.fcproj` (neither = empty project), plus
`--data-dir`. Bridge: `--bridge 127.0.0.1:9876` to the running app. `.mcp.json` in the repo registers both,
pointing at `target/release/filmcraft-cli`.

Tools (`crates/automation/src/server.rs:311-551`, `docs/agents.md:57-77`): `command_list`, `command_run`,
`command_batch`, `doc_inspect`, `render_preview`, `project_inspect`, `sequence_inspect`, `media_import`,
`render_frame`, `ui_inspect`, `ui_elements`, `ui_click`, `ui_drag`, `ui_key`, `ui_type`, `ui_screenshot`,
`ui_control`. Resources: `filmcraft://document`, `filmcraft://commands` (both `application/json`).

Behaviour worth relying on:

- Every tool carries `title` + `readOnlyHint`/`destructiveHint`/`idempotentHint`/`openWorldHint`.
- Unknown tool arguments are `-32602` errors naming the accepted ones; unknown lines are `-32700` and the
  server keeps serving; a panicking command is reported as `internal error: …` and the session stays usable.
- `command_run {"id": "file.exportMedia", "params": {…, "wait": true}}` blocks through progress/cancellation:
  `notifications/progress` with a `_meta.progressToken`, `notifications/cancelled` stops the encode and deletes
  the partial output. Without `wait` it returns `{job, path}` immediately — poll `jobs.list`, stop with
  `jobs.cancel`. `offlineMedia` and `etaSeconds` are reported on jobs and queue items.
- Headless MCP is **not** confined to a folder; any option other than the four above is rejected (exit 2).

Typical agent loop (`docs/agents.md:79-80`): `project_inspect` / `sequence_inspect` → ids → `command_run` →
`render_frame` or `ui_screenshot` → inspect → `edit.undo` if wrong.

## 4. Commands worth memorising

Project/media: `file.newProject`, `file.newSequence`, `file.import`, `file.importImageSequence`, `file.open`,
`file.save`/`file.saveAs`/`file.saveCopy`/`file.revert`, `file.listAutoSaves`, `file.recoveryList`,
`file.recover`, `file.projectManager`, `media.status`, `media.findMissing`, `media.relink`, `media.autoRelink`,
`media.search`, `media.makeOffline`, `media.createProxies`/`attachProxies`/`toggleProxies`,
`project.ingestSettings`.

Editing: `source.insert`, `source.overwrite`, `sequence.lift`, `sequence.extract`, `sequence.addEdit`,
`timeline.move`, `timeline.razor`, `timeline.place`, `edit.undo`, `edit.redo`, `edit.pasteInsert`,
`trim.selectEditPoint`, `trim.shuttle`, `trim.tick`, `trim.shuttleStop`, `clip.replaceFromBin`,
`clip.audioGain`, `markers.*`, `markers.exportCsv`.

Look/audio/text: `effects.list`, `effects.apply`, `effects.setParam`, `lumetri.setInputLut`,
`lumetri.setLook`, `lumetri.setSection`, `lut.import`, `mixer.*`, `clipMixer.set`, `essentialSound.*`,
`captions.*`, `transcript.*`, `tts.*`, `graphics.*`, `gfxTemplates.*`.

Output: `file.exportMedia`, `file.exportFrame`, `export.queue.add/start/list/stop/cancel/retry/remove/move/clear`,
`export.quick`, `export.presets.*`, `export.formats`, `export.resolve`, `jobs.list`, `jobs.cancel`,
`perf.stats`, `file.exportEdl`, `file.exportFcp7Xml`, `file.exportFcpxml`, `file.exportOtio`,
`file.exportAaf`, `file.exportOmf`, `file.exportAle`, `file.importAaf`.

UI/app: `tool.*`, `playback.*`, `view.*`, `window.workspace.*`, `window.panel.*`, `window.dockPanel`,
`window.floatPanel`, `window.dockAction`, `app.settings.<category>`, `prefs.get`/`prefs.set`/`prefs.reset`/
`prefs.schema`, `shortcuts.*`, `command.list`.

`file.exportMedia` parameters (from the registry, `crates/engine/src/commands.rs:1599-1607`):
`path` (required), `preset`, `settings` (ExportSettings JSON), `format`, `audioCodec: auto|aac|pcm|flac`,
`flacLevel`, `width`, `height`, `fps`, `bitrateKbps`, `bitrateMode: cbr|vbr1Pass|vbr2Pass|crf`, `crf`,
`hardwareEncoding: off|auto`, `scale`, `audio`, `quality`, `burnCaptions`, `alpha`, `exrCompression`,
`captionSidecar: srt|vtt`, `loudnessLufs`, `proresProfile`, `dnxProfile`, `apvProfile`, `mxfVideoCodec`,
`sequence`, `range: entire|inOut|workArea|custom`, `startSeconds`, `endSeconds`, `wait`.

## 5. Building (developers)

```sh
cargo build --release -p filmcraft -p filmcraft-cli   # app + CLI (packaging/macos/package.sh:61)
cargo run --release -p filmcraft -- --control 9876
cargo xtask ci        # fmt, lints, tests, layering, asset attribution, wasm check
cargo xtask web       # WebAssembly site into target/web/dist
cargo xtask parity    # menu/effects parity against a local plan/premiere reference
```

`CRAFT_FONTS_DIR=<craft-fonts checkout>` adds the shared font set (optional; official releases embed it —
`packaging/macos/package.sh`, `docs/web.md`). Release builds pass no `--features`, so `whisper` and
`neural-voices` are **off** in shipped binaries.
