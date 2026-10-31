# SH150 hold, a living still in HyperFrames

The first HyperFrames composition written for The Shadow We Share, on 2026-10-31, after Tee asked for a route that costs nothing. It takes the registered SH150 conform (`SH150_FINAL_CONFORM_1920x1080.png`, sha256 `88c26e7559a3815a7cd481f9a0c97817d641951dd88272407c9279b2b6900505`, placed at `assets/SH150_conform.png`, not committed here) and renders twelve seconds of it with a 3.5 percent push over the whole length and seeded rain drawn as a pure function of timeline time. Nobody in the frame moves. It is the cheap route for the holds, titles and transitions of the episode, not for a new scene or still.

Measured on the first render: 288 frames at 1920x1080, 24 fps, 12.0 s, rendered in 37.9 s on a 4 core container with software GL, no account and no credits; `npx hyperframes check --json` clean on lint, runtime, layout and contrast. The push reads as a symmetric edge drift of about 28 px by the last frame on the skill's static regions, and the rain as 0.25 to 1.27 of frame to frame change in the sky. The output sha256 was `6c1e9d7bf61e90750ae9425ae1a2a6caf24eeb2598776f352f4ebb0e81061c56`.

To render it again:

```bash
npm install hyperframes@0.8.223          # Apache-2.0, Node 22 or later, FFmpeg on the path
mkdir -p assets && cp <the SH150 conform> assets/SH150_conform.png
HYPERFRAMES_BROWSER_PATH=/opt/pw-browsers/chromium HYPERFRAMES_NO_TELEMETRY=1 \
  npx hyperframes check --json && npx hyperframes render --quality looks --fps 24 --output renders/out.mp4
```

`HYPERFRAMES_BROWSER_PATH` points at any Chromium; the cloud container has one at that path. The two variables on `index.html`, `push` and `rain`, are what the HyperFrames desktop app or a batch render can change without touching the code. The composition follows the contract in the upstream `hyperframes` skill (one scene file inside `<template>`, a paused GSAP timeline registered under the scene id, no clocks or unseeded randomness, no CSS filters on footage).
