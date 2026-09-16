# The owned presenter: MuseTalk lip sync over Tee's own footage

Ruled by Tee on 2026-09-15, on an inline card, after HeyGen answered 402
insufficient credit and Runway was found to have no avatar on record and no
credits either. The presenter for The Quiet Operator and NCO Forge is Tee's own
footage with the mouth driven to the cloned narration by MuseTalk, run on a
rented GPU per episode. Nothing here is rented as a persona: the face is Tee's,
the voice is Tee's clone, and the software is MIT licensed.

## Amended 2026-09-16: both routes are live, on purpose

Tee ruled on 2026-09-16, on an inline card, that HeyGen and MuseTalk both run
rather than one replacing the other. HeyGen avatar `1b799c8689a54ebcb6a55de37f92488c`
is the base track that unblocks episodes now; MuseTalk over his own recorded
footage stays the owned route and the recording session below stays on the plan.

This is not the 2026-09-15 ruling being forgotten. It is a deliberate second
route, and it is written here because the sentence above it says HeyGen is out
and a reader who stopped there would act on a fact that is one day stale.

`presenter_composite` in `deploy/render-worker/jobs.js` takes an `avatar` file
and does not care how it was made, so the base track is swappable and neither
route is thrown away by choosing the other today.

Still unverified and blocking the HeyGen half: that account answered 402
insufficient credit on 2026-09-15, and no HeyGen credential exists on the n8n
instance (`list_credentials` returns zero for it) or on the Railway `api` or
`presence` services. An avatar id is not access. Both the funding and the key
have to be confirmed before anything renders.

Nothing in this directory has been run yet. This container has no GPU, checked
on 2026-09-15 with `nvidia-smi` and `/dev/nvidia*`, both absent. The proof
below is the first thing that runs, on a rented pod, and Tee watches the
30 second file before anything is wired into the render lane.

## What was verified before this was written

| claim | where it was checked | what it said |
|---|---|---|
| MuseTalk code license | `TMElyralab/MuseTalk` LICENSE on GitHub, read 2026-09-15 | MIT, Tencent Music Entertainment Group, 2024 |
| MuseTalk weights | the README, same day | "available for any purpose, even commercially" |
| third party parts | the README | Whisper, the sd-vae, DWPose and face-alignment carry their own licenses (MIT, MIT, Apache 2.0, BSD 3-Clause by their bundled LICENSE files); read each before a commercial upload |
| smallest GPU the authors tested | the README | an RTX 3050 Ti laptop GPU with 4 GB, fp16, about 5 minutes for 8 seconds of video |
| speed on a real card | the README | 30 fps and above on a Tesla V100 |
| input the model wants | the README | a 256 by 256 face region, 25 fps video, one audio file |
| LatentSync as the alternative | `bytedance/LatentSync` LICENSE | Apache 2.0 for the code; the weights license on Hugging Face could not be read from this container (egress blocked), so it stays unverified and MuseTalk goes first |

Unverified and named as such: the quality of any of this on Tee's footage.
The known weakness of every audio driven lip sync model is teeth and the inner
mouth on a close, well lit face. The proof exists to measure that, not to
argue about it.

## Step one: the recording session (Tee, iPhone 15 Pro, about 20 minutes)

One session gives the presenter bank the render lane draws from for every
episode. Record 4K at 25 fps if the camera app offers it, otherwise 30 fps and
the worker conforms to 25. Landscape for the long form desk shot, then the same
takes in portrait for the stacked Shorts head zone.

- Light from the front, no window behind you. The mouth region is what the
  model redraws, so it needs to be lit and in focus.
- Frame from mid chest up, face about a third of the frame height. Larger than
  that and the 256 pixel face crop upsamples badly; smaller and the mouth loses
  detail.
- Take A, 90 seconds: talking. Read anything aloud, ideally a paragraph of a
  real script, at your normal pace. This is the take the model drives.
- Take B, 60 seconds: listening. Look at the lens, small natural movement, no
  talking. This covers gaps and cutaways.
- Take C, 60 seconds: talking with a hand gesture every ten seconds or so.
- Repeat A, B and C in portrait.
- Say the take letter on camera at the start of each take. Keep the originals;
  AirDrop or upload them to the Drive folder the render lane reads.

For the proof itself only take A landscape is needed, plus one narration line.

## Step two: the 30 second proof (Tee, rented GPU, under an hour)

Rent one pod on RunPod or Vast with an NVIDIA card of 16 GB or more (an A4000,
an L4 or a 4090 all clear it; the README's floor is 4 GB, the margin is for
speed). Pick the PyTorch 2.x CUDA 11.8 template. Open the pod's terminal and
run `musetalk-proof.sh` from this directory: it clones MuseTalk, installs the
pinned dependencies the README names, downloads the weights with the project's
own script, and runs `inference.sh v1.5 normal` on two inputs you upload first:

- `in/tee.mp4`, the first 30 seconds of take A
- `in/line.wav`, 30 seconds of the cloned narration (the S1E1 MP3 on Drive,
  converted with `ffmpeg -i s1e1.mp3 -t 30 -ar 16000 -ac 1 in/line.wav`)

The output lands under `out/`, named by MuseTalk itself; the script lists the
directory when it finishes. Download the file, watch it on the phone at full
brightness, then watch it again on the largest screen in the house. The
questions that decide the ruling:

1. Does the mouth match the words, including the closed lips on p, b and m?
2. Do the teeth hold their shape or do they smear?
3. Is there a visible seam around the mouth crop, especially at the jaw?
4. Does the rest of the face stay yours, or does it soften?

`bbox_shift` is the one knob. The README: positive values increase mouth
openness, negative values decrease it, the example range is minus 9 to 9. Run
the default first, then one pass each at minus 4 and plus 4 if the mouth is too
tight or too wide, and keep the one you would put on the channel.

If the answer to all four is yes at any setting, the presenter build wires
this in. If not, the next candidate is LatentSync 1.6 (Apache 2.0 code,
18 GB of VRAM by its README, weights license still to be read), and the
recording is reused as is.

## Step two, the free route, ruled 2026-09-15: Hugging Face Spaces

Tee ruled the same day, on an inline card, that until the 25th the proof runs
on Hugging Face's free shared GPU instead of a rented pod. Two public Spaces
already run the models this arc chose, and a free Hugging Face account gets a
daily allowance of ZeroGPU time. Checked on 2026-09-15 by reading each Space's
own files, not by running them: how much daily quota a free account has, and
whether a Space is awake when you open it, are unverified from this container.

The primary door is the MuseTalk 1.5 Space at
`huggingface.co/spaces/henrybit/musetalk-1-5`, MIT, pinned to MuseTalk commit
`0a89dec`, running the v1.5 UNet on ZeroGPU. Its app takes a driving audio
file and a reference image or video, exposes `bbox_shift`, `extra_margin`
(default 10), a `parsing_mode` of `jaw`, and left and right cheek widths
(default 90), and has a Test Inpainting button that runs the first frame only.
Its GPU reservation for a generate is 45 seconds plus 18 seconds per second
of media, capped at 600 seconds, so a 30 second clip sits at the cap: use 15
to 20 seconds of take A for the first proof and grow from there.

From the phone:

1. Sign up at huggingface.co (free), confirm the email, sign in.
2. Make the two inputs: 15 to 20 seconds of take A landscape as a small MP4
   (the phone's own trim in Photos is fine), and the same length of cloned
   narration as MP3 or WAV. Keep both under about 20 MB so the upload holds.
3. Open the Space. If it says Sleeping or Building, tap to wake it and wait;
   the first start downloads the weights and can take several minutes.
4. Upload the video as the reference and the narration as the driving audio.
5. Tap Test Inpainting. It draws the mouth box on the first frame. If the box
   misses the mouth, move `bbox_shift` by a few units and test again.
6. Tap Generate, wait, download the MP4, and watch it against the four
   questions in the pod steps above. Same verdict rule, same next step.

If the Space is asleep for good or the quota refuses the reservation, the
second free door is Meituan's own LongCat-Video-Avatar 1.5 demo at
`huggingface.co/spaces/meituan-longcat/LongCat-Video-Avatar-1.5-Demo`, MIT
weights, on ZeroGPU: one photo of you plus the narration plus a one line text
prompt returns a 5 second lip synced clip. It is a different model from the
one ruled, so a pass there is a signal, not the proof; it says whether a
still of you can carry a Short's head zone while MuseTalk is sorted out.

Not free routes, recorded so nobody reaches for them first: HeyGen's free
plan, D-ID's trial and Hedra's free credits all watermark or expire, and all
of them are a rented persona of Tee's face, which the identity ruling forbids.

## Step three, after the proof passes: the job shape

The render worker on the VPS has no GPU, so the lip sync runs as a remote job
the worker calls, the same way it calls the json2video style adapter today.
The planned job is `lipsync_remote` in `deploy/render-worker/jobs.js`:

- params: `video` (a take from the presenter bank), `audio` (the narration
  WAV), `bbox_shift` (default 0), `output`
- the worker posts both files to the GPU endpoint, polls, and downloads the
  result to `output`; it returns `{ output, seconds, endpoint, model:
  'musetalk-1.5' }` and refuses any endpoint that is not on an allowlist
- the result then feeds `presenter_composite` as its `avatar` input, so the
  existing full and stacked layouts, captions and ducked bed need no change

The endpoint is a RunPod serverless worker running the same MuseTalk install
this script builds, paid per second of GPU time. That is the near free part:
an episode of sixteen minutes at real time speed on a mid card is well under
an hour of GPU, which is on the order of a dollar at the community rates
seen on 2026-09-15. Pricing pages could not be fetched from this container,
so that number is Tee's to confirm on the RunPod console before the first
episode.

Not built yet: the job, the serverless endpoint, the allowlist, the tests.
They follow the proof, in that order, and each lands as its own small PR.
