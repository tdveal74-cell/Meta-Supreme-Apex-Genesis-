# tqohq.online

The public home page of The Quiet Operator (TQO), a YouTube channel that teaches AI tools and career strategy. It is static HTML for Hostinger shared hosting. It makes no third-party requests at runtime: no CDN, no analytics, no remote fonts.

The page is an interoffice memo addressed to the visitor. The Re line is the visitor's own question, a Note row discloses the AI before any ask, and a Cc row leads to the one signup form. An attached specimen shows the episode format: a learning objective inside 30 seconds, a checklist, and one usable action.

## Files

| Path | What it is | Upload it |
|---|---|---|
| `index.html` | The home page. CSS and the one script are inline. | yes |
| `privacy.html` | The privacy notice, in the same design system. | yes |
| `fonts/atkinson-hyperlegible-next-latin.woff2` | Atkinson Hyperlegible Next, variable, weights 200 to 800. | yes |
| `fonts/OFL-atkinson-hyperlegible-next.txt` | The font's SIL Open Font License 1.1. It must ship with the font. | yes |
| `check.mjs` | The rendered checks, described below. | no |
| `PRODUCT.md` | Product truth this page was built from. | no |
| `DESIGN.md` | The design system as built. | no |
| `README.md` | This file. | no |

## Preview

Open `index.html` in a browser; the font loads over `file://`. To preview it the way a host serves it:

```bash
python3 -m http.server 8000 --directory sites/tqohq
```

Then open `http://127.0.0.1:8000/`.

## Checks

```bash
NODE_PATH=$(npm root -g) node sites/tqohq/check.mjs [dir]
```

`dir` defaults to the script's own folder, so a reviewer can point it at a copy and change that copy freely. It needs the globally installed `playwright` package and a Chromium build under `/opt/pw-browsers`. If either is missing it throws, so a machine without a browser fails instead of passing.

Every HTML file is loaded over `file://`. The run exits 1 when any of these fail:

- an em or en dash (U+2012 to U+2015) in visible text, attributes or source
- a banned house word, or a sentence opening with Additionally, Moreover or Notably
- horizontal overflow at 320px or 390px
- any request to a non-file URL
- zero or several `h1` elements
- a form control without a label, or a link or button without a name
- an image without alt text
- a font file that fails to load, or no license text beside it
- a console error or an uncaught exception
- a relative link or `#fragment` that points nowhere
- a signup form that reports success it did not receive, or that breaks with JavaScript off
- an exclamation mark, a curly quote or an ellipsis in visible text, attributes or script strings
- a missing Content-Security-Policy, a `script-src` hash that no longer matches the inline script, or a `connect-src` that does not name the endpoint's origin
- a form status region or field error that is missing from the page, or from the accessibility tree, on load
- a form answer drawn off screen at 393x659, the iPhone Safari visible area, with the submit button at the bottom edge
- a wrong answer from the form against a local stand-in for the list provider

The stand-in runs on every check, with or without an endpoint. The page is served over http from one local origin, with `SIGNUP_ENDPOINT` pointed at a stand-in on another, so CORS applies as it will in production, and the page's own policy is kept but re-pinned to the stand-in. Six cases: a 200 with CORS must say Received; a 503 and a 200 whose body reports an error must say Not added; a 200 with no CORS header, a redirect, and no answer before the timeout must say Not confirmed. The no-CORS case also checks the stand-in received the address, which is the whole point of that answer.

While `SIGNUP_ENDPOINT` is empty it prints `WARN ... DEPLOY BLOCKER: SIGNUP_ENDPOINT is empty` and still exits 0. It also warns for each passage marked `data-unconfirmed`, which waits on Tee's ruling; once the endpoint is set, any such passage fails the run. Once the endpoint is set, the file:// form test also answers the endpoint itself with a mocked 503 and then a mocked 200. A test address is never posted to the real list. The run also fails if any page still says signup is not open yet.

After any edit to the inline script in `index.html`, the `script-src` hash in its Content-Security-Policy must change too. The csp line prints the new hash, and until it matches the browser refuses the script, so the submit button stays disabled.

Screenshots at 390x844 and 1280x800, light and dark, go to `TQO_SHOTS_DIR` when it is set. Otherwise they go to the scratchpad path of the session that built the page.

The design detector from the Impeccable skill, `detect.mjs --json index.html privacy.html`, returned `[]` with exit 0 on 2026-09-23 after the polish pass. It reads `DESIGN.md`, so re-run it after either changes.

## Deploy checklist

**Deploy is blocked until both of these are true.**

- [ ] **(a) tqohq.online has a document root.** Today it is a Hostinger Website Builder site. Read on 2026-09-23 through the Hostinger API: `website_type` is `builder`, `root_directory` is null, and the file listing call returns HTTP 404. Static files cannot be uploaded to it. It has to be replaced by a hosting website with a document root, such as `public_html`.
- [ ] **(b) `SIGNUP_ENDPOINT` is set.** It is the first line of the inline script in `index.html` and is empty today. No Hostinger Reach form or endpoint exists yet: on 2026-09-23 the one Reach profile for tqohq.online (a trial, 100 subscribers, 200 emails a month) listed zero forms.

**Never put a Hostinger API token, or any other secret, in `index.html`.** The page is public and so is every line of its script. That token controls the whole Hostinger account: domains, DNS, VPS, mail and billing. The only programmatic way to add a Reach contact on record is that authenticated API, so a browser cannot call it directly. Contacts can only arrive through one of two routes, and Tee picks which:

1. A same-origin handler on the server that holds the token and calls the Reach API. It needs the document root from (a) and server-side code.
2. A Reach form endpoint that has been confirmed to accept an unauthenticated cross-origin `POST`. Reach forms are served from a hosted template URL with no embed snippet, and embedding that template would be a third-party request, which this page does not make.

When (b) is done:

- [ ] The endpoint accepts a `POST` of form data and answers with a 2xx status on success. The inputs are named `email` and `first_name`. The Reach contact API names the field `name`, so if the route ends at that API, rename `first_name` to match.
- [ ] Find out how the endpoint reports failure. The page treats a 2xx as success only when it was not redirected and its JSON body has no `success: false`, `ok: false`, `error` or non-empty `errors`. If the provider signals failure some other way, change `reportsError` in the script.
- [ ] The endpoint allows cross-origin requests from `https://tqohq.online`, unless it is same-origin. Without that header the browser still delivers the form, because a form-data `POST` needs no preflight, so the address is probably stored. The page cannot read the answer and says "Not confirmed". That is honest, and it is broken.
- [ ] Add the endpoint's origin to `connect-src` in the Content-Security-Policy meta of `index.html`, in place of `'none'`, and update the `script-src` hash. `check.mjs` fails until both match.
- [ ] Confirm whether double opt-in is on in Reach. With it on, a contact is created as pending and a confirmation email goes out, so the consent line should say so. With it off, anyone can add a stranger's address.
- [ ] Once there is a document root, add a response header that stops other sites framing the form, for example `Header set Content-Security-Policy "frame-ancestors 'none'"` in `.htaccess`. A meta policy cannot carry `frame-ancestors`.
- [ ] Replace the Note row in `privacy.html` that says signup is not open yet. `check.mjs` fails while it remains.
- [ ] Remove each `data-unconfirmed` attribute only after Tee has ruled on that passage. `check.mjs` fails while any remains.
- [ ] Run `check.mjs` and read the screenshots.
- [ ] Submit one real address from a phone and confirm it arrives in Reach.

Before either, these need Tee's decision:

- [ ] **The checklist.** The page shows a checklist of 3 to 5 steps as part of the episode format. The sources are Tee's stated profile of 2026-09-23 and `n8n/devon/drive-draft-writer/validate_and_plan.js:94`. The live lane does not write one: the TQO branch of `n8n/tqo-v5/build_script_prompt.js` never mentions a checklist, sets the description to 2 to 3 sentences plus the audit line (:81 to 82), and closes on a comment question and the free audit (:79). The page no longer says where the checklist appears or that an episode closes on it. Either the V5 prompt gains the checklist, or the Checklist part comes off the specimen.
- [ ] **What the list sends.** The page now offers "an email each time a new episode is published". That offer is not on record anywhere. It appears in the consent line and in the privacy notice's Why clause, and both are marked `data-unconfirmed`.
- [ ] **The privacy notice's missing parts.** Who is responsible for the list, with a working contact address. A route for deletion requests: unsubscribing in Reach keeps the contact with the status unsubscribed, and deletion is a separate call. The lawful basis, which is consent. How long addresses are kept, stated only if it is really done. The reader's rights, and the right to complain to a regulator. The Deletion clause is marked `data-unconfirmed`. Naming someone responsible touches the open question about using his name; a business name and a mailbox on tqohq.online would meet it without naming him, and no such mailbox exists yet. Outside this page, US law (CAN-SPAM) also wants a postal address in each email Reach sends.
- [ ] **The statistics line.** The Note now says only what the QC gate does: it holds any episode that states an outside statistic without a named source (`n8n/tqo-v5/build_qc_prompt.js:40 to 42`). The earlier promise that "every statistic comes with a named source" and that "when something is not known, the episode says so" was cut, because the gate covers outside figures only and the second rested on a voice descriptor.
- [ ] **The presenter.** The page says any avatar that presents is built from footage of the man who makes the channel. Confirm that no published TQO video used another presenter. "Elias" is still open in `docs/devon/TQO_CANON_sisinty-benchmark-refresh_v1_2026-09-08.md`.
- [ ] **Before any link to the channel.** Check that each public video's description carries the AI disclosure and that YouTube's altered or synthetic content label is set. All 20 rows marked Published in the Airtable Content table have an empty AI Disclosure field, and none has a Published URL, so whether they are live on YouTube is unknown.

Upload `index.html`, `privacy.html` and the `fonts/` folder with both files, to the document root. Nothing else. Never upload this folder as a whole: `README.md`, `PRODUCT.md`, `DESIGN.md` and `check.mjs` are internal notes and tooling.

## What the page leaves out, on purpose

- A link to the YouTube channel. The channel id `UCZ58HLffFc3VJJ_RfvOLteQ` is verified, but no URL built from it has been loaded here.
- Tee's name, rank and military history. Nothing on record shows them used in public for TQO.
- The brand lines from the show context board, including "AI Strategy for the Next Economy." and the thesis line, and the audience line about building income before it is needed. None are cleared for public use.
- The internal name "The Quiet Move". The specimen calls that part "One usable action", the QC gate's own words.
- The script QC checklist as a ticked list. It is internal until Tee clears it.
- Subscriber counts, testimonials, results, logos, episode titles and dates. None exist that could be shown honestly.
