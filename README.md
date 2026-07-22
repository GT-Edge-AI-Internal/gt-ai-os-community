# GT AI OS Community Edition

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

GT AI OS Community Edition is a self-hosted, web-based generative AI platform for individuals and teams who need document-centric workflows with strong data-privacy controls. Install on **Ubuntu (x86_64)**, **NVIDIA DGX OS 7 (ARM64)**, or **Apple Silicon macOS** using Docker and the runbooks in this repository’s wiki.

> **🚀 New: GT AI OS Gen 3 is here.** Check out our next-generation platform at [github.com/GT-Edge-AI/GT-AI-OS](https://github.com/GT-Edge-AI/GT-AI-OS).

---

## Installation

Choose your platform for step-by-step instructions:

| Platform | Guide |
|----------|-------|
| **Ubuntu** 24.04 (x86_64) | [Installation — Ubuntu](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Installation#ubuntu-installation) |
| **NVIDIA DGX OS 7** (ARM64) | [Installation — DGX](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Installation#dgx-installation) |
| **macOS** (Apple Silicon M1+) | [Installation — macOS](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Installation#macos-installation) |

Each platform uses its own install script. Select the guide that matches your OS and CPU architecture.

**Start here:** [Installation (wiki)](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Installation)

---

## Update an existing installation

From your clone of this repository:

**macOS:**

```bash
cd ~/gt-ai-os-community && git pull && bash scripts/deploy.sh
```

**Ubuntu:**

```bash
cd ~/gt-ai-os-community && git pull && bash scripts/deploy.sh
```

**DGX:**

```bash
cd ~/gt-ai-os-community && sudo git pull && sudo bash scripts/deploy.sh
```

For troubleshooting and release notes, see [Updating](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Updating).

---

## Access

| App | URL | Default login (first install) |
|-----|-----|-----------------------------|
| Control Panel | http://localhost:3001 | `gtadmin@test.com` / `Test@123` |
| Tenant App | http://localhost:3002 | `gtadmin@test.com` / `Test@123` |

Change default passwords after first sign-in in production use.

---

## Platform requirements

| Platform | Architecture | Minimum resources |
|----------|--------------|-------------------|
| **Ubuntu** 24.04 | x86_64 | 4 CPU cores, 16 GB RAM, 50 GB SSD |
| **DGX OS 7** | ARM64 (Grace) | See [DGX installation guide](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Installation#dgx-installation) |
| **macOS** | Apple Silicon (M1+) | 16 GB RAM, 20 GB+ free disk |

A typical install uses about **7 GB RAM** at steady state. Local models, conversation history, and datasets require additional disk space.

**Supported:** Ubuntu on Proxmox with GPU passthrough. **Not supported:** Windows hosts.

Install scripts for macOS target **Apple Silicon only** (not Intel Macs).

---

## Inference and privacy

- Connect **local** inference (Ollama) or **external** APIs (NVIDIA NIM, Groq, vLLM, SGLang, and others supported in the Control Panel).
- For document workflows, use **local models** or providers that offer **zero data retention** when privacy is required.
- As of **v2.0.33**, Community Edition is **not multimodal**: it does not generate or process images, video, or audio in the core product path.

---

## Embeddings and GPU acceleration

Retrieval-augmented generation (RAG) uses an embedding model to index uploaded files. **NVIDIA GPUs** and **Apple Silicon** accelerate embedding and dataset ingestion.

| Topic | Detail |
|-------|--------|
| **Embedding model (v2.0.34+)** | `BAAI/bge-m3` (~3.78 GB VRAM when loaded on GPU) |
| **Minimum GPU VRAM at install** | 4 GB (smaller GPUs may be supported in a future release) |
| **Ubuntu + NVIDIA** | Install the GPU before running the Ubuntu runbook; drivers are installed by the runbook |
| **macOS** | No extra drivers; Metal acceleration is part of the standard install |
| **CPU-only** | Supported; dataset uploads are slower without GPU acceleration |
| **GPU added after install** | Not supported for switching embeddings CPU→GPU in v2.0.34; planned for a future release |

---

## Features

- **Agent builder** — Custom agents with system prompts, categories, role-based access, and guardrails
- **Local models** — Run models with Ollama for offline inference
- **Document processing** — Datasets and RAG-backed chat over your files
- **Teams** — Shared access to agents and datasets within a workgroup
- **Observability** — Usage dashboards, chat logs, and operational metrics

---

## Documentation

Full guides are in the **[wiki](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki)**:

| Topic | Description |
|-------|-------------|
| [Installation](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Installation) | Fresh install for Ubuntu, DGX, and macOS |
| [Updating](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Updating) | Upgrade an existing deployment |
| [Control Panel Guide](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Control-Panel-Guide) | Admin configuration |
| [Tenant App Guide](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Tenant-App-Guide) | End-user guide |
| [Ollama Setup](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Ollama-Setup) | Local model configuration |
| [NVIDIA NIM](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Control-Panel-Guide#adding-nvidia-nim-models) | GPU-accelerated cloud inference |
| [Groq](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Control-Panel-Guide#adding-groq-models) | Fast cloud inference |
| [Cloudflare Tunnel](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Cloudflare-Tunnel-Setup) | Remote access without port forwarding |
| [Troubleshooting](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Troubleshooting) | Common issues |

---

## Quick commands

```bash
docker compose ps              # Service status
docker compose logs -f         # Follow logs
docker compose down            # Stop stack
docker compose up -d           # Start stack
```

---

## Community vs Enterprise

| Capability | Community (free) | Enterprise (paid) |
|------------|------------------|-------------------|
| **Users** | Up to 10 | Licensed seats |
| **Support** | GitHub Issues | Dedicated support |
| **Billing and reports** | — | Financial controls |
| **Professional agents** | — | Pre-built agent packs |
| **Inference** | Bring your own | Fully managed option |
| **Deployment** | Self-hosted (DIY) | Managed deployment |
| **Uptime** | Self-operated | 99.99% SLA (managed) |

**Enterprise:** [Contact GT Edge AI](https://gtedge.ai/contact-us/)

---

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                          GT AI OS                              │
├──────────────────┬──────────────────────┬──────────────────────┤
│   Control Panel  │      Tenant App      │   Resource Cluster   │
│    (Admin UI)    │       (User UI)      │ (AI inference routing)│
├──────────────────┴──────────────────────┴──────────────────────┤
│                         PostgreSQL                              │
│                  Control DB  │  Tenant DB                       │
└────────────────────────────────────────────────────────────────┘
```

---

## Support

- **Runbook issues:** [GitHub Issues](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/issues)
- **Security:** [SECURITY.md](SECURITY.md) and [contact GT Edge AI](https://gtedge.ai/contact-us)

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).

---

**GT AI OS Community Edition** · [GT Edge AI](https://gtedge.ai)
