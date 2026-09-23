---
name: The Quiet Operator
description: An interoffice memo to the visitor, typed in navy on white bond, with one blue ballpoint for what a person does by hand.
colors:
  paper: "#ffffff"
  ink: "#0a1628"
  ink-2: "#4b5870"
  rule: "#d3d8e1"
  pen: "#1f3fa6"
  pen-deep: "#16307f"
  copy: "#f6edb2"
  copy-ink-2: "#574f1e"
  copy-rule: "#dccf85"
  field: "#f1f3f7"
  field-line: "#6b778c"
  err: "#a3261c"
  dark-paper: "#0a1628"
  dark-ink: "#e8ecf3"
  dark-ink-2: "#a6b1c4"
  dark-rule: "#26344d"
  dark-pen: "#9db8ff"
  dark-copy: "#18140e"
  dark-copy-ink: "#efe7d6"
  dark-copy-ink-2: "#c4b597"
  dark-copy-rule: "#3d3223"
  dark-tungsten-edge: "#d39a52"
  dark-tungsten-mark: "#e2ac68"
  dark-perf: "#d39a52"
  dark-field: "#12203a"
  dark-field-line: "#8a96ac"
  dark-err: "#ff9e91"
typography:
  display:
    fontFamily: "Atkinson Hyperlegible Next, ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(1.75rem, 1.1rem + 4vw, 4.15rem)"
    fontWeight: 380
    lineHeight: 1.08
    letterSpacing: "-0.024em"
  display-secondary:
    fontFamily: "Atkinson Hyperlegible Next, ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(1.75rem, 1.1rem + 3.2vw, 3.4rem)"
    fontWeight: 380
    lineHeight: 1.08
    letterSpacing: "-0.024em"
  heading:
    fontFamily: "Atkinson Hyperlegible Next, ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(1.6rem, 1.2rem + 1.7vw, 2.5rem)"
    fontWeight: 450
    lineHeight: 1.12
    letterSpacing: "-0.018em"
  specimen:
    fontFamily: "Atkinson Hyperlegible Next, ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(1.375rem, 1.15rem + 1vw, 1.875rem)"
    fontWeight: 430
    lineHeight: 1.28
    letterSpacing: "-0.012em"
  move:
    fontFamily: "Atkinson Hyperlegible Next, ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(1.25rem, 1.1rem + 0.6vw, 1.5rem)"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  lead:
    fontFamily: "Atkinson Hyperlegible Next, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  body:
    fontFamily: "Atkinson Hyperlegible Next, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "normal"
  body-desktop:
    fontFamily: "Atkinson Hyperlegible Next, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.1875rem"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "normal"
  strong-small:
    fontFamily: "Atkinson Hyperlegible Next, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 680
    lineHeight: 1.3
    letterSpacing: "-0.005em"
  form-label:
    fontFamily: "Atkinson Hyperlegible Next, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "normal"
  label:
    fontFamily: "Atkinson Hyperlegible Next, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 560
    lineHeight: 1.3
    letterSpacing: "normal"
rounded:
  control: "3px"
  box: "2px"
spacing:
  gutter: "clamp(1rem, 4.2vw, 3rem)"
  label-phone: "2.6rem"
  label-tablet: "4.25rem"
  label-desktop: "12.5rem"
  gap-phone: "0.625rem"
  gap-tablet: "1.25rem"
  gap-desktop: "2.5rem"
  measure: "34em"
components:
  button-primary:
    backgroundColor: "{colors.pen}"
    textColor: "{colors.paper}"
    typography: "{typography.strong-small}"
    rounded: "{rounded.control}"
    padding: "0.7rem 1.4rem"
    height: "3.25rem"
  button-primary-hover:
    backgroundColor: "{colors.pen-deep}"
  input-box:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.form-label}"
    rounded: "{rounded.control}"
    padding: "0.6rem 0.875rem 0.65rem"
  status:
    backgroundColor: "{colors.field}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0.85rem 1rem"
  tick-box:
    size: "1.5rem"
    rounded: "{rounded.box}"
---

# Design System: The Quiet Operator

Recorded from the built pages, `index.html` and `privacy.html`, after the build. Where this file and the pages disagree, the pages win.

## Overview

Each page is an interoffice memo addressed to the visitor: a letterhead, To, From, Re and Note fields, then the body. The home page adds a Cc row, an attachment and a distribution list. Everything is typed except one mark: a blue ballpoint tick, the only thing drawn by hand, meaning a person checked this. The register is calm and exact. Emphasis comes from size and position, never from color or ornament.

## Colors

Restrained: white bond, navy ink and one blue pen, plus one region of committed color, the carbon copy that holds the attachment.

### Primary
- **Pen** (`#1f3fa6`, dark `#9db8ff`): ballpoint blue. It marks what a person can act on or has done by hand: the tick, links, the one filled button, focus rings, the caret.

### Neutral
- **Paper** (`#ffffff`): white bond. In dark mode it becomes the carbon sheet, `#0a1628`.
- **Ink** (`#0a1628`): typed text. It is the TQO render worker's default plate navy, used here as ink.
- **Ink 2** (`#4b5870`): field labels, secondary lines, the consent line.
- **Rule** (`#d3d8e1`): decorative hairlines between memo fields. Component edges use `field-line`, which is above 3:1.

### Tertiary
- **Copy** (`#f6edb2`): the canary carbon copy. It fills the attachment band edge to edge, with a row of paper-colored perforation holes along the top. Secondary text on it is tinted from its own hue (`#574f1e`), never gray.
- **Copy under a tungsten lamp** (dark): bone text (`#efe7d6`) on a warm near-black (`#18140e`), with a 1px tungsten edge (`#d39a52`) at the top and bottom of the band and tungsten (`#e2ac68`) for the ruler's objective window. The perforation holes are tungsten too (`#d39a52`, 7.35:1 on the band), read as holes punched through to lamp light. Holes in the page navy measured 1.01:1 and vanished. The band is 1.01:1 against the dark page by luminance. The tungsten edge (7.35:1) and the change from cool to warm hue carry the boundary, so the edge must never be removed.

### Named Rules
- **One pen.** Pen blue is never decoration. Where it appears, something can be clicked, typed into, or was ticked by hand.
- **Color owns a region or nothing.** Canary fills the attachment band full bleed. It is never a chip, a badge or an accent stripe.

## Typography

One family, Atkinson Hyperlegible Next, self-hosted as a variable woff2 (weights 200 to 800, SIL OFL 1.1, license beside it in `fonts/`). Its zero is slashed and has no plain alternate, so 0 and O cannot be confused. That trait is kept on purpose. The face is declared without a preload: the CSS is inline, so a preload gains little, and one fetched in CORS mode fails over `file://`.

### Hierarchy
- **Display** (380, 1.75rem to 4.15rem, 1.08): the home page's Re line only. Four lines at 320px and 390px, three at 1280px.
- **Display secondary** (380, 1.75rem to 3.4rem, 1.08): the privacy notice's Re line. A second-order page takes a smaller top step.
- **Heading** (450, 1.6rem to 2.5rem, 1.12): section headings that carry memo words themselves ("Attached: ...", "distribution list", "Note on ...").
- **Specimen** (430, 1.375rem to 1.875rem): the sample learning objective.
- **Move** (600, 1.25rem to 1.5rem): the sample usable action.
- **Lead** (400, 1.25rem, 1.375rem on desktop): the first paragraph of the memo body.
- **Body** (400, 1.125rem, 1.1875rem on desktop, 1.55): measure capped at 34em, about 70 characters.
- **Strong small** (650 to 720, 1.0625rem): wordmark, sign-off name, part and clause titles, buttons.
- **Form label** (600, 1rem): labels inside the form boxes.
- **Label** (560, 0.9375rem): memo field labels (To, From, Re, Note, Cc), part notes, the consent line, errors, ruler times and the ruler's caption. Nothing on the page is set smaller.

### Named Rules
- **Labels sit beside, never above.** A memo field label shares a row with its value. No eyebrows or kickers above headings.
- **No second face.** A monospace companion was tried and removed as costume. Ruler times use tabular figures of the same face.

## Layout

One grid on every section: a label column and a value column. The label column is 2.6rem on phones, 4.25rem from 40em and 12.5rem from 60em. From 60em all content sits in the value column. The left column then holds memo field labels, the attachment's part notes and the privacy notice's clause titles, and the right side of the page stays empty on purpose. Mobile first at 390px, with a gutter of 16px or more and no horizontal scroll at 320px. On the home page at 390px, the first viewport holds the letterhead, To, From, the Re line, the Note row with the AI disclosure, and the Cc button, which ends at y 586.

## Elevation & Depth

None. The pages are flat paper with no shadows. Separation comes from hairlines, the double rule (3px and 1px of ink) under the letterhead and above the sign-off, and the carbon band.

## Shapes

Near square. Controls use 3px corners, tick boxes 2px. No cards, no pills.

## Components

### Buttons
One filled pen-blue button style. It is full width on phones, at least 3.25rem tall, and its label wraps balanced. The home page uses it twice for the same ask, with the same words, "Get new episodes by email": as the Cc link that jumps to the form, and as the form's submit. It carries a 2px transparent border so that forced colors (Windows High Contrast) still draws its edge. Hover deepens the ink; press moves it down 1px. Disabled is `rule` on `ink-2`. The submit is disabled in the markup and enabled by the script, so with JavaScript off it cannot post anywhere, and a noscript line says why.

### Inputs / Fields
A typed form box: a 2px `field-line` border on paper, with the label inside at the top and a right-aligned "Required" or "Optional" tag in `ink-2`. Focus draws one pen outline, 3px, 2px outside the box, and turns the border pen. Invalid turns the border `err`, so an invalid field in focus shows a red border inside a single blue ring. The error text sits inside the box, below the input, and names the fix. It is a `role="alert"` element present from load and empty until needed, so an error raised while focus is already in the field (Enter, or the iOS Go key) is still announced. Email comes first. The consent line sits between the inputs and the submit, so it is read before the button.

### Status line
The form's answer, in a `field` box with a 1px `field-line` border, directly under the submit. It is rendered from load and collapses to nothing while empty, so the live region exists before its first message. Each answer is written a frame after clearing, so a repeat is announced again, and the page scrolls it into view. It reports only what the page knows: "Signup is not open yet" while the endpoint is empty; "Received" only on a 2xx answer that was not redirected and whose body reports no error; "Not added" for a readable error; "Not confirmed" when no answer could be read, because the provider may have stored the address anyway. Error uses a 2px `err` border and Not confirmed a 2px `ink-2` border, all round, never a side stripe.

### Tick box (signature)
A 1.5rem square box with a 2px border. When ticked, a constant-width ballpoint tick draws in 0.42s and overshoots the box to the upper right, the way a hand does. It is used for the specimen checklist (real checkboxes) and, static, for the review line in the note. Reduced motion shows the tick without the draw.

### Attachment band
Full-bleed carbon copy with a perforated top edge. Part notes sit in the label column and the specimen in the value column. It is labeled twice as an example written for the page.

### Ruler
A small figure under the learning objective's part note: the first minute of an episode in discrete ticks, 13 of them, 5 seconds apart, with major ticks at 0:00, 0:15, 0:30, 0:45 and 1:00. A bar marks 0:00 to 0:30 and a taller line marks 0:30. Labels read 0:00, 0:30 and 1:00 at label size, and the figcaption below the track reads "The first minute of an episode." The bar has square ends.

### Favicon
A small canary memo sheet with navy lines, never the tick. A tick beside the page title in a browser tab reads as a "verified" badge.

## Do's and Don'ts

### Do:
- Keep the memo grammar: say who it is to, who it is from, and what it is about.
- Disclose the AI before any ask. On the home page the Note row sits above the Cc row.
- Use the tick only where a person checks something.
- Label any demonstration content as written for the page.

### Don't:
- Put the pen tick next to a name or a title. It reads as a social "verified" badge.
- Add a second accent, a gradient, a shadow or a card.
- Put a label above a heading.
- Remove the tungsten edge from the dark band. Without it the band disappears into the page.
