# Redeploying devon-soul after an environment variable change

Vercel runs `ignoreCommand` in `vercel.json` before every build, and that
command skips the build unless something under `deploy/soul` changed between
the previous deployment's commit and HEAD. A Redeploy from the dashboard runs
the same check against the same commit, so it is skipped too. Measured on
2026-09-15: the CONSOLE_TOKEN was rotated, two dashboard redeploys at 12:31Z
and 14:02Z both recorded CANCELED, and the serving deployment kept the old
token, answering 401 to the rotated value on every probe.

So a changed variable reaches production only through a build that runs, and
a build runs only when this directory changes. This file exists to be touched:
add a dated line below, open a pull request, merge it, and the build that
follows carries the new environment. The alternative is to clear the Ignored
Build Step in the project settings for one redeploy, then put it back.

## Touches

- 2026-09-15: CONSOLE_TOKEN rotated, redeploys skipped by the ignore rule; this file added so the build runs.
