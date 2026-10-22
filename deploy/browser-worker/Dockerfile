# Candidate only: pinned build inputs; still disabled pending reviewed rollout.
FROM node:24-bookworm-slim@sha256:55fb5f5a527ea2c5c4a95f963e48ef90aa38c7b346054fdc8ee9957a2b55d205
RUN apt-get update && apt-get install -y --no-install-recommends chromium=155.0.8059.79-1~deb12u1 chromium-common=155.0.8059.79-1~deb12u1 chromium-sandbox=155.0.8059.79-1~deb12u1 ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 10001 devonbrowser && useradd -u 10001 -g 10001 -M devonbrowser \
    && mkdir -p /run/devon-browser /var/lib/devon-browser \
    && chown -R 10001:10001 /run/devon-browser /var/lib/devon-browser
WORKDIR /app
COPY worker.mjs chrome-pipe.mjs chrome-smoke.mjs sandbox-proof.mjs worker.test.mjs seccomp-moby-base.json seccomp-browser.json proxy-launcher.mjs /app/
USER 10001:10001
CMD ["node", "/app/worker.mjs"]
