# Claude Project Brief — Meta Supreme Apex Genesis

**Paste this into a Claude Project or start of a conversation.**

---

You are continuing development of **Meta Supreme Apex Genesis**, an Intelligence Operating System (not a chatbot).

### Current State
- **Phase 1 (Foundation) is complete and ready.**
- Repository: monorepo with Next.js frontend + FastAPI backend + PostgreSQL/pgvector.
- Auth (JWT), Projects CRUD, full AI Council registry (9 agents), Executive Controller skeleton, Docker Compose, design system, and dashboard shell all exist.

### Critical Reading (in order)
1. `docs/HANDOVER_FOR_CLAUDE.md` — full handover (read completely)
2. `ARCHITECTURE.md`
3. `services/agents/registry.py` — the 9 agents are fully defined here
4. `services/intelligence/executive_controller.py`
5. `CONTRIBUTING.md`

### Immediate Goal
Begin **Phase 2 — Intelligence Core**:
1. AI provider abstraction (model-agnostic)
2. Wire Executive Controller to real agent execution + synthesis
3. Persist conversations/messages
4. Connect frontend login + basic Command Center flow

### Non-Negotiables
- This is **not** a chatbot. Preserve multi-agent council + synthesis.
- Humans make final decisions. AI recommends.
- Secure by design, transparent by default, modular architecture.
- Design system: Deep Navy `#0A1628` + Amber Gold `#D4A017` + Warm Off-White.
- Never hard-code secrets. Keep production quality.

### How to Run
```bash
make install && make up
```
- Frontend: http://localhost:3000
- API docs: http://localhost:8000/api/docs

Full details, file map, API surface, known gaps, and coding standards are in `docs/HANDOVER_FOR_CLAUDE.md`.

Start by confirming local run works, then propose the first concrete Phase 2 implementation slice.
