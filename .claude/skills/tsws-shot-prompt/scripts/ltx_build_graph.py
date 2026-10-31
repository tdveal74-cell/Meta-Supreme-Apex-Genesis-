"""Build a ComfyUI API prompt for an LTX-2.3 shot on the owned A100 pod.

Mirrors the official Comfy-Org video_ltx2_3_i2v template: two stages, half
resolution with the 8 step distilled schedule, then the x2 latent upscaler and
a 3 step refine, with the last frame added as a guide at both stages. Inputs
are pre-conformed to the target size (1920x1088 for a 1080 shot), so there is
no resize node.

Two ways to anchor the start:
  --first IMG            one still, LTXVPreprocess then LTXVImgToVideoInplace
  --first-frames F1..Fn  8k+1 frames of a previous segment (model output, no
                         preprocess), batched and added with LTXVAddGuide at
                         frame_idx 0 at both stages, so motion carries across
                         the seam. The seam is then at the last of those frames.

Usage: python3 ltx_build_graph.py OUT.json (--first IMG | --first-frames F...) --prompt TEXT
       [--last IMG] [--negative TEXT] [--width 1920 --height 1088 --frames 241 --fps 24]
       [--seed 42] [--ckpt NAME] [--text-encoder NAME] [--upscaler NAME] [--prefix P]
       [--first-strength1 0.7] [--last-strength 1.0] [--single-stage] [--save-frames]

Limits the builder enforces: sides divisible by 32, and by 64 for the two stage
path because stage 1 runs at half size; frames 8k plus 1; guide frames 8k plus 1
and at most 97 of them.
"""
import argparse
import json

NEG = ("camera pan, camera zoom, camera drift, head turn toward camera, eye contact "
       "with lens, face morphing, identity change, duplicate people, masks slipping "
       "or disappearing, full-face masks, melting architecture, text, watermark, "
       "pc game, console game, video game, cartoon, childish, ugly")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--first")
    ap.add_argument("--first-frames", nargs="+")
    ap.add_argument("--last")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--negative", default=NEG)
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1088)
    ap.add_argument("--frames", type=int, default=241)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--ckpt", default="ltx-2.3-22b-distilled-1.1.safetensors")
    ap.add_argument("--text-encoder", default="gemma_3_12B_it.safetensors")
    ap.add_argument("--upscaler", default="ltx-2.3-spatial-upscaler-x2-1.1.safetensors")
    ap.add_argument("--prefix", default="shot")
    ap.add_argument("--first-strength1", type=float, default=0.7)
    ap.add_argument("--last-strength", type=float, default=1.0)
    ap.add_argument("--single-stage", action="store_true")
    ap.add_argument("--save-frames", action="store_true")
    a = ap.parse_args()

    assert a.width % 32 == 0 and a.height % 32 == 0, "LTX needs width and height divisible by 32"
    if not a.single_stage:
        assert a.width % 64 == 0 and a.height % 64 == 0, (
            "the two stage path runs stage 1 at half size, so sides must be divisible by 64 (or pass --single-stage)")
    assert (a.frames - 1) % 8 == 0, "LTX needs frames = 8k + 1"
    assert bool(a.first) != bool(a.first_frames), "give --first or --first-frames, not both"
    if a.first_frames:
        assert (len(a.first_frames) - 1) % 8 == 0, "guide frames must be 8k + 1"
        assert len(a.first_frames) <= 97, "at most 97 guide frames"
    last_idx = a.frames - 1

    g = {}

    def node(nid, ctype, **inputs):
        g[str(nid)] = {"class_type": ctype, "inputs": inputs}
        return str(nid)

    def out(nid, slot=0):
        return [str(nid), slot]

    node(1, "CheckpointLoaderSimple", ckpt_name=a.ckpt)
    node(2, "LTXAVTextEncoderLoader", text_encoder=a.text_encoder, ckpt_name=a.ckpt, device="default")
    node(3, "LTXVAudioVAELoader", ckpt_name=a.ckpt)
    node(4, "LatentUpscaleModelLoader", model_name=a.upscaler)
    node(5, "CLIPTextEncode", text=a.prompt, clip=out(2))
    node(6, "CLIPTextEncode", text=a.negative, clip=out(2))
    node(7, "LTXVConditioning", positive=out(5), negative=out(6), frame_rate=a.fps)

    guide_img = None
    if a.first:
        node(10, "LoadImage", image=a.first)
        node(12, "LTXVPreprocess", image=out(10), img_compression=18)
    else:
        prev = None
        for i, f in enumerate(a.first_frames):
            node(100 + i, "LoadImage", image=f)
            if prev is None:
                prev = out(100 + i)
            else:
                node(300 + i, "ImageBatch", image1=prev, image2=out(100 + i))
                prev = out(300 + i)
        guide_img = prev
    if a.last:
        node(13, "LoadImage", image=a.last)
        node(15, "LTXVPreprocess", image=out(13), img_compression=18)

    w1, h1 = (a.width, a.height) if a.single_stage else (a.width // 2, a.height // 2)
    node(20, "EmptyLTXVLatentVideo", width=w1, height=h1, length=a.frames, batch_size=1)
    pos, neg, lat = out(7, 0), out(7, 1), out(20)
    if a.first:
        node(21, "LTXVImgToVideoInplace", vae=out(1, 2), image=out(12), latent=lat,
             strength=1.0 if a.single_stage else a.first_strength1, bypass=False)
        lat = out(21)
    else:
        node(19, "LTXVAddGuide", positive=pos, negative=neg, vae=out(1, 2), latent=lat, image=guide_img,
             frame_idx=0, strength=1.0)
        pos, neg, lat = out(19, 0), out(19, 1), out(19, 2)
    if a.last:
        node(22, "LTXVAddGuide", positive=pos, negative=neg, vae=out(1, 2), latent=lat, image=out(15),
             frame_idx=last_idx, strength=a.last_strength)
        pos, neg, lat = out(22, 0), out(22, 1), out(22, 2)
    node(23, "LTXVEmptyLatentAudio", frames_number=a.frames, frame_rate=a.fps, batch_size=1, audio_vae=out(3))
    node(24, "LTXVConcatAVLatent", video_latent=lat, audio_latent=out(23))
    node(25, "RandomNoise", noise_seed=a.seed)
    node(26, "KSamplerSelect", sampler_name="euler")
    node(27, "ManualSigmas", sigmas="1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0")
    node(28, "CFGGuider", model=out(1, 0), positive=pos, negative=neg, cfg=1.0)
    node(29, "SamplerCustomAdvanced", noise=out(25), guider=out(28), sampler=out(26), sigmas=out(27), latent_image=out(24))
    node(30, "LTXVSeparateAVLatent", av_latent=out(29, 0))
    node(31, "LTXVCropGuides", positive=pos, negative=neg, latent=out(30, 0))
    final_video_latent = out(31, 2)

    if not a.single_stage:
        node(40, "LTXVLatentUpsampler", samples=out(31, 2), upscale_model=out(4), vae=out(1, 2))
        pos2, neg2, lat2 = out(31, 0), out(31, 1), out(40)
        if a.first:
            node(41, "LTXVImgToVideoInplace", vae=out(1, 2), image=out(12), latent=lat2, strength=1.0, bypass=False)
            lat2 = out(41)
        else:
            node(39, "LTXVAddGuide", positive=pos2, negative=neg2, vae=out(1, 2), latent=lat2, image=guide_img,
                 frame_idx=0, strength=1.0)
            pos2, neg2, lat2 = out(39, 0), out(39, 1), out(39, 2)
        if a.last:
            node(42, "LTXVAddGuide", positive=pos2, negative=neg2, vae=out(1, 2), latent=lat2, image=out(15),
                 frame_idx=last_idx, strength=a.last_strength)
            pos2, neg2, lat2 = out(42, 0), out(42, 1), out(42, 2)
        node(43, "LTXVConcatAVLatent", video_latent=lat2, audio_latent=out(30, 1))
        node(44, "RandomNoise", noise_seed=a.seed + 1)
        node(45, "ManualSigmas", sigmas="0.85, 0.7250, 0.4219, 0.0")
        node(46, "CFGGuider", model=out(1, 0), positive=pos2, negative=neg2, cfg=1.0)
        node(47, "SamplerCustomAdvanced", noise=out(44), guider=out(46), sampler=out(26), sigmas=out(45), latent_image=out(43))
        node(48, "LTXVSeparateAVLatent", av_latent=out(47, 0))
        node(49, "LTXVCropGuides", positive=pos2, negative=neg2, latent=out(48, 0))
        final_video_latent = out(49, 2)

    node(60, "VAEDecodeTiled", samples=final_video_latent, vae=out(1, 2), tile_size=768, overlap=64,
         temporal_size=4096, temporal_overlap=4)
    node(61, "CreateVideo", images=out(60), fps=a.fps)
    node(62, "SaveVideo", video=out(61), filename_prefix=f"video/{a.prefix}", format="auto", codec="auto")
    if a.save_frames:
        node(63, "SaveImage", images=out(60), filename_prefix=f"frames/{a.prefix}")

    json.dump({"prompt": g, "client_id": a.prefix}, open(a.out, "w"), indent=1)
    print(a.out, len(g), "nodes", f"{w1}x{h1}" + ("" if a.single_stage else f" then {a.width}x{a.height}"),
          a.frames, "frames", "guide" if a.first_frames else "still", "+last" if a.last else "")


if __name__ == "__main__":
    main()
