# Contributing to Meta Supreme Apex Genesis

Thank you for helping build the Intelligence Operating System.

This document defines how we work together so the platform remains secure, modular, and high-quality.

---

## Code of Conduct

- Be respectful and professional.
- Prioritize user data protection and system integrity above all else.
- Prefer clarity over cleverness.
- Document decisions that affect architecture or security.

---

## Branch Strategy

We use a simplified Git Flow:

| Branch        | Purpose                              |
|---------------|--------------------------------------|
| `main`        | Production-ready code only           |
| `develop`     | Integration branch for the next release |
| `feature/*`   | New features                         |
| `fix/*`       | Bug fixes                            |
| `hotfix/*`    | Critical production fixes            |
| `release/*`   | Release preparation                  |

**Rules**
- Never commit directly to `main` or `develop`.
- All changes go through Pull Requests.
- Feature branches are created from `develop`.
- Hotfixes are created from `main` and merged back to both `main` and `develop`.

---

## Coding Standards

### General
- Production-quality code only.
- Prefer explicit over implicit.
- Keep functions and modules focused.
- Write tests for non-trivial logic.
- Never hard-code secrets or credentials.

### TypeScript / Frontend
- Strict TypeScript (`strict: true`).
- Functional components + hooks.
- Prefer Server Components when possible.
- Use the shared design system (`packages/ui`).
- Accessible by default (ARIA, keyboard, contrast).
- Tailwind + design tokens for styling.

### Python / Backend
- Type hints everywhere.
- Pydantic models for all request/response and domain objects.
- FastAPI dependency injection for services.
- Structured logging (JSON preferred in production).
- Explicit error handling with meaningful HTTP status codes.
- Services are modular and independently testable.

### Database
- All tables use UUID primary keys.
- `created_at` and `updated_at` on every table.
- Ownership / tenancy columns required for multi-tenant tables.
- Migrations are the only way to change schema.
- Row-level security enabled where applicable.

### AI / Agents
- Every agent has a clear Identity, Mission, System Instructions, Capabilities, Limitations, Output Format, and Evaluation Criteria.
- Agent configurations are versioned.
- No agent should silently fail or invent facts.

---

## Commit Messages

Follow Conventional Commits:

```
feat: add council synthesis engine
fix: correct memory retrieval permission check
docs: update architecture overview
chore: upgrade FastAPI to 0.115
refactor: extract agent registry
test: add executive controller unit tests
security: enforce project-level isolation on knowledge items
```

---

## Pull Request Process

1. Create a branch from the correct base (`develop` or `main`).
2. Implement the change with tests and documentation.
3. Ensure the following pass:
   - Linting
   - Type checking
   - Unit / integration tests
   - Security scan (where applicable)
4. Open a PR against the correct target branch.
5. Fill out the PR template (description, testing notes, screenshots if UI).
6. Request review from at least one other engineer for non-trivial changes.
7. Address feedback.
8. Squash or rebase as agreed by the team before merge.

---

## Testing Requirements

| Type              | Scope                              |
|-------------------|------------------------------------|
| Unit              | Functions, services, agents        |
| Integration       | API endpoints + database           |
| API               | Contract and auth tests            |
| Security          | Auth, isolation, input validation  |
| AI Evaluation     | Accuracy, relevance, usefulness, confidence |

AI-related changes must include evaluation criteria and sample inputs/outputs.

---

## Security

- Never commit `.env`, secrets, or private keys.
- Use environment variables and secret managers.
- All external AI provider keys are injected at runtime.
- Audit logs are required for sensitive operations.
- Assume the platform will be used in regulated environments.

---

## Documentation

- Architecture decisions that affect multiple systems belong in `docs/architecture/`.
- Public API changes must update `docs/api/`.
- User-facing features should have corresponding guide updates.

---

## Deployment Workflow

```
CODE CHANGE
    “
TEST (unit + integration + security)
    “
SECURITY SCAN
    “
BUILD (Docker images)
    “
DEPLOY STAGING
    “
MANUAL / AUTOMATED APPROVAL
    “
PRODUCTION
```

Staging must pass smoke tests before production promotion.

---

## Questions

Open an issue or discuss in the appropriate channel before large architectural changes.

We are building a durable platform. Quality and security come first.
