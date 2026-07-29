<div align="center">

<img src=".github/images/The_Colonel.png" width="100"/>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
<img src=".github/images/The_General_Logo.png" width="100"/>

# Unicorn Commander

### Mesh-Distributed AI Infrastructure & Agent Orchestration

*VPN-meshed multi-node infrastructure. A GPU compute fabric that routes inference to wherever the hardware is. Federated SSO. Agent-to-agent orchestration across the mesh. Self-hosted. Open source.*

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-purple?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-blue?style=for-the-badge&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-teal?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react)](https://react.dev)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker)](https://docs.docker.com/compose/)

[![Sponsor](https://img.shields.io/badge/Sponsor-GitHub-EA4AAA?style=for-the-badge&logo=githubsponsors)](https://github.com/sponsors/Unicorn-Commander)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy_Me_A_Coffee-FFDD00?style=for-the-badge&logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/aaronyo)

**[Quick Start](#quick-start)** · **[Ops-Center](#ops-center--the-colonel)** · **[Unicorn Brigade](#unicorn-brigade--the-general)** · **[The Ecosystem](#the-ecosystem)** · **[Architecture](#architecture)** · **[Website](https://unicorncommander.com)**

</div>

---

## What Is Unicorn Commander?

Nearly every AI application needs the same foundation underneath it: users, authentication, permissions, agents, models, memory, search, files, billing, and APIs. Unicorn Commander is that foundation, built once, self-hosted, so the applications on top only have to build what actually makes them different.

It ties multiple machines together over a secure mesh and routes AI workloads to whichever node has hardware available.

| System | Role | What It Does |
|--------|------|-------------|
| **[Ops-Center](https://github.com/Unicorn-Commander/Ops-Center-OSS)** (The Colonel) | Infrastructure | Users, orgs, billing, SSO, LLM proxy, service management, credit system, federation mesh |
| **[Unicorn Brigade](https://github.com/Unicorn-Commander/Unicorn-Brigade-OSS)** (The General) | Agent Orchestration | 18 AI agents, workflow engine, 46 MCP servers, voice agents, real-time coordination |
| **AI Services** (Optional) | Self-hosted AI | 9 microservices: embeddings, reranking, STT, TTS, OCR, model manager, vLLM, Bolt.diy, proxy |

They share authentication (Keycloak SSO) and database infrastructure (PostgreSQL), and Brigade routes all LLM calls through Ops-Center for centralized billing and usage tracking.

A suite of applications is built on this foundation. See **[The Ecosystem](#the-ecosystem)** below.

---

## Ops-Center · The Colonel

> *Your AI infrastructure command center. Manage everything from one dashboard.*

Ops-Center is the admin backbone: user management with bulk operations, subscription billing (Stripe + Lago), multi-tenant organizations, LLM model management, service health monitoring, and a credit system that tracks every API call across your platform.

**624 API endpoints** · **Keycloak SSO** (Google, GitHub, Microsoft) · **Stripe/Lago billing** · **RBAC** · **BYOK support**

<div align="center">

#### User Homepage & Quick Access

<img src=".github/images/ops-center-homepage.png" width="720"/>

The landing page users see. Search bar powered by Center-Deep, quick access cards to platform services, and the admin dashboard link.

</div>

### Ops-Center Highlights

- **User Management:** Bulk import/export, advanced filtering (10+ fields), role hierarchy, API key management, user impersonation
- **Billing:** Stripe + Lago integration, subscription tiers (Trial through Enterprise), usage metering, credit system with per-model pricing
- **Organizations:** Multi-tenant with org-level feature grants, team roles, invitation system
- **LLM Proxy:** OpenAI-compatible API, routes to OpenRouter/OpenAI/Anthropic/local models, BYOK passthrough (no credits charged)
- **Image Generation:** DALL-E 3, GPT Image 1, Gemini Imagen 3, Stable Diffusion via unified API
- **Configurable Billing:** `BILLING_ENABLED=false` for personal servers, `CREDIT_EXEMPT_TIERS=*` for internal use

---

## Unicorn Brigade · The General

> *The AI agent factory. Build, deploy, and orchestrate autonomous agent teams.*

Unicorn Brigade is where the agent work happens: 18 specialized agents organized into military-style teams, a 3-tier hierarchical workflow engine (Orchestrator to Team Leads to Workers), 46 MCP servers providing roughly 1,360 enterprise tools, real-time orchestration with SSE streaming, and self-correcting workflows that retry on failure.

**18 agents** · **46 MCP servers** · **~1,360 tools** · **25 workflow templates** · **Voice agents** · **A2A + MCP protocols**

<div align="center">

#### Brigade Dashboard

<img src=".github/images/brigade-dashboard.png" width="720"/>

18 agents across 8 domains. Quick actions to build agents, browse the library, explore tools, or read API docs. The General (orchestrator) monitors operations from the command panel.

---

#### Agent Orchestration Concept

<img src=".github/images/brigade-orchestration-demo.gif" width="640"/>

*Conceptual mockup of multi-agent orchestration coordinating across domains. Not a product capture.*

</div>

### Brigade Highlights

- **18 Production Agents:** Research, finance, code, sales, legal, medical, DevOps, content, customer support, document analysis
- **3-Tier Workflows:** Orchestrator (GPT-4o) delegates to Team Leads (7B-14B) who assign Workers (1B-3B) for significant cost reduction
- **46 MCP Servers:** Stripe, Salesforce, Jira, GitHub, Slack, HubSpot, Shopify, Zendesk, MongoDB, Twilio, and 36 more
- **Ralph Self-Correction:** Workflows automatically retry on failure with error recovery and mid-execution guidance injection
- **Voice Agents:** LiveKit WebRTC with self-hosted STT (Whisper) and TTS (Kokoro, Chatterbox voice cloning)
- **Agent Trace:** Code attribution tracking for compliance and auditing (which AI wrote which code)
- **Visual Workflows:** Interactive workflow builder with @xyflow/react, drag-and-drop, real-time execution tracking

---

## The Ecosystem

Unicorn Commander is the foundation. These are the applications built on top of it, each self-hostable and each sharing the same identity, agents, permissions, and data layer. They are separate repos, so you can run one, several, or all of them.

### Collaboration plane

| Project | What It Does | Links |
|---------|-------------|-------|
| **Unicorn Stable** | Messaging, voice, video, meetings, and collaboration for people *and* agents. Your agents and someone else's can share a room with both of you in it. | [Code](https://github.com/Unicorn-Commander/unicorn-stable-oss) · [Live](https://stable.unicorncommander.ai/) |

### Applications

| Project | What It Does | Links |
|---------|-------------|-------|
| **Meeting-Ops** | Records meetings, works out who said what, and pushes decisions and action items into the rest of the stack. | [Code](https://github.com/Unicorn-Commander/meeting-ops-community) · [Live](https://meeting-ops.unicorncommander.ai/) |
| **Project-Ops** | Project management where a task can be assigned to a human or an agent, and the agent can execute it. Both are first-class citizens on the same board, with the same RBAC and audit trail. | [Code](https://github.com/Unicorn-Commander/project-ops-community) · [Live](https://projectops.unicorncommander.ai/) |
| **Contact-Ops** | The canonical record for people, identities, and relationships across the ecosystem. | [Code](https://github.com/Unicorn-Commander/contact-ops-community) |
| **Customer-Ops** | Leads, prospects, customers, and partners. The business relationship layer over the same people. | [Code](https://github.com/Unicorn-Commander/customer-ops-community) |
| **Email-Ops** | Turns email into structured work instead of leaving it trapped in an inbox. | [Code](https://github.com/Unicorn-Commander/email-ops-community) · [Live](https://email-ops.unicorncommander.ai/landing.html) |
| **Accounting-Ops** | Books, reconciliation, financial records, and agents that keep it straight. | [Code](https://github.com/Unicorn-Commander/accounting-ops-community) · [Live](https://accounting-ops.unicorncommander.ai/) |

Maturity varies. Ops-Center and Project-Ops have the most production mileage. Unicorn Stable is the newest. Everything listed is AGPL-3.0 and self-hostable.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Unicorn Commander                          │
│              docker compose up -d  (this repo)                │
└──────────────────────────┬──────────────────────────────────┘
                           │
             ┌─────────────┴──────────────┐
             │                            │
    ┌────────▼─────────┐       ┌─────────▼──────────┐
    │    Ops-Center     │       │   Unicorn Brigade   │
    │   (The Colonel)   │       │    (The General)    │
    │    :8084          │       │     :8112           │
    │                   │       │                     │
    │ Users & Orgs      │       │ 18 AI Agents        │
    │ Billing (Stripe)  │◄─────►│ Workflow Engine      │
    │ LLM Proxy         │  API  │ 46 MCP Servers       │
    │ Credit System     │       │ Voice (LiveKit)      │
    │ Service Mgmt      │       │ Agent Trace          │
    │ 624 API Endpoints │       │ Ralph Self-Correct   │
    └────────┬──────────┘       └──────────┬──────────┘
             │                             │
     ┌───────┴───────┐             ┌───────┴───────┐
     │   Keycloak    │             │  PostgreSQL   │
     │   SSO :8080   │             │  :5432        │
     │               │             │               │
     │ Google        │             │ unicorn_db    │
     │ GitHub        │             │ brigade_db    │
     │ Microsoft     │             │               │
     └───────────────┘             └───────┬───────┘
                                           │
                                    ┌──────┴──────┐
                                    │    Redis    │
                                    │    :6379    │
                                    └─────────────┘
```

**How they connect:**
- Brigade sends all LLM requests through Ops-Center's proxy for centralized billing and usage tracking
- Both services authenticate users via the same Keycloak realm (`uchub`)
- Separate databases (`unicorn_db` for Ops-Center, `brigade_db` for Brigade) on shared PostgreSQL
- Redis provides caching for both services

### AI Services (Optional)

Unicorn Commander ships with **9 self-hosted AI microservices**, all opt-in via Docker Compose profiles:

```bash
# Start with AI services
docker compose --profile ai up -d

# Or pick individual services
docker compose --profile embeddings --profile tts up -d
```

| Service | Port | What It Does |
|---------|------|-------------|
| **Embeddings** | 7997 | Vector embeddings (Nomic, BGE, GTE, Sentence Transformers) |
| **Reranker** | 7998 | Cross-encoder document reranking for search relevance |
| **WhisperX** | 9528 | Speech-to-text with word-level timestamps and speaker diarization |
| **Kokoro TTS** | 8880 | Text-to-speech with ONNX models, multiple voices |
| **Tika OCR** | 9998 | Document OCR via Apache Tika |
| **Model Manager** | 8085 | Web UI for switching between vLLM-hosted models |
| **vLLM** | 8000 | High-performance LLM serving |
| **Bolt.diy** | -- | Browser-based AI code IDE |
| **Infinity Proxy** | -- | On-demand container proxy (starts services when needed) |

### Monitoring (Optional)

```bash
docker compose --profile monitoring up -d
```

| Service | Port | What It Does |
|---------|------|-------------|
| **Prometheus** | 9090 | Metrics collection from all services |
| **Grafana** | 3001 | Dashboards and visualization |

### Cloud GPU Federation

Bootstrap GPU instances on **RunPod**, **Lambda**, or **Vast.ai** and connect them to your Unicorn Commander mesh:

```bash
cd cloud-gpu
FEDERATION_PEERS=https://your-ops-center.example.com \
FEDERATION_KEY=your-key \
./bootstrap.sh
```

The federation idle monitor automatically shuts down GPU instances when not in use to save costs.

---

## Quick Start

### Option A: One-Command Setup

```bash
git clone --recursive https://github.com/Unicorn-Commander/Unicorn-Commander.git
cd Unicorn-Commander
./setup.sh
```

The setup script auto-generates secure secrets, initializes submodules, imports the Keycloak SSO realm, and starts all services.

Use `./setup.sh --quick` to skip prompts and accept all defaults.

### Option B: Manual Setup

#### 1. Clone

```bash
git clone --recursive https://github.com/Unicorn-Commander/Unicorn-Commander.git
cd Unicorn-Commander
```

Already cloned without `--recursive`?

```bash
git submodule update --init --recursive
```

#### 2. Configure

```bash
cp .env.example .env
# Edit .env, at minimum set your database passwords
```

For a personal or dev deployment, the defaults work out of the box with `BILLING_ENABLED=false`.

#### 3. Run

```bash
# Everything
docker compose up -d

# Or just what you need
docker compose up -d ops-center        # Admin dashboard only
docker compose up -d unicorn-brigade   # Agent platform only

# With AI services (embeddings, TTS, STT, OCR, vLLM, etc.)
docker compose --profile ai up -d

# With monitoring (Prometheus + Grafana)
docker compose --profile monitoring up -d
```

The Keycloak `uchub` realm (with pre-configured OAuth clients for Ops-Center and Brigade, plus identity provider stubs for Google, GitHub, and Microsoft) is auto-imported on first boot.

#### 4. Open

| Service | URL | What You'll See |
|---------|-----|-----------------|
| **Ops-Center** | [localhost:8084](http://localhost:8084) | Admin dashboard: users, services, billing |
| **Brigade API** | [localhost:8112](http://localhost:8112) | Agent orchestration REST API |
| **Brigade UI** | [localhost:3000](http://localhost:3000) | Agent dashboard, chat, orchestration |
| **Keycloak** | [localhost:8080](http://localhost:8080) | SSO admin console |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI (Python 3.12), SQLAlchemy 2.0 |
| **Frontend** | React 18, Vite, Tailwind CSS, Material-UI, Three.js |
| **Auth** | Keycloak 26 (OIDC/SSO: Google, GitHub, Microsoft) |
| **Database** | PostgreSQL 16 |
| **Cache** | Redis 7 |
| **LLM Routing** | LiteLLM proxy to OpenRouter, OpenAI, Anthropic, local models |
| **Billing** | Stripe + Lago |
| **Agents** | LangGraph, OpenAI Agents SDK |
| **Protocols** | A2A (Agent-to-Agent), MCP (Model Context Protocol), UCP, Agent Trace |
| **Voice** | LiveKit WebRTC, Whisper (STT), Kokoro/Chatterbox (TTS) |
| **Observability** | Langfuse (self-hosted) |
| **Containers** | Docker + Docker Compose |

---

## Repository Structure

```
Unicorn-Commander/
├── ops-center/              # Git submodule → Ops-Center-OSS
├── unicorn-brigade/         # Git submodule → Unicorn-Brigade-OSS
├── docker-compose.yml       # Full-stack orchestration
├── setup.sh                 # One-command installer
├── init-db.sh               # Creates both databases on first run
├── .env.example             # Environment template
├── .gitmodules              # Submodule references
├── LICENSE                  # AGPL-3.0
└── README.md
```

Each component also runs standalone. See their individual repos for single-service setup.

## Updating

```bash
# Pull latest from both submodules
git submodule update --remote --merge
git add ops-center unicorn-brigade
git commit -m "Update submodules to latest"
```

---

## Running Standalone

Each component works independently:

**Ops-Center only:**
```bash
cd ops-center
docker compose -f docker-compose.direct.yml up -d
# → localhost:8084
```

**Brigade only:**
```bash
cd unicorn-brigade
docker compose up -d
# → localhost:8112 (API), localhost:3000 (UI)
```

**Brigade with optional services:**
```bash
cd unicorn-brigade
docker compose -f docker-compose.yml \
  -f docker-compose.langfuse.yml \     # Observability
  -f docker-compose.zep.yml \          # Temporal memory
  -f docker-compose.falkordb.yml \     # Knowledge graph
  -f docker-compose.livekit.yml \      # Voice agents
  -f docker-compose.langflow.yml \     # Visual workflow builder
  up -d
```

---

## Integration Details

When running the full stack via this repo's `docker-compose.yml`:

| Connection | From → To | Purpose |
|------------|-----------|---------|
| LLM Proxy | Brigade → Ops-Center `:8084` | All LLM calls routed through Ops-Center for billing/tracking |
| Auth | Both → Keycloak `:8080` | Shared SSO, same `uchub` realm |
| Database | Both → PostgreSQL `:5432` | Separate DBs: `unicorn_db`, `brigade_db` |
| Cache | Both → Redis `:6379` | Session/query caching |
| Service Key | Brigade → Ops-Center | `BRIGADE_SERVICE_KEY` for authenticated API calls |

---

## By the Numbers

| Metric | Value |
|--------|-------|
| Ops-Center API endpoints | 624 |
| Brigade AI agents | 18 |
| MCP servers | 46 |
| MCP tools available | ~1,360 |
| Workflow templates | 25 |
| Supported LLM providers | OpenRouter, OpenAI, Anthropic, Gemini, Ollama, vLLM |
| Identity providers | Google, GitHub, Microsoft |
| Subscription tiers | Trial, Starter, Professional, Enterprise |
| Agent domains | Research, Finance, Content, Sales, DevOps, Legal, Medical, Investigation |

---

## Star History

<div align="center">

[![Star History Chart](https://api.star-history.com/svg?repos=Unicorn-Commander/Unicorn-Commander,Unicorn-Commander/Ops-Center-OSS,Unicorn-Commander/Unicorn-Brigade-OSS&type=Date)](https://star-history.com/#Unicorn-Commander/Unicorn-Commander&Unicorn-Commander/Ops-Center-OSS&Unicorn-Commander/Unicorn-Brigade-OSS&Date)

</div>

---

## License

[AGPL-3.0](LICENSE). Use it, modify it, self-host it. If you run a modified version as a network service, the same license applies to your changes.

---

<div align="center">

**[Ops-Center](https://github.com/Unicorn-Commander/Ops-Center-OSS)** · **[Unicorn Brigade](https://github.com/Unicorn-Commander/Unicorn-Brigade-OSS)** · **[Unicorn Stable](https://github.com/Unicorn-Commander/unicorn-stable-oss)** · **[unicorncommander.com](https://unicorncommander.com)**

Built by [Magic Unicorn Unconventional Technology & Stuff Inc](https://magicunicorn.tech)

[![Sponsor](https://img.shields.io/badge/Sponsor-GitHub-EA4AAA?style=flat-square&logo=githubsponsors)](https://github.com/sponsors/Unicorn-Commander)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy_Me_A_Coffee-FFDD00?style=flat-square&logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/aaronyo)

</div>
