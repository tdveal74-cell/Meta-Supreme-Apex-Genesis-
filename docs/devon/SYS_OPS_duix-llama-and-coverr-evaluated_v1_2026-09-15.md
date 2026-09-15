# Duix, the llama script writer and Coverr, evaluated and none installed

Date: 2026-09-15. Supersedes nothing. First status doc on all three.

Tee asked for three things in one session: go to the Duix repository and
install it, check the llama repository for a script writer, and install the
Coverr repository. Nothing was installed. Duix is real and is the right tool
for the avatar work, but it cannot run on any machine this estate currently
has. The llama script writer exists and is a step down from what the estate
already runs. Coverr is not a repository at all.

## Duix, which is real and is blocked on hardware

`https://github.com/duixcom/Duix.Heygem.git` redirects to Duix.Avatar; both
remotes answer with the same head, `1328feb5` on `main`. Cloned clean at depth
one. It is an Electron desktop client plus three Docker services, and the
project's own framing is offline avatar and voice cloning on a Windows or
Ubuntu 22.04 desktop.

The hardware floor is stated in the README and it is not soft. Windows 10
19042.1526 or higher, or Ubuntu 22.04; 32 GB of memory called necessary; an
RTX 4070 as the recommended card; more than 100 GB free for the images and
more than 30 GB again for project data; an NVIDIA driver plus the NVIDIA
Container Toolkit, with `nvidia-ctk runtime configure`.

Two measurements decide it, and both were taken today rather than assumed.

First, every one of the four compose files in `deploy/` pins the NVIDIA
runtime on every service it defines: `docker-compose.yml` and
`docker-compose-linux.yml` three each, `docker-compose-5090.yml` two, and
`docker-compose-lite.yml` one. The file named lite is not a lower tier, it is
the same GPU service on its own. There is no GPU free path in the repository.

Second, all three images are single architecture, amd64 only, read from the
Docker Hub tags API:

| image | architecture | compressed size |
|---|---|---|
| `guiji2025/duix.avatar` | amd64, linux | 5.00 GB |
| `guiji2025/fun-asr` | amd64, linux | 15.23 GB |
| `guiji2025/fish-speech-ziming` | amd64, linux | 20.49 GB |

No arm64 variant is published for any of them. That matters more than the GPU
line, because an ARM host does not run these images slowly, it does not run
them at all.

This container cleared none of it. `nvidia-smi` is not installed, `df` reports
29 GB available against a 100 GB floor, and the egress policy denies the
Docker CDN outright: the proxy logged `connect_rejected`, gateway answered 403
to CONNECT, for `production.cloudfront.docker.com:443` at 11:01Z. So the pull
was never possible here on three independent counts.

`HARDWARE.md` section 5 already refuses this shape in general terms: no GPU,
inference is a provider's problem, and a code path that needs a local GPU
belongs behind an API. Duix happens to satisfy that second clause. After the
Docker services start it exposes a plain HTTP surface: synthesis at
`127.0.0.1:18180/v1/invoke`, video submission at `127.0.0.1:8383/easy/submit`
and progress at `/easy/query?code=`. So the estate pattern for adopting it is
the one `deploy/render-worker` already uses, a worker on its own box driven
over HTTP, and no part of Duix would ever be imported into this repository.

### The Oracle box, unresolved

Tee asked whether it can run on his Oracle box. The estate does record an
Oracle host: `129.80.78.29:8080`, a FastAPI service answering validation
errors on GET, which the 09-15 watched run names as the old json2video style
render worker, and which ruling 4 that day moved the render path away from in
favour of the VPS adapter at `172.16.2.1:8081`. A second Oracle address,
`150.136.200.85`, serves the five music tracks that `Build Movie` embeds.

Nothing in the estate records that box's architecture, memory, disk or
whether it has a GPU, and it cannot be probed from this session: the egress
policy denies raw IP addresses, answering `x-deny-reason: host_not_allowed`.
So the question is open and the check belongs to Tee, on the box:

```
uname -m && nproc && free -g | head -2 && df -h / | tail -1 && (nvidia-smi -L || echo "NO GPU")
```

`aarch64` ends it, because no arm64 image exists. `x86_64` with a listed
NVIDIA device and 100 GB free is the only green light. Oracle's two free
shapes are Ampere A1, which is ARM, and E2.1.Micro, which is amd64 with 1 GB
of memory; neither has a GPU, and a paid GPU shape needs a service limit
increase. The inference from the free tier being the common case is that the
answer is no, but that is an inference and the command above is the fact.

### The licence, worth reading before any of this is bought

The repository carries `Duix.Avatar model community Licensing Agreement.pdf`
and its Chinese counterpart, and the README claims global free commercial use
with a signed agreement required above 100,000 users or ten million US dollars
of annual revenue. Neither PDF was read in this arc. That reading is a
prerequisite to spending money on hardware for it, not a follow up.

## The llama script writer, found and not recommended

`meta-llama/llama-cookbook` carries `end-to-end-use-cases/NotebookLlama/`, an
open version of NotebookLM in four notebooks: a 1B model cleans a PDF, a 70B
model writes a two speaker podcast transcript, an 8B model rewrites it with
interruptions and drama, and `parler-tts-mini-v1` with `bark/suno` speak it.
Its own README states the requirement as a GPU server or an API provider, and
about 140 GB of aggregated memory to run the 70B in bfloat16.

The recommendation is to decline it, and the reason is fit rather than
quality. Its output target is a generic two host explainer podcast. The estate
already runs `tsws-canonical-script-writer`, `cinematic-script`,
`script-doctor` and `content-system`, which are built to Tee's voice, to the
TSWS arc and to characters voiced under recorded consent. Swapping a tuned
lane for a generic one, and paying 140 GB of GPU for the privilege, is a step
backwards. The one part worth taking is the Step 3 pattern, a second pass
whose only job is to add interruption and texture to an already correct
transcript, which is a prompt shape and not a dependency.

The estate's only existing hit for llama is unrelated: `llama-text-embed-v2`,
the Pinecone embedding model named in the Soul index setup. There is no Meta
llama code anywhere in this repository.

Separately, the 06:00 Script Writer schedule already exists inside TQO FINAL
V5 and is one of the six disabled triggers. The estate does not lack a script
writer lane. It lacks a funded key on the one it has.

## Coverr, which is not a repository

There is no Coverr repository to install. A GitHub search returns 93 matches
for the name and none of them is the thing: an R package for covering point
cloud data, a WPF album art widget, a Julia range library, a handful of
student HTML pages. Coverr is `coverr.co`, a stock footage website with a REST
API, so the only real work available is an integration, not an installation.

That integration was not built, because its contract could not be read. The
egress policy denies the host: the proxy logged `connect_rejected`, gateway
answered 403 to CONNECT, for `coverr.co:443` at 11:03Z, and the proxy's own
README instructs that policy denials are reported rather than retried. Writing
an adapter against an API whose shape was guessed is the precise failure this
repository's first law names, so it was refused.

One correction to the framing the question was put in. The render lane is not
missing a b roll source. It has a working one: Pexels, which answered on
execution 46 yesterday with `Build Movie` returning 45 clips, 0 from the
retired pool and 0 held. Coverr would be a second source beside a lane that
already works, so the case for it has to be that Pexels clips are the wrong
look, which is a judgement about footage and belongs to Tee, not a gap in the
pipeline.

## DEVON RECEIPT

```
AREA: Systems, TQO
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_duix-llama-and-coverr-evaluated_v1_2026-09-15
DATE: 2026-09-15
DECISIONS: none ruled by Tee within this arc; he chose the Coverr b roll integration from a card and asked whether Duix could run on his Oracle box, and both answers came back blocked rather than done. The decisions taken inside the arc were mine and there were three. I refused to install Duix anywhere, because no machine in the estate clears its floor and the container denied the image pull on policy regardless. I refused to write the Coverr adapter, because the host is denied by the egress policy and the API contract could not be read, and coding against a guessed contract is the failure mode the first law names. I recommended declining the llama NotebookLlama script writer on fit, because the estate already runs voice tuned script skills and NotebookLlama wants about 140 GB of aggregated GPU memory to produce a generic two host explainer. If Tee overrules on Coverr, the honest order is his API key and one recorded response body first, adapter second.
FINDINGS: duixcom/Duix.Heygem redirects to Duix.Avatar with both remotes at head 1328feb5 on main, cloned at depth one today; all four compose files under deploy pin runtime nvidia on every service they define, three in docker-compose.yml, three in docker-compose-linux.yml, two in docker-compose-5090.yml and one in docker-compose-lite.yml, so the file named lite is the same GPU service alone and no GPU free path exists in the repository; all three images are single architecture amd64 linux with no arm64 variant published, guiji2025/duix.avatar at 5.00 GB compressed, guiji2025/fun-asr at 15.23 GB and guiji2025/fish-speech-ziming at 20.49 GB, read from the Docker Hub tags API, which makes an ARM host a hard stop rather than a slow one; the README floor is Windows 10 19042.1526 or Ubuntu 22.04, 32 GB memory called necessary, an RTX 4070 recommended, over 100 GB plus 30 GB of disk and the NVIDIA Container Toolkit; this container has no nvidia-smi, 29 GB available and a policy denial on production.cloudfront.docker.com:443 logged at 11:01Z, so the pull failed on three independent counts; Duix does expose the HTTP surface HARDWARE.md section 5 requires of a GPU path, synthesis on 18180/v1/invoke and video on 8383/easy/submit with progress on /easy/query, so the adoption pattern would be a worker box driven over HTTP like deploy/render-worker and never an import into this repository; the Oracle host 129.80.78.29:8080 is recorded in the estate as the old json2video style render worker that ruling 4 on 2026-09-15 moved the render path away from toward the VPS adapter at 172.16.2.1:8081, with 150.136.200.85 serving the five Build Movie music tracks, but no record anywhere states that box's architecture, memory, disk or GPU and it cannot be probed from here because the egress policy denies raw IPs with x-deny-reason host_not_allowed; meta-llama/llama-cookbook carries end-to-end-use-cases/NotebookLlama as four notebooks running Llama-3.2-1B, Llama-3.1-70B and Llama-3.1-8B into parler-tts-mini-v1 and bark/suno, its README stating a GPU server or API provider and about 140 GB aggregated memory for the 70B in bfloat16; the estate's only llama string is the unrelated Pinecone model llama-text-embed-v2 in the Soul index setup and no Meta llama code exists in this repository; a 06:00 Script Writer schedule already exists in TQO FINAL V5 among the six disabled triggers, so the estate lacks a funded key rather than a script writer lane; Coverr has no repository, a GitHub search returning 93 unrelated matches led by an R point cloud package and a WPF album art widget, and coverr.co:443 is denied by the egress policy with connect_rejected logged at 11:03Z so its API contract could not be read; and the render lane already has a working b roll source in Pexels, which answered on execution 46 on 2026-09-15 with Build Movie returning 45 clips, 0 from the retired pool and 0 held, so Coverr would be a second source beside a working one rather than a gap being filled.
OPEN: the Oracle box's shape is unknown and decides whether Duix is possible at all, settled by running uname -m with nproc, free -g, df -h / and nvidia-smi -L on that box, where aarch64 ends it and x86_64 with a listed NVIDIA device and 100 GB free is the only green light; neither Duix licensing PDF was read and both must be before hardware is bought for it, because the README's commercial terms carry thresholds at 100,000 users and ten million US dollars of annual revenue; whether Tee wants Coverr as a second b roll source beside Pexels is a judgement about footage look that only he can make, and if he does it needs an API key and one recorded response body before any adapter is written; whether the NotebookLlama Step 3 dramatic rewrite prompt is worth lifting into the existing script skills is untested and not proposed here; and no hosted Duix API option at duix.com was priced or evaluated in this arc.
STATUS: filed, nothing installed and nothing shipped. This document is the only artifact in the arc. No dependency was added, no skill was vendored under .claude/skills, no compose file was copied into the repository, no n8n workflow was touched on either instance, and no estate code changed. Both clones, Duix.Avatar and llama-cookbook, were made under the session scratchpad and not into the repository. Every hardware and architecture number here is measured from the cloned files and the Docker Hub tags API rather than recalled; every network denial is quoted from the agent proxy's own status output. The Oracle box claim is explicitly not measured and is marked unverified above.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
