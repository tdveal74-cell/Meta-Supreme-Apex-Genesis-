# vision-inbox

The one directory `vision.describe` is allowed to read from.

Ruled 2026-09-16. Vision could have been pointed at the working tree or at the
render worker's output. It is pointed here instead, at a directory that holds
nothing but frames put there to be described, so that a bug which slips the
root guard, the traversal guard and the extension guard still has nothing
interesting to reach.

## Turning it on

Set `VISION_IMAGE_ROOT` to this directory's absolute path. Unset, the tool
refuses every call and says so, which is the shipped default: what writes into
this directory on a deployed container is a deployment decision.

```bash
export VISION_IMAGE_ROOT="$PWD/var/vision-inbox"
```

## What still refuses, with the root set

An absolute `image_path`, any path that climbs out of this directory, a file
extension outside `.jpg`, `.jpeg`, `.png`, `.webp` and `.gif`, a media type
outside that same set, and anything over `VISION_MAX_IMAGE_BYTES`. Approval is
separate and comes first: `vision.describe` is a WRITE tool that is not
reversible, so it stops at a human in both presence lanes before any of this
runs.

## Why nothing here is committed

Images in this directory are ignored by git. A frame is whatever was on a
screen when it was captured, which is the reason the tool is gated in the first
place, and this repository is public.
