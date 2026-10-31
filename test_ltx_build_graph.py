"""The LTX 2.3 graph builder in the tsws-shot-prompt skill.

It writes a ComfyUI API prompt, so the test runs the script as a process and
reads the JSON back. It pins the two LTX constraints the pod refuses silently
(frames 8k plus 1, sides divisible by 32), the two anchor paths (a still
through LTXVImgToVideoInplace, a nine frame guide through LTXVAddGuide at
frame_idx 0 at both stages), the last-frame guide index, and that every edge
in the graph points at a node that exists.
"""
import json
import pathlib
import subprocess
import sys

SCRIPT = pathlib.Path(__file__).resolve().parent / ".claude/skills/tsws-shot-prompt/scripts/ltx_build_graph.py"


def build(tmp_path, *args):
    out = tmp_path / "graph.json"
    out.unlink(missing_ok=True)
    proc = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), str(out), "--prompt", "p", *args],
        capture_output=True, text=True, timeout=60,
    )
    return proc, (json.loads(out.read_text())["prompt"] if out.exists() else None)


def edges(graph):
    for nid, node in graph.items():
        for key, value in node["inputs"].items():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
                yield nid, key, value[0], value[1]


def test_frames_must_be_8k_plus_1(tmp_path):
    proc, graph = build(tmp_path, "--first", "a.png", "--frames", "240")
    assert proc.returncode != 0 and graph is None
    assert "8k + 1" in proc.stderr


def test_sides_must_divide_by_32(tmp_path):
    proc, graph = build(tmp_path, "--first", "a.png", "--height", "1080")
    assert proc.returncode != 0 and graph is None
    assert "divisible by 32" in proc.stderr


def test_one_anchor_path_only(tmp_path):
    proc, graph = build(tmp_path, "--first", "a.png", "--first-frames", *["f%d.png" % i for i in range(9)])
    assert proc.returncode != 0 and graph is None
    assert "not both" in proc.stderr
    proc, graph = build(tmp_path)
    assert proc.returncode != 0 and graph is None
    assert "not both" in proc.stderr


def test_two_stage_needs_sides_divisible_by_64(tmp_path):
    # 1280x736 is divisible by 32 but its half size 640x368 is not
    proc, graph = build(tmp_path, "--first", "a.png", "--width", "1280", "--height", "736")
    assert proc.returncode != 0 and graph is None
    assert "divisible by 64" in proc.stderr
    proc, graph = build(tmp_path, "--first", "a.png", "--width", "1280", "--height", "736", "--single-stage")
    assert proc.returncode == 0, proc.stderr
    assert graph["20"]["inputs"]["width"] == 1280 and graph["20"]["inputs"]["height"] == 736


def test_many_guide_frames_keep_distinct_node_ids(tmp_path):
    frames = ["g%03d.png" % i for i in range(33)]
    proc, graph = build(tmp_path, "--first-frames", *frames, "--frames", "225")
    assert proc.returncode == 0, proc.stderr
    loads = [n for n in graph.values() if n["class_type"] == "LoadImage"]
    batches = [n for n in graph.values() if n["class_type"] == "ImageBatch"]
    assert len(loads) == 33 and len(batches) == 32
    assert [n["inputs"]["image"] for n in loads] == frames
    proc, graph = build(tmp_path, "--first-frames", *["g%03d.png" % i for i in range(105)], "--frames", "225")
    assert proc.returncode != 0 and graph is None
    assert "at most 97" in proc.stderr


def test_guide_frames_must_be_8k_plus_1(tmp_path):
    proc, graph = build(tmp_path, "--first-frames", *["f%d.png" % i for i in range(8)])
    assert proc.returncode != 0 and graph is None
    assert "8k + 1" in proc.stderr


def test_still_anchor_uses_inplace_at_both_stages(tmp_path):
    proc, graph = build(tmp_path, "--first", "a.png", "--last", "z.png", "--frames", "241", "--seed", "7")
    assert proc.returncode == 0, proc.stderr
    assert graph["21"]["class_type"] == "LTXVImgToVideoInplace" and graph["21"]["inputs"]["strength"] == 0.7
    assert graph["41"]["class_type"] == "LTXVImgToVideoInplace" and graph["41"]["inputs"]["strength"] == 1.0
    assert graph["12"]["class_type"] == "LTXVPreprocess" and graph["12"]["inputs"]["image"] == ["10", 0]
    assert graph["10"]["inputs"]["image"] == "a.png"
    assert "19" not in graph and "39" not in graph
    for nid in ("22", "42"):
        assert graph[nid]["class_type"] == "LTXVAddGuide"
        assert graph[nid]["inputs"]["frame_idx"] == 240 and graph[nid]["inputs"]["image"] == ["15", 0]
    assert graph["20"]["inputs"] == {"width": 960, "height": 544, "length": 241, "batch_size": 1}
    assert graph["31"]["class_type"] == "LTXVCropGuides" and graph["31"]["inputs"]["latent"] == ["30", 0]
    assert graph["49"]["class_type"] == "LTXVCropGuides" and graph["49"]["inputs"]["latent"] == ["48", 0]
    assert graph["40"]["inputs"]["samples"] == ["31", 2] and graph["60"]["inputs"]["samples"] == ["49", 2]
    assert graph["25"]["inputs"]["noise_seed"] == 7 and graph["44"]["inputs"]["noise_seed"] == 8
    assert graph["27"]["inputs"]["sigmas"] == "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"
    assert graph["45"]["inputs"]["sigmas"] == "0.85, 0.7250, 0.4219, 0.0"
    assert graph["28"]["inputs"]["cfg"] == 1.0 and graph["46"]["inputs"]["cfg"] == 1.0
    assert "63" not in graph
    assert not any(n["class_type"] == "ResizeImageMaskNode" for n in graph.values())


def test_frame_guide_chains_nine_frames_and_guides_at_zero(tmp_path):
    frames = ["seg1_%05d_.png" % i for i in range(233, 242)]
    proc, graph = build(tmp_path, "--first-frames", *frames, "--frames", "225", "--last", "z.png", "--save-frames")
    assert proc.returncode == 0, proc.stderr
    loads = [n for n in graph.values() if n["class_type"] == "LoadImage" and n["inputs"]["image"] in frames]
    assert [n["inputs"]["image"] for n in loads] == frames
    batches = [nid for nid, n in graph.items() if n["class_type"] == "ImageBatch"]
    assert len(batches) == 8
    last_batch = ["308", 0]
    assert graph["308"]["inputs"]["image2"] == ["108", 0]
    assert "21" not in graph and "41" not in graph and "12" not in graph
    for nid in ("19", "39"):
        assert graph[nid]["class_type"] == "LTXVAddGuide"
        assert graph[nid]["inputs"]["frame_idx"] == 0 and graph[nid]["inputs"]["strength"] == 1.0
        assert graph[nid]["inputs"]["image"] == last_batch
    assert graph["22"]["inputs"]["frame_idx"] == 224 and graph["42"]["inputs"]["frame_idx"] == 224
    # the guide's conditioning feeds the end guide, which feeds the sampler
    assert graph["22"]["inputs"]["positive"] == ["19", 0] and graph["22"]["inputs"]["latent"] == ["19", 2]
    assert graph["28"]["inputs"]["positive"] == ["22", 0] and graph["24"]["inputs"]["video_latent"] == ["22", 2]
    assert graph["42"]["inputs"]["positive"] == ["39", 0] and graph["46"]["inputs"]["positive"] == ["42", 0]
    assert graph["63"]["class_type"] == "SaveImage"


def test_every_edge_points_at_a_node(tmp_path):
    for args in (["--first", "a.png", "--last", "z.png"],
                 ["--first", "a.png"],
                 ["--first-frames", *["f%d.png" % i for i in range(9)]],
                 ["--first", "a.png", "--single-stage"]):
        proc, graph = build(tmp_path, *args)
        assert proc.returncode == 0, proc.stderr
        for nid, key, target, slot in edges(graph):
            assert target in graph, (nid, key, target)
            assert isinstance(slot, int)
