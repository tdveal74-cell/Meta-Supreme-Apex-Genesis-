# tsws-ltx23-serverless: the Comfy Build definition for the Episode 1 motion lane

Ruled by Tee on 2026-11-03 on the tenth post-merge card: repairs run on the VPS
Kling API nodes, new motion runs on a Comfy Build release of LTX 2.3 deployed
serverless. This directory holds the build definition, written by hand from
the pod lane's own job record, because the only ComfyUI install the estate owns (`/opt/comfyui-tsws/ComfyUI` on
`srv1936199`) is CPU only and holds no model weights.

## What is in it

Three models, each by a public `https` source and the sha256 the pod lane
verified on download (`.claude/skills/tsws-shot-prompt/references/LTX23_pod_jobs_2026-10-31.md`,
the weights table, `hash_verified: true` on both pods). On 2026-11-03 the
Hugging Face tree API (`/api/models/<repo>/tree/main?recursive=true`) returned
the same three digests as the files' LFS `oid` values, so the source and the
digest come from the same party:

| type | file | bytes | source |
|---|---|---|---|
| `checkpoints` | `ltx-2.3-22b-distilled-1.1.safetensors` | 46,149,345,334 | `Lightricks/LTX-2.3` |
| `text_encoders` | `gemma_3_12B_it.safetensors` | 24,379,468,890 | `Comfy-Org/ltx-2`, `split_files/text_encoders/` |
| `latent_upscale_models` | `ltx-2.3-spatial-upscaler-x2-1.1.safetensors` | 995,743,560 | `Lightricks/LTX-2.3` |

No custom nodes. `scripts/ltx_build_graph.py` in the `tsws-shot-prompt` skill
emits core node classes only (`LTXVImgToVideoInplace`, `LTXVAddGuide`,
`LTXVCropGuides`, `LTXVLatentUpsampler`, `LTXAVTextEncoderLoader`,
`SamplerCustomAdvanced`, `VAEDecodeTiled`, `CreateVideo`, `SaveVideo` and
their neighbours), all of which ship in upstream ComfyUI; `comfy_extras/nodes_lt.py`
at v0.42.0 on the VPS defines fifteen `LTXV` classes, read 2026-11-03.

No pip pins. The `comfy-build` skill says to cut the first build with
`pipDependencies` emptied, and the authoring skill says that on a definition
with no custom node the answer is usually nothing at all.

`baseComfyVersion` is `v0.42.0`, the version the VPS install reports. The pod
lane ran v0.30.0 inside `runpod/comfyui:1.3.3-comfyuiv0.30.0-cuda13.0`; the
graph's node classes exist in both. Whether the builder's catalog carries
`v0.42.0` as a base is read with `comfy build refs base-images` and
`build-targets`, which need a sign-in.

## Licence

LTX-2 Community License Agreement, read 2026-10-31 (the job record above):
commercial use allowed under $10M annual revenue; machine-generated content
must be disclaimed as such; no impersonation without consent. The AI
disclosure sits on the episode's publish gate (TSWS 01 Post-Production Master,
version `4810d159`). The performers' consent for generated motion of their
likeness is the D9-A addenda, drafted and awaiting signature.

## How it is used, and what each step costs

Every step that touches the builder runs on `srv1936199` with the comfy.org key
read from `/root/.config/comfy/api_key` (mode 600, created by Tee), never from
this repository or a chat. The key is passed as `COMFY_CLOUD_API_KEY` on the
command line of one process and is never printed.

1. `comfy build validate <this dir>`: offline, spends nothing.
2. `comfy build refs base-images`, `build-targets`, `model-dirs`: reads, need the
   key, spend nothing. Confirm `v0.42.0`, `linux/nvidia` and the three `type`
   folders before any cut.
3. `comfy build push <this dir>`: saves the definition to platform.comfy.org;
   with no local upload there is nothing to send but the definition.
4. `comfy build release create <this dir> --target linux/nvidia --watch`:
   commits a release and spends one release slot. A slot is a count; nothing
   on the build surface bills by time. Three cuts, then stop. Asked on a card first.
5. `comfy deploy refs compute`, then `comfy deploy up <this dir> --gpu <class>
   --region <region> --min 0 --max 1`: bills by time from the moment the
   deployment serves. `--min 0` scales to zero between jobs and pays a cold
   start per job. The GPU class, region and price go on a card before `up`.
6. `comfy deploy run` or the SDK against the deployment's URL: each run is a
   fresh billed job; a resubmit is a second charge. One card per shot, with the
   estimate, as the Kling lane has.
7. `comfy deploy stop` after each batch: keeps the endpoint and the staged
   models and stops the bill.

Nothing in this directory runs on its own; it is read by the CLI when a person
passes its path.
