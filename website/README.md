# Operations & Ecosystem website

A single-file static site presenting the Meta Supreme Apex Genesis ecosystem
(layers, Council, engines) and its operating discipline (gates, the daily loop,
cost drivers, non-negotiables). Content is sourced from `README.md`,
`ARCHITECTURE.md`, and `OPERATING.md`.

No build step. Everything is inline except the Google Fonts stylesheet.

## View it

Open `website/index.html` in a browser, or serve it:

```bash
python -m http.server 8080 --directory website
# http://localhost:8080
```

## Hosting options

- **GitHub Pages** — Settings → Pages → deploy from a branch; point it at the
  branch root and visit `/website/`, or move this file to `docs/` and select
  the `/docs` folder.
- Any static host (Netlify, Vercel, Cloudflare Pages) — publish the `website/`
  directory as-is.

## Notes

- The hero contains an interactive approval-gate demo; the page works without
  JavaScript (scroll animations and the demo degrade gracefully).
- Honors `prefers-reduced-motion`.
