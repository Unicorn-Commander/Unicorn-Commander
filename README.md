<div align="center">

<img src=".github/images/The_Colonel.png" width="120"/>
&nbsp;&nbsp;&nbsp;&nbsp;
<img src=".github/images/The_General_Logo.png" width="120"/>

# Unicorn Commander

### **The Open-Source AI Cloud Platform**

*Infrastructure Management + Agent Orchestration — Self-Hosted, Integrated, Ready.*

[![License: MIT](https://img.shields.io/badge/License-MIT-purple?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-blue?style=for-the-badge&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-teal?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react)](https://react.dev)

</div>

---

## What Is This?

Unicorn Commander is the umbrella project that brings together the entire self-hosted AI platform:

| Component | Description | Repo |
|-----------|-------------|------|
| **Ops-Center** (The Colonel) | AI infrastructure command center — users, billing, LLMs, services, SSO | [Ops-Center-OSS](https://github.com/Unicorn-Commander/Ops-Center-OSS) |
| **Unicorn Brigade** (The General) | Multi-agent orchestration — 17 agents, workflows, MCP servers, voice | [Unicorn-Brigade-OSS](https://github.com/Unicorn-Commander/Unicorn-Brigade-OSS) |

Think of it like:
- **Ops-Center** = AWS Console (manage infrastructure, users, billing)
- **Unicorn Brigade** = The AI workforce (agents that actually do things)
- **This repo** = Glue that runs them together

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   Unicorn Commander                       │
│              (this repo — orchestrates all)                │
└────────────────────────┬─────────────────────────────────┘
                         │
           ┌─────────────┴─────────────┐
           │                           │
  ┌────────▼────────┐       ┌─────────▼─────────┐
  │   Ops-Center    │       │  Unicorn Brigade   │
  │  (The Colonel)  │       │   (The General)    │
  │                 │       │                    │
  │ • User mgmt    │◄─────►│ • 17 AI agents     │
  │ • Billing/SSO  │  API  │ • Workflow engine   │
  │ • LLM routing  │       │ • MCP servers       │
  │ • Service mgmt │       │ • Voice agents      │
  │ • Credit system│       │ • Agent tracing     │
  └────────┬────────┘       └─────────┬──────────┘
           │                          │
    ┌──────┴──────┐            ┌──────┴──────┐
    │  Keycloak   │            │ PostgreSQL  │
    │  (SSO)      │            │ (shared DB) │
    └─────────────┘            └─────────────┘
```

## Quick Start

### 1. Clone with submodules

```bash
git clone --recursive https://github.com/Unicorn-Commander/Unicorn-Commander.git
cd Unicorn-Commander
```

If you already cloned without `--recursive`:

```bash
git submodule update --init --recursive
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your settings (database passwords, API keys, etc.)
```

### 3. Start everything

```bash
# Full stack (Ops-Center + Brigade + infrastructure)
docker compose up -d

# Or individual services
docker compose up -d ops-center       # Just the admin dashboard
docker compose up -d unicorn-brigade  # Just the agent platform
```

### 4. Access the services

| Service | URL | Description |
|---------|-----|-------------|
| Ops-Center | http://localhost:8084 | Admin dashboard |
| Brigade API | http://localhost:8112 | Agent orchestration API |
| Brigade Frontend | http://localhost:3000 | Agent orchestration UI |
| Keycloak | http://localhost:8080 | SSO admin console |

## Repository Structure

```
Unicorn-Commander/
├── ops-center/              # Git submodule → Ops-Center-OSS
├── unicorn-brigade/         # Git submodule → Unicorn-Brigade-OSS
├── docker-compose.yml       # Full-stack orchestration
├── .env.example             # Environment template
├── .gitmodules              # Submodule configuration
└── README.md                # This file
```

## Running Individual Components

Each component works standalone. See their repos for details:

- **Ops-Center**: `cd ops-center && docker compose -f docker-compose.direct.yml up -d`
- **Unicorn Brigade**: `cd unicorn-brigade && docker compose up -d`

## How They Talk to Each Other

When running together via this repo's `docker-compose.yml`:

- **Brigade → Ops-Center**: LLM routing, credit tracking, user auth
  - `OPS_CENTER_URL=http://ops-center:8084`
  - `OPS_CENTER_LLM_ENDPOINT=http://ops-center:8084/api/v1/llm/chat/completions`
- **Shared Auth**: Both use Keycloak SSO (same realm)
- **Shared Database**: PostgreSQL with separate databases (`unicorn_db`, `brigade_db`)

## Updating Submodules

Pull latest from both repos:

```bash
git submodule update --remote --merge
git add ops-center unicorn-brigade
git commit -m "Update submodules to latest"
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python 3.12) |
| Frontend | React 18 + Vite + Tailwind |
| Auth | Keycloak (OIDC/SSO) |
| Database | PostgreSQL 16 |
| Cache | Redis |
| LLM Proxy | LiteLLM |
| Containers | Docker + Docker Compose |
| Agents | LangGraph + OpenAI Agents SDK |
| Protocols | A2A, MCP, UCP, Agent Trace |

## License

MIT License — see individual repos for details.

## Links

- [Ops-Center-OSS](https://github.com/Unicorn-Commander/Ops-Center-OSS) — The Colonel
- [Unicorn-Brigade-OSS](https://github.com/Unicorn-Commander/Unicorn-Brigade-OSS) — The General
- [unicorncommander.ai](https://unicorncommander.ai) — Production instance
</div>
