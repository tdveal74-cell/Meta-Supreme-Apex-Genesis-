---
title: DEVON Ecosystem Control Map
type: SYS_SPEC
version: 1
date: 2026-08-26
area: Systems
status: current
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
canonical_ref: main
owner: DEVON
---

# DEVON Ecosystem Control Map v1

## Ruling

DEVON remains the single executive control plane. Models, intelligence
providers, action systems, and production systems are capability lanes beneath
that authority. The four portfolio properties remain separate outputs with
their own canon, audience, voice, and production requirements.

## Rendered control map

![DEVON ecosystem with complementary operating layer and four portfolio properties](assets/SYS_PROOF_devon-ecosystem-control-map_v2_2026-08-26.jpg)

Rendered artifact SHA-256:
`1e4445c345e3197c0e3c39bdf677e89712c89faa99b94be82ef89954ba9a2ba1`

```mermaid
flowchart TD
    T["Tee<br/>Final authority"]
    I["Identity layer<br/>Tee Clone + Tee Soul"]
    D["DEVON<br/>Executive control plane"]

    T --> I
    I --> D

    subgraph INT["Intelligence and operating surfaces"]
        M["Meta Supreme X<br/>LLM Council"]
        C["Cerebras<br/>Intelligence acceleration"]
        O["Claude + ChatGPT<br/>Codex + Research + Work"]
    end

    D --> M
    D --> C
    D --> O

    subgraph ACT["Approved action layer"]
        A["n8n + connected apps<br/>scheduled tasks"]
        E["EditForge<br/>Production studio"]
    end

    D --> A
    A --> E

    subgraph PORT["Separate portfolio outputs"]
        TQO["The Quiet Operator<br/>TQO"]
        TSWS["The Shadow We Share<br/>TSWS"]
        NCO["NCO Forge<br/>NCO"]
        ACX["Ascension Caudex<br/>ACX"]
    end

    E --> TQO
    E --> TSWS
    E --> NCO
    E --> ACX

    O -. "artifacts + receipts" .-> D
    M -. "council result" .-> D
    C -. "provider result" .-> D
    A -. "effect receipt" .-> D
```

## Authority boundaries

| Layer | Canonical job | Boundary |
|---|---|---|
| Tee | Final rulings and consequential approval | No model substitutes for Tee |
| Tee Clone and Tee Soul | Identity, likeness, voice, values, memory, and judgment context | Identity does not become an execution authority |
| DEVON | Routing, conflict holds, approval coordination, receipt acceptance, and status | The only executive control plane |
| Meta Supreme X | Council deliberation and structured disagreement | Returns recommendations to DEVON |
| Cerebras | Intelligence acceleration within the existing provider lane | Not a router or orchestrator |
| Claude and ChatGPT operating surfaces | Architecture, synthesis, code, research, Work, apps, and tasks | Every route returns evidence to DEVON |
| Action layer | Approved automations and connected-service effects | Existing gates and read-back rules remain intact |
| EditForge | Production execution and media assembly | Does not own portfolio canon |

## Portfolio separation

| Code | Property | Canonical scope |
|---|---|---|
| TQO | The Quiet Operator | Quiet AI leverage, content engine, and monetization |
| TSWS | The Shadow We Share | Cinematic metaphysical relationship property, podcast, and micro-drama lane |
| NCO | NCO Forge | Military leadership content, checklists, and products |
| ACX | Ascension Caudex | Independent micro-drama IP, canon, assets, and production pipeline |

These properties share infrastructure only where DEVON approves the shared
service. Their canon, visual systems, audiences, and strategy do not merge.

## Source ownership

The executable Area names remain owned by `services/devon/areas.py`. This map
is an architectural representation for humans and handoffs. It does not create
a second Area registry or a second orchestrator.
