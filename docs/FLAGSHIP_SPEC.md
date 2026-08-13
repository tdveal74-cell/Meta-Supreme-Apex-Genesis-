# Meta Supreme Apex Genesis — AAA Flagship Spec

**Status:** Flagship visual + product specification  
**Design system:** Deep Navy · Amber Gold · Warm Off-White  
**Standard:** Apple-level calm · evidence-first · never a chatbot  
**Viewport rule:** Chromebook-first · native resolution · fluid upward scale

---

## 0. Viewport & resolution (entry standard)

**Primary experience is optimized for the current HP Chromebook viewport first**, then scales upward automatically.

| Rule | Requirement |
|------|-------------|
| Entry device | HP Chromebook-class (compact laptop / convertible) |
| Rendering | Device native resolution and pixel density |
| Canvas | **No fixed canvas** — layout is fluid |
| Scaling | Automatic upward to larger / higher-DPI displays |
| Sharpness | **No blur** — respect `devicePixelRatio`; no forced 1× bitmap stretch |
| Screen use | **No wasted screen** — content and chrome use the available viewport efficiently |
| Quality bar | **AAA is the entry standard** — not a progressive enhancement after a degraded base |

Implementation implications:

- Use relative units, fluid grids, and container queries where useful.
- Prefer CSS that paints crisply at the device DPR (vector icons, `rem`/`em`, SVG, or properly generated high-DPI assets).
- Avoid fixed-pixel artboards or “design at 1440 then scale down.”
- Test and ship the Chromebook-class viewport as the primary experience; larger displays receive the same AAA quality with more space, not a different product.

---

## 1. Product identity

| Axis | Flagship standard |
|------|-------------------|
| Category | Intelligence Operating System |
| Anti-position | Not a chatbot, not a copilot toy, not therapy language |
| Promise | Amplify human judgment; AI analyzes and recommends |
| Human role | Values, responsibility, final decisions |
| AI role | Patterns, options, risks, synthesis — labeled when simulated |

---

## 2. Visual system (non-negotiable)

### Color

| Token | Hex | Use |
|-------|-----|-----|
| Navy | `#0A1628` | Primary surfaces, type on light, chrome |
| Navy 800 | `#0F1C30` | Hover / elevated dark |
| Amber | `#D4A017` | Accent, secondary CTAs, focus rings, labels |
| Surface | `#F8F5F0` | Page background |
| Surface muted | `#F0EBE3` | Subtle panels |
| Surface elevated | `#FFFFFF` | Cards, modals |
| Border | `#E5DFD5` | Hairlines |
| Border strong | `#D4CBBC` | Emphasis dividers |

**Rules**

- Never invent brand colors outside this palette.
- Amber is sparse — emphasis only, not decoration.
- Body secondary copy uses Navy at ~70% opacity.
- Simulated / offline intelligence is always visually labeled.

### Type

- Primary: Geist Sans (system-ui fallback)
- Mono: Geist Mono — agents, tokens, IDs
- Hero: semibold, tight tracking, balanced line length
- Overlines: medium, small, wide letter-spacing, amber
- Type remains legible and crisp at Chromebook-class sizes; scale upward with viewport, never down into blur.

### Shape & depth

- Radius: 0.75rem cards, 0.5rem controls
- Shadow soft: `0 2px 8px -2px rgba(10,22,40,0.08)`
- Shadow elevated: `0 8px 24px -4px rgba(10,22,40,0.12)`
- Borders: 1px, low contrast — never heavy chrome

### Motion

- 150–200ms UI, 300ms panels; ease-out
- Prefer opacity + subtle translate — no bounce
- Honor `prefers-reduced-motion`

### Layout

- Fluid first: Chromebook viewport is the primary canvas.
- Marketing: fluid up to `max-w-6xl` on larger screens; no fixed artboard.
- Command Center: council stream is the hero; chrome stays quiet and does not waste horizontal space on small viewports.

---

## 3. AAA UI surfaces

| Surface | Flagship bar |
|---------|----------------|
| Marketing home | Hero + capability cards + clear CTA; no hype |
| Auth | Minimal form, navy primary, amber focus |
| Command Center | Live council, synthesis distinct |
| Knowledge | Upload + search + cited sources |
| Memory | List / edit / pause / delete — user controlled |
| Decisions | Human records final call; AI drafts only |
| Workflows | Gate shows *rendered* effect before approve |
| Settings | Mock vs live provider; never hide simulated state |

All surfaces must meet the viewport rules in §0 on Chromebook-class hardware.

---

## 4. Council agents

| Slug | Name | Role |
|------|------|------|
| oracle | Oracle | Future / patterns |
| analyst | Analyst | Evidence |
| strategist | Strategist | Options & tradeoffs |
| architect | Architect | Systems structure |
| engineer | Engineer | Execution plans |
| guardian | Guardian | Risk |
| creator | Creator | Communication |
| librarian | Librarian | Knowledge structure |
| skeptic | Skeptic | Challenge assumptions |

**UI:** Agent chips navy on surface-muted; active contribution uses thin amber left rail — not rainbow avatars.

---

## 5. Copy rules

- Calm, precise, no hype
- Simulated output: API `simulated: true` + visible badge
- Never claim live intelligence when provider is mock
- Errors in plain language in product UI

---

## 6. Accessibility

- Focus rings: amber
- Contrast: navy on surface meets AA for body
- Targets ≥ 40px height where practical (especially on Chromebook touch/trackpad use)
- Labels always visible on forms

---

## 7. Definition of done (flagship visual)

- [x] Only navy / amber / surface tokens in product CSS
- [x] Landing matches calm OS positioning
- [x] Design tokens exported from `@meta-supreme/ui`
- [x] Simulated badge pattern defined
- [x] `prefers-reduced-motion` respected
- [ ] Primary experience verified on Chromebook-class viewport at native DPR (no blur, no fixed canvas, no wasted screen)
- [ ] Fluid upward scale confirmed on larger / higher-DPI displays
- [ ] Command Center live polish (requires full web from Workflows 11 zip)
- [ ] Workflow gate rendered preview in UI (same)

---

## 8. Engineering map

```
apps/web/app/globals.css
apps/web/tailwind.config.ts
apps/web/app/page.tsx
apps/web/components/ui/button.tsx
packages/ui/src/index.ts
docs/FLAGSHIP_SPEC.md
```

Offline API (`standalone_api.py`) remains usable without the visual stack.

---

*Meta Supreme Apex Genesis — the intelligence operating system.*
