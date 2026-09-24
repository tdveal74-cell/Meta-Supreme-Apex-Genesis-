# tqohq.online

The public home page of The Quiet Operator (TQO), a YouTube channel that teaches AI tools and career strategy. It is static HTML for Hostinger shared hosting. The site's own code makes one third-party request: the Hostinger Reach signup form, framed on the home page. The frame is marked `loading="lazy"`, but Chromium asks for it as soon as the home page opens, with no scrolling, at 390x844 and 1280x800, and with JavaScript off at every size measured (320x568, 390x844 and 1280x800, 2026-09-23). Only at 320x568 with JavaScript on did it wait for a scroll. Safari was not measured, because no WebKit build is installed here. The framed Reach page then makes requests of its own, at least to `cdn-reach.hostinger.com` for its badge image, which answered with a Hostinger cookie, `__cf_bm`, when fetched on 2026-09-23. No CDN, no analytics, no remote fonts, and no Hostinger script in the site's own pages.

The page is an interoffice memo addressed to the visitor. The Re line is the visitor's own question, a Note row discloses the AI before any ask, and a Cc row leads to the one signup form. An attached specimen shows the episode format: a learning objective inside 30 seconds, a checklist, and one usable action.

## Files

| Path | What it is | Upload it |
|---|---|---|
| `index.html` | The home page. CSS and its one small script, which sizes the Reach frame, are inline. | yes |
| `privacy.html` | The privacy notice, in the same design system. | yes |
| `fonts/atkinson-hyperlegible-next-latin.woff2` | Atkinson Hyperlegible Next, variable, weights 200 to 800. | yes |
| `fonts/OFL-atkinson-hyperlegible-next.txt` | The font's SIL Open Font License 1.1. It must ship with the font. | yes |
| `check.mjs` | The rendered checks, described below. | no |
| `PRODUCT.md` | Product truth this page was built from. | no |
| `DESIGN.md` | The design system as built. | no |
| `README.md` | This file. | no |

## The signup form

Ruled by Tee on 2026-09-23: the form is the Hostinger Reach form "TQO home page" (uuid `d2047809-a203-479e-8db7-f598580f7b7b`), shown in a frame on the home page, without Hostinger's embed script. So this page's own code loads no Hostinger script, sends no impression beacons, and stores nothing in the browser. The framed Reach page is Hostinger's: it runs Hostinger's code, makes its own requests, and may set cookies and use browser storage under its own origin, which this page cannot see or stop. What a visitor types goes to Reach directly, and each signup carries the tag `form:TQO home page`.

- **The frame.** `src` is `https://reach-forms.hostingerusercontent.com/form/d2047809-a203-479e-8db7-f598580f7b7b`, with `title="Signup form, run by Hostinger Reach"`, `loading="lazy"`, `referrerpolicy="strict-origin-when-cross-origin"`, no border, a white background of its own (`#ffffff`) in both color schemes, and full width up to 520px, which is the Reach template's own max-width. The white is set by the page because in dark mode Chromium painted the framed document's canvas white on its own, and whether WebKit does the same could not be checked here. The template's thank-you panel has no background of its own, so without a white backdrop its dark text could land on the navy page.
- **Its height.** The CSS `min-height` is 560px, so the whole form shows at every width from 320 to 1280 with JavaScript off, and before Reach has said how tall it is. The Reach template (read from cdn-reach.hostinger.com on 2026-09-23) was rendered here in Chromium at every frame width the page produces: 288px at a 320 viewport, up to 520px, the frame's cap. At its tallest it measured 543px, at 288px wide with an 8px body margin, where the paragraph wraps to three lines in DejaVu Sans. DejaVu Sans is wider than the iPhone's system face, so that is the worst case. 560px adds 17px of room.
- **Fitted once Reach reports.** The first valid `reach:resize` drops the min-height, and the frame takes the reported height, kept between 120px and 1600px. Before this, the frame never went below 560px, so the form, shorter than that at every width above 320, sat on a band of empty white, and the thank-you panel, 219px tall in the review of 2026-09-23, sat at the top of a 560px white block. Against the stand-in, which reports its own height with margins, the frame is 520px at 390 with no inner scroll. The trade-off: if the real Reach page reports less than it needs, the frame shows a scroll bar inside it instead of empty space. Reach's own embed trusts the reported height the same way, with no lower limit at all. Unverified: what the hosted page measures. If it reports its document's `scrollHeight`, which never reads less than the frame it sits in, the frame stays at 560px and the white band stays. Only Tee's check of the live page can say.
- **Its sandbox.** `allow-scripts allow-forms allow-same-origin allow-popups allow-popups-to-escape-sandbox`, and nothing else:
  - `allow-scripts`: the Reach form sends by script. The template has no form element, and its button is a scripted `data-reach-submit`.
  - `allow-forms`: in case the hosted page submits a real form.
  - `allow-same-origin`: Reach keeps its own origin. Without it the form's requests to Reach would come from an opaque origin, and its size messages would arrive with origin `null`, which the page could not tell from anyone else's.
  - `allow-popups`: the Reach badge opens hostinger.com in a new tab.
  - `allow-popups-to-escape-sandbox`: that tab is an ordinary page rather than one bound by this frame's sandbox. It loosens only the new tab, never this page.
  - No `allow-top-navigation` of any kind: the form cannot move the visitor off the page.
  - No `allow` attribute: Reach's own embed asks for `clipboard-write`, and a signup form has no need of it.
- **The script.** 27 lines, 7 of them comments. It acts only when a message comes from the Reach origin, from this frame's own window, with type `reach:resize` and a finite `payload.height`. It then drops the CSS min-height and sets the frame's height, never below 120px and never above 1600px. Every other message is ignored, including `reach:redirect`, which the page never follows, and `reach:submitted`.
- **The lines around it.** One line sits above the frame. It names Hostinger Reach and carries the fallback: a plain link that opens the form on its own page for anyone whose frame does not load. The consent line and the privacy link sit directly under the frame. They were above it, and measured on 2026-09-23 at 393x659, the iPhone Safari visible area, with the frame routed to the Reach template as read: after tapping the Cc button the submit sat at 655 to 702px, off screen. With one line above it sits at 578 to 625px. The check's phone fold case now holds that.
- **Content-Security-Policy.** `frame-src https://reach-forms.hostingerusercontent.com` on `index.html` and `frame-src 'none'` on `privacy.html`. `script-src` is only the inline script's hash on the home page and `'none'` on the notice, and `connect-src 'none'` is set on both.

## Preview

Open `index.html` in a browser; the font loads over `file://`. To preview it the way a host serves it:

```bash
python3 -m http.server 8000 --directory sites/tqohq
```

Then open `http://127.0.0.1:8000/`. The frame loads the real Reach form wherever `reach-forms.hostingerusercontent.com` is reachable. It is not reachable from the build container.

## Checks

```bash
NODE_PATH=$(npm root -g) node sites/tqohq/check.mjs [dir]
```

`dir` defaults to the script's own folder, so a reviewer can point it at a copy and change that copy freely. It needs the globally installed `playwright` package and a Chromium build under `/opt/pw-browsers`. If either is missing it throws, so a machine without a browser fails instead of passing.

The hosted Reach form cannot load in the build container, and a check must never touch the real list. So every browser context the script opens routes the one allowed URL, the Reach form document, to a local stand-in page, and aborts every other off-file request. The stand-in is sized from the Reach template as read on 2026-09-23: the same 8px body margin, box and type sizes, and the template's own heading and paragraph, so the phone fold case measures the form as Reach serves it today. It says in its title and in the badge's place that it is a stand-in, and sends one `reach:resize` with its own height, margins included. None of the checks can read inside the real hosted form: the "one h1" and "labels" results are about this site's two pages only.

Every HTML file is loaded over `file://`. The run exits 1 when any of these fail:

- an em or en dash (U+2012 to U+2015) in visible text, attributes or source
- a banned house word, or a sentence opening with Additionally, Moreover or Notably
- horizontal overflow at 320px or 390px
- any request to a non-file URL other than the Reach form document in a frame. A request to `cdn-reach.hostinger.com` or to any impression URL is named as such.
- zero or several `h1` elements
- a form control without a label, a frame without a title, or a link or button without a name
- an image without alt text
- a font file that fails to load, or no license text beside it
- a console error or an uncaught exception
- a relative link or `#fragment` that points nowhere
- an exclamation mark, a curly quote or an ellipsis in visible text, attributes or script strings
- a Content-Security-Policy that is missing or looser than the page needs. `script-src` must be exactly the inline script's hash, or `'none'` where there is no script. `frame-src` must be exactly the Reach origin on the page with the frame, and `'none'` or absent on every other. `connect-src`, `form-action` and `base-uri` must be `'none'`.
- **reach frame**, against the stand-in:
  - (a) the frame's `src`, title and exact sandbox tokens, with no `allow-top-navigation`, no `allow` and no `srcdoc`. It is lazy, has no border and is full width, and its stylesheet min-height is at least the template's measured 543px. Its own background is white in light and in dark.
  - (b) the stand-in's own report fits the frame under its min-height with no scroll inside it. A `reach:resize` of 700 from the frame makes it 700px, and 300 makes it 300px. A height of 10 gives the 120px floor, and a height of 10,000,000 is capped.
  - Shapes that are not a finite height change nothing: NaN, Infinity, a string, a payload that is not an object, no payload, the wrong type, and a bare string.
  - (c) the right message from the top window, or from a second frame at the Reach origin, changes nothing. Nor does it from the frame itself once that frame is moved off the Reach origin. Each decoy's origin is read back first, so the case cannot pass without being tested.
  - (d) `reach:redirect` and `reach:submitted` navigate nowhere and request nothing.
  - (e) `localStorage`, `sessionStorage`, IndexedDB and CacheStorage are empty at load and after all of the above.
  - (f) with JavaScript off, the frame still loads, stands at its min-height, and the fallback link is there.
- **phone fold**: at 393x659, the iPhone Safari visible area, after tapping the Cc button, the section heading, the email field or the submit inside the frame is off screen. It is measured against the stand-in, which carries the template's heading and paragraph, so deleting those in Reach only moves the button up.
- **storage apis**: an inline script that names `document.cookie`, `cookieStore`, `indexedDB`, `localStorage`, `sessionStorage`, `caches` or `serviceWorker`. It reads the source, because over `file://` Chromium drops a cookie write without an error, so no run here could see one.
- **no reach script**: any page that mentions `embed.js`, `cdn-reach.hostinger.com` or `data-reach-form`.

It prints `WARN ... DEPLOY BLOCKER` and still exits 0 while any passage is marked `data-unconfirmed`. Each one waits on Tee's ruling.

The checks were proved to bite on 2026-09-23 by planting a defect in a copy of the site, one at a time, and running the check against it. Each defect turned it red, and the check named the defect:

| Planted defect | Named by |
|---|---|
| No origin test | reach frame (c) |
| No source test | reach frame (c) |
| Follows `reach:redirect` | reach frame (d) |
| Writes `localStorage` | reach frame (e) |
| Adds Hostinger's embed script | requests, console, csp, reach frame, no reach script |
| `allow-top-navigation` | reach frame (a) |
| min-height 300px | reach frame (a) |
| No finite test | reach frame, Infinity cases |
| No upper clamp | reach frame (b) |
| No fallback link | reach frame (f) |
| A frame on the privacy notice | console, csp, reach frame |
| An impression beacon, with `connect-src` opened | requests, console, csp, reach frame |
| Sets `document.cookie` and opens IndexedDB | reach frame (e), storage apis |
| Holds the frame at its CSS min-height after Reach reports | reach frame (b) |
| The consent line and the Reach line back above the frame | phone fold, submit at 655 to 702px |
| No background on the frame | reach frame, in light and dark |
| The frame's background set to the page's paper | reach frame, in dark only |

After any edit to the inline script in `index.html`, the `script-src` hash in its Content-Security-Policy must change too. The csp line prints the new hash. Until it matches, the browser refuses the script, and the reach frame check fails.

Screenshots at 390x844 and 1280x800, light and dark, go to `TQO_SHOTS_DIR` when it is set. The framed section also gets a 390x844 shot in light, in dark and with JavaScript off, and the phone fold case leaves a 393x659 shot taken after tapping the Cc button. Otherwise they go to the scratchpad path of the session that built the page. The frame in every screenshot shows the stand-in, not the real form.

The design detector from the Impeccable skill, `detect.mjs --json index.html privacy.html`, returned `[]` with exit 0 on 2026-09-23 after the switch to the framed form. It reads `DESIGN.md`, so re-run it after either changes. It cannot see into the frame, which is most of the signup section, so its `[]` says nothing about the form. Run on the Reach template as read, with `DESIGN.md` beside it, it returned 8 findings and exit 2 on 2026-09-23: a font outside `DESIGN.md` (Roboto, from the template's font stack), the colors `#111`, `#444`, `#333` and `#d1d1d1` outside the palette, an 8px radius outside the scale, 14px off the type ramp, and a flat type hierarchy.

## Deploy checklist

**Deploy is blocked until these are true.**

- [ ] **tqohq.online has a document root.** Today it is a Hostinger Website Builder site. Read on 2026-09-23 through the Hostinger API: `website_type` is `builder`, `root_directory` is null, and the file listing call returns HTTP 404. Static files cannot be uploaded to it. It has to be replaced by a hosting website with a document root, such as `public_html`.
- [ ] **Tee edits the Reach form's wording inside Reach.** The page cannot reword a cross-origin frame, and no check here can read inside it, so this copy goes live under TQO's name unchecked. As read on 2026-09-23 the thank-you panel says "You're in!", which breaks the house punctuation, and promises "our latest updates and exclusive content", which is not on record and does not match the page's consent line. The exact copy to set, with straight quotes and no exclamation marks:
  - Heading "Stay in the loop": delete it. The page's own heading says the same, and at 26px bold it outweighs that heading directly above it.
  - Paragraph "Get an email each time a new TQO episode is published.": delete it. The consent line under the frame says the same.
  - Button "Join the club": change it to "Get new episodes by email", the words on the Cc button, so the one ask has one name.
  - Thank-you heading "You're in!": change it to "You are on the list".
  - Thank-you body: if double opt-in is on, "Check your inbox for a message to confirm your address." If it is off, "The next email comes when the next episode is published."

The earlier second blocker, an empty `SIGNUP_ENDPOINT`, is gone. The form is now Reach's own page in a frame, so there is no endpoint to set and no token anywhere near the page. **Still, never put a Hostinger API token, or any other secret, in `index.html`.** The page is public and so is every line of its script, and that token controls the whole Hostinger account: domains, DNS, VPS, mail and billing.

Before deploy:

- [ ] **Tee's look and access changes inside Reach**, only where Reach's editor offers them. Whether it does is unverified.
  - Leave the form's background white. It matches the light page's paper, `#ffffff`, exactly. No color picked in Reach can fix the white panel in dark mode: the template's colors are fixed values with no dark variant, and in the review of 2026-09-23 a navy background standing in for one picked in Reach showed, in dark mode, as a navy card inside a white ring with a white band below. The page side is done instead: the frame now fits Reach's reported height and sets its own white backdrop.
  - The button's color: `#1f3fa6`, the page's pen blue, in place of `#111`.
  - A smaller corner radius than 8px, and a darker field border: `#d1d1d1` measures 1.53:1 against white, below the 3:1 that WCAG 1.4.11 asks for. `#6b778c`, the page's own field line, measures 4.52:1.
  - "First name": relabel it "First name (optional)", or remove the field. The privacy notice already treats it as optional, and the native form this replaced led with Email and tagged First name optional.
- [ ] **Tee reports two access faults in the Reach template to Hostinger.** This repository cannot fix them. The Email field's accessible name is its placeholder, "your@email.com": the visible "Email" label has no `for` and the input has no `id`, which fails WCAG 2.5.3, Label in Name, so a voice-control user who says "tap Email" misses it. Neither field has `autocomplete`, so a phone does not offer to fill the address. The template also adds a second `h1` after the page's `h2`, which deleting the heading fixes. All of this was read from the template; the hosted page is blocked here and may differ.
- [ ] **No redirect after signup in Reach.** The page ignores `reach:redirect` on purpose, so use Reach's thank-you panel instead.
- [ ] **Double opt-in and the consent box.** Confirm whether double opt-in is on in Reach. With it on, a contact is created as pending and a confirmation email goes out, so the consent line should say so. With it off, anyone can add a stranger's address. The template's GDPR checkbox is hidden. The page's own consent line, under the frame, is marked `data-unconfirmed`.
- [ ] **Tee checks the live framed form once on his iPhone.** It loads and sizes itself with no inner scroll bar and no band of empty white under the badge. After tapping the Cc button, the submit is on screen. The badge opens in a new tab. With VoiceOver on, the email field is read as "Email", not "your@email.com". In dark mode, one real address is submitted, it arrives in Reach with the tag `form:TQO home page`, and the thank-you panel shows and can be read. This is the only test of the real hosted page: it is blocked from the build container, so nothing here has ever loaded it.
- [ ] **JavaScript off.** Check whether the hosted form can send at all with JavaScript off. The template has no form element and a scripted submit, so it probably cannot. The frame and the fallback link still show, and both lead to the same form. Not checked here, because the hosted page is blocked.
- [ ] Once there is a document root, add a response header that stops other sites framing this site's pages, for example `Header set Content-Security-Policy "frame-ancestors 'none'"` in `.htaccess`. A meta policy cannot carry `frame-ancestors`.
- [ ] Remove each `data-unconfirmed` attribute only after Tee has ruled on that passage. `check.mjs` warns with DEPLOY BLOCKER while any remains.
- [ ] Run `check.mjs` and read the screenshots.

These also need Tee's decision before deploy:

- [ ] **The checklist.** The page shows a checklist of 3 to 5 steps as part of the episode format. The sources are Tee's stated profile of 2026-09-23 and `n8n/devon/drive-draft-writer/validate_and_plan.js:94`. The live lane does not write one: the TQO branch of `n8n/tqo-v5/build_script_prompt.js` never mentions a checklist, sets the description to 2 to 3 sentences plus the audit line (:81 to 82), and closes on a comment question and the free audit (:79). The page no longer says where the checklist appears or that an episode closes on it. Either the V5 prompt gains the checklist, or the Checklist part comes off the specimen.
- [ ] **What the list sends.** The page offers "an email each time a new episode is published". That offer is not on record in the repository. It appears in the consent line under the frame and in the privacy notice's Why clause, and both are marked `data-unconfirmed`. The Reach form's own paragraph, as read on 2026-09-23, says the same thing, and it was written inside Reach. It may already be his answer, but the markers stay until he says so.
- [ ] **Whether every home page visit should reach Hostinger.** As built, Chromium asks Hostinger Reach for the framed form as soon as the home page opens, so Reach sees the IP address and browser details of every visitor, including those who never join, and its badge image sets a Hostinger cookie. The privacy notice now says so. If Tee wants Reach contacted only by visitors who ask for the form, the option is a click-to-load frame: the Cc button, or a button in the section, inserts the frame. That changes his ruling of 2026-09-23, so it is a question for him and is not built.
- [ ] **The privacy notice's missing parts.** Who is responsible for the list, with a working contact address. A route for deletion requests: unsubscribing in Reach keeps the contact with the status unsubscribed, and deletion is a separate call. The lawful basis, which is consent. How long addresses are kept, stated only if it is really done. The reader's rights, and the right to complain to a regulator. The Deletion clause is marked `data-unconfirmed`. Naming someone responsible touches the open question about using his name; a business name and a mailbox on tqohq.online would meet it without naming him, and no such mailbox exists yet. Outside this page, US law (CAN-SPAM) also wants a postal address in each email Reach sends.
- [ ] **The statistics line.** The Note now says only what the QC gate does: it holds any episode that states an outside statistic without a named source (`n8n/tqo-v5/build_qc_prompt.js:40 to 42`). The earlier promise that "every statistic comes with a named source" and that "when something is not known, the episode says so" was cut, because the gate covers outside figures only and the second rested on a voice descriptor.
- [ ] **The presenter.** The page says any avatar that presents is built from footage of the man who makes the channel. Confirm that no published TQO video used another presenter. "Elias" is still open in `docs/devon/TQO_CANON_sisinty-benchmark-refresh_v1_2026-09-08.md`.
- [ ] **The channel the page links.** The footer on both pages links the channel by its verified id (ruled by Tee on 2026-09-23). Check that each public video's description carries the AI disclosure, and that YouTube's altered or synthetic content label is set. All 20 rows marked Published in the Airtable Content table have an empty AI Disclosure field, and none has a Published URL, so whether they are live on YouTube is unknown.

Upload `index.html`, `privacy.html` and the `fonts/` folder with both files, to the document root. Nothing else. Never upload this folder as a whole: `README.md`, `PRODUCT.md`, `DESIGN.md` and `check.mjs` are internal notes and tooling.

## What the page leaves out, on purpose

- Hostinger's embed script, and with it the impression beacons and the browser storage it uses. Ruled out by Tee on 2026-09-23.
- Tee's rank and military history. Nothing on record shows them used in public for TQO. His name appears only in the mandated disclosure line, by his ruling of 2026-09-23.
- The brand lines from the show context board, including "AI Strategy for the Next Economy." and the thesis line, and the audience line about building income before it is needed. None are cleared for public use.
- The internal name "The Quiet Move". The specimen calls that part "One usable action", the QC gate's own words.
- The script QC checklist as a ticked list. It is internal until Tee clears it.
- Subscriber counts, testimonials, results, logos, episode titles and dates. None exist that could be shown honestly.
