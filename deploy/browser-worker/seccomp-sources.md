Current optional public-proxy candidate is documented in README.md. The receipt below is historical offline sandbox evidence; it is not a claim that the current candidate is deployed.

# Per-container sandbox profile provenance

Reviewed on 2026-10-22. This is a candidate container policy, not a daemon setting.

- Baseline: [official Moby profiles default.json at 6fe7deb1b9fb7c0397a4593480d7d22b9ee8caef](https://github.com/moby/profiles/blob/6fe7deb1b9fb7c0397a4593480d7d22b9ee8caef/seccomp/default.json), commit dated 2026-09-17.
- Unmodified baseline bytes: `seccomp-moby-base.json`, SHA-256 `6416b47770785a41ac59073cdc77d9fe98517df2799dc83ef207e622de3053f6`.
- Namespace addition: [official Playwright Docker guidance](https://playwright.dev/docs/docker#crawling-and-scraping): allow `clone`, `setns`, `unshare` for nonroot Chromium user namespaces.
- Original [Playwright full profile](https://github.com/microsoft/playwright/blob/ae935a43d9e376e4759548f6b3c6905c7b282333/utils/docker/seccomp_profile.json) dates to 2021. We do not replace the modern Moby baseline with that old snapshot.
- Additional reviewed single `chroot` allow: [official Chromium sandbox credentials code](https://github.com/chromium/chromium/blob/main/sandbox/linux/services/credentials.cc), `ChrootToSelfFdinfo` calls `sys_chroot("/proc/self/fdinfo/")`. Current Moby conditional chroot rule requires an initial CAP_SYS_CHROOT; cap-drop-all removes that condition. The syscall allowance grants no initial capability: Linux checks CAP_SYS_CHROOT in the caller user namespace. This enables Chromium to confine its new user namespace. The syscall rule is not path-scoped and adds attack surface; no other baseline rule changes. Independent reviewer confirmed rationale before test.
- Baseline license is reproduced in `LICENSE.seccomp-moby`.

`node generate-seccomp.mjs` checks the exact baseline hash and produces
`seccomp-browser.json`. Its test verifies every baseline rule remains present,
including filtered socket creation; only the explicitly documented additions
may follow it. NNP, zero initial capabilities, read-only root, no host IPC/network,
no profile mounts and deny-all browser/network policy remain mandatory.

Build inputs are pinned to Node image manifest digest
`sha256:55fb5f5a527ea2c5c4a95f963e48ef90aa38c7b346054fdc8ee9957a2b55d205`
and Debian Chromium/common/sandbox `156.0.8078.47-1~deb12u1`. Apt repositories remain
external build dependencies; pins fail closed when packages disappear. Record the
resulting image ID/digest for each reviewed rollout and do not equate a Dockerfile
pin with proof of what a deployed host runs.

On 2026-10-23 a fresh GitHub build could not resolve the previous three
`155.0.8059.79-1~deb12u1` pins. Fresh signed APT metadata and the official
[Debian security tracker](https://security-tracker.debian.org/tracker/source-package/chromium)
identified `156.0.8078.47-1~deb12u1` for all three packages. On 2026-10-31 the same thing happened again: `156.0.8078.47-1~deb12u1` had left `bookworm-security` and the signed `Packages.xz` named `156.0.8078.73-1~deb12u1` for all three, so the Dockerfile pins moved to it (run 41185942735 on PR #453 was the red that found it). An exact pin on a rolling security pocket goes stale at every Chromium security upload, about every two weeks, and is corrected the same way each time. A no-cache build
installed that version and produced image
`sha256:7c27b521037d44416cb03951f9652bda7d8f393b7c0b86b6f965ba7aa241557e`.
All 20 actual worker tests and 8 proxy tests passed with no skips. Only the
three package pins changed; the sandbox profile and constraints below did not.
This is isolated validation evidence, not browser activation or deployment.


## Actual candidate smoke receipt (2026-10-22)

Image ID: `sha256:cb02194715d59ecb06452737548e0b0dd268ba1e450fa3846c27d787c8a1e26d`.
Generated seccomp SHA-256:
`5274c22c5e9fdf4749ce50fc95c6cccb5836ee7b55b04f1541f764c2c06e1743`.

On authorized VPS srv1936199, actual candidate image passed all eleven tests
with no skips, including real worker UDS blank open, duplicate suppression,
refused public navigation, PNG snapshot receipt and close. Renderer proof:
UID mapping differs from its container; container has one seccomp filter and
renderer has two. The blank screenshot was 1906 bytes. No external page loaded.

Container inspection confirmed UID/GID 10001, network none, cap-drop ALL, no
added capabilities, NNP, reviewed per-container seccomp, read-only root,
no mounts or port bindings, 128 MiB dedicated noexec/nosuid tmpfs and shared memory, 768 MiB
memory, one CPU and 128 process limit. Source was COPY-built, never host-mounted;
test environment was cleared and used fixture-only owner/service auth. No Tee
BrowserDesk profile, secrets or external provider were used.

The earlier three-syscall profile alone let user namespace creation succeed but
Chromium failed its chroot confinement call. That negative control identifies
the fourth rule's necessity; no broader sandbox/capability relaxation was used.

Host evidence retained under `/tmp/devon-worker-candidate-20261022/`:
`build-final.log`, `smoke-final.log`, `container-flags.log`, `smoke-reviewed.log`,
`container-flags-noexec.log`, `smoke-noexec.log`,
and the earlier `sandbox-diagnostic.log`. Temporary test containers were removed.
The fixture image is retained temporarily for independent reviewer readback.
This is isolated test evidence, not a deployed DEVON browser or Railway/VPS
transport integration. Named persistent IPC/data volumes were not exercised by
the temporary fixtures and remain a rollout gate. Stale IPC sockets remain the documented manual restart
gate. Public egress remains categorically disabled.
