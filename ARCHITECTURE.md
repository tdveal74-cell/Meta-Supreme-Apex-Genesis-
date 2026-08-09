# Architecture — Meta Supreme Apex Genesis

This document defines the system architecture for the Intelligence Operating System.

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     USER EXPERIENCE                          │
│  Command Center · Council Room · Knowledge Vault · Decisions │
└────────────────────────────,────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                    APPLICATION LAYER                         │
│              Next.js (SSR / RSC / Client)                    │
└────────────────────────────,────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                      API SERVICES                            │
│                    FastAPI  /api/v1                          │
│  Auth · Users · Projects · Intelligence · Council · ...     │
└────────────────────────────,────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│             INTELLIGENCE ORCHESTRATION ENGINE                │
│                   Executive Controller                       │
│  Intent → Context → Routing → Execution → Synthesis         │
└────────────,───────────────────────────────,────────────────┘
             │                               │
┌────────────▼────────────┐     ┌────────────▼────────────┐
│    AI COUNCIL SYSTEM    │     │   KNOWLEDGE + MEMORY    │
│  Oracle · Analyst ·     │     │  Embeddings · Retrieval │
│  Strategist · Architect │     │  Long-term Memory       │
│  Engineer · Guardian    │     │  Decision History       │
│  Creator · Librarian    │     └─────────────────────────┘
│  Skeptic                │
└─────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────┐
│                         DATABASE                             │
│              PostgreSQL + pgvector                           │
│  Users · Orgs · Projects · Agents · Knowledge · Memories    │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Core Layers

### 2.1 User Experience Layer
- **Command Center**: Primary interaction surface for conversations and council activation
- **Council Room**: Real-time visualization of agent contributions and synthesis
- **Knowledge Vault**: Document management, search, and organization
- **Decision Center**: Structured decision questions, options, recommendations, and outcomes

Design goals: Apple-level simplicity, calm premium aesthetic, enterprise reliability.

### 2.2 Application Layer
- Next.js App Router
- Server Components + Client Components where needed
- Shared design system via `packages/ui`
- Framer Motion for subtle, purposeful motion

### 2.3 API Services Layer
- FastAPI with versioned routes (`/api/v1`)
- Strict request/response contracts (Pydantic)
- Authentication & authorization middleware
- Structured logging and error handling
- Rate limiting and usage tracking (SaaS ready)

### 2.4 Intelligence Orchestration Engine
The **Executive Controller** is the central brain:

1. Receive user request
2. Analyze intent + extract context
3. Retrieve relevant knowledge and memory
4. Select and route to appropriate agents
5. Coordinate parallel or sequential agent execution
6. Synthesize final response
7. Update memory and decision records

### 2.5 AI Council System
Nine specialized agents, each with clear identity, mission, capabilities, limitations, and output schema:

| Agent      | Purpose                  |
|------------|--------------------------|
| Oracle     | Future / emerging patterns |
| Analyst    | Evidence & research      |
| Strategist | Options & tradeoffs      |
| Architect  | Systems & frameworks     |
| Engineer   | Implementation plans     |
| Guardian   | Risk & security          |
| Creator    | Communication & messaging|
| Librarian  | Knowledge organization   |
| Skeptic    | Assumption testing       |

Agents are registered, versioned, and configured independently.

### 2.6 Knowledge Engine
Pipeline:

```
UPLOAD → EXTRACT → CHUNK → EMBED → STORE → RETRIEVE
```

Supports PDF, DOCX, TXT, Markdown.  
Uses pgvector for semantic search.

### 2.7 Memory Engine
Persistent, transparent, editable, permission-controlled memory of:
- User preferences
- Project context
- Past decisions and outcomes
- Lessons learned
- Important patterns

Memory is never a black box.

---

## 3. Data Model (Core Entities)

Every table includes:
- `id` (UUID)
- `created_at`
- `updated_at`
- Ownership / tenancy fields

**Primary Entities**
- Users
- Organizations
- Projects
- Conversations / Messages
- Agents / Agent Runs
- Knowledge Items / Embeddings
- Memories
- Decisions
- Workflows
- Feedback
- Audit Logs

Row-level security is mandatory for multi-tenant isolation.

---

## 4. Security Architecture

- Authentication (JWT / session)
- Role-based access control (RBAC)
- Encryption in transit and at rest
- Secret management (never in code)
- Full audit logging
- Data isolation by organization / project
- Prepared for SOC 2 and GDPR

---

## 5. SaaS Model

| Plan        | Target          |
|-------------|-----------------|
| Free        | Individuals     |
| Professional| Power users / small teams |
| Enterprise  | Organizations   |

Billing, usage limits, analytics, and account management are first-class.

---

## 6. Deployment Topology

- **Development**: Local Docker Compose
- **Staging**: Isolated cloud environment
- **Production**: Multi-AZ, SSL, monitoring, backups, recovery procedures

CI/CD flow:

```
CODE CHANGE → TEST → SECURITY SCAN → BUILD → DEPLOY STAGING → APPROVAL → PRODUCTION
```

---

## 7. Design Principles (Non-Negotiable)

1. Secure by design
2. Transparent by default
3. Modular by architecture
4. Simple by experience
5. Powerful beneath the surface

The goal is a **durable platform**, not a demo.

---

## Related Documents

- `docs/architecture/` — deeper subsystem designs
- `CONTRIBUTING.md` — coding standards and workflow
- `CHANGELOG.md` — version history
