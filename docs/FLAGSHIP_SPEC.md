# Meta Supreme Apex Genesis — AAA Flagship Spec

**Status:** Flagship visual + product specification  
**Design system:** Deep Navy · Amber Gold · Warm Off-White  
**Standard:** Apple-level calm · evidence-first · never a chatbot

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

- Marketing: `max-w-6xl`
- Command Center: council stream is the hero; chrome stays quiet

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
- Targets ≥ 40px height where practical
- Labels always visible on forms

---

## 7. Definition of done (flagship visual)

- [x] Only navy / amber / surface tokens in product CSS
- [x] Landing matches calm OS positioning
- [x] Design tokens exported from `@meta-supreme/ui`
- [x] Simulated badge pattern defined
- [x] `prefers-reduced-motion` respected
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
