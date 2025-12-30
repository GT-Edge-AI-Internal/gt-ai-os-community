# GT AI OS Community Edition

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

GT AI OS software is intended to provide easy to use "daily driver" web based generative AI for processing documents & files with data privacy for individuals and organizations.
You can install GT AI OS on Ubuntu x86, NVIDIA DGX OS 7 ARM and Apple Silicon macOS hosts using Docker.

Minimum 4 CPU cores, 16GB RAM and 50GB SSD storage required for the application.
GT AI OS will usually use about 7GB RAM when fully installed.

Local models, conversation history and datasets will consume additional SSD or disk storage.

The provided runbooks are intended to provide a smooth installation and include commands for dependencies.
Open an issue on the repo if you have problems with the runbooks.

Build and deploy custom generative AI agents and bring-your-own local or external API inference via NVIDIA NIM, Ollama, Groq, vLLM, SGLang and more.

GT AI OS is ideal for working with documents and files that need data privacy.
It is not multimodal and can't generate or process images, videos or audio as of version 2.0.33.

Ensure that you are using local or external inference with zero data retention features if you want your data to remain private.

[GT AI OS Wiki](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki)

## Supported Platforms

| Platform | Host Architecture |
|----------|--------------|
| **Ubuntu Linux** 24.04 | x86_64 |
| **NVIDIA DGX OS 7** (Optimized for Grace Blackwell Architecture) | ARM64 |
| **macOS** (Apple Silicon M1+) | ARM64 |

Ubuntu VM's running on Proxmox with raw all functions GPU passthrough works.
Windows is currently not supported.

macoS Install scripts are designed for Apple Silicon only.

Note that the install scripts are unique for each OS and hardware architecture.
Carefully choose the correct installation script for your host.

## Embedding model GPU acceleration:
NVIDIA GPU's and Apple Silicon will significantly accelerate embedding acceleration (uploading files and documents for Retrieval Augemented Generation "RAG").
As of release 2.0.34 the minimum GPU VRAM needed at installation time is 4GB as the embedding model installed is teh BAAI/bge-m3 which consumes around 3.78GB once fully loaded onto the GPU.
We will be adjusting the installation scripts in future release so that smaller GPU's down to 1GB can be used on mini desktop computers.

Ensure that your NVIDIA GPU hardware is physically installed prior to starting the GT AI OS installation.
Note that all NVIDIA drivers and dependencies will be installed during the standard Ubuntu runbook.

There are no aditional drivers or dependencies needed for using Apple Silicon to accelerate the embedding model as that is part of the standard installation.

At v2.0.34, once you install GT AI OS, you cannot install GPU hardware and switch from CPU to GPU for embeddings.
We are looking to fix this in a future release.

If you do not have an NVIDIA GPU installed in your host, then the CPU and host RAM will be used for running the embedding model.
CPU vs GPU accelerated embedding will result in slower file uploads when adding files to datasets.

---

## Features

- **AI Agent Builder** - Create custom AI agents with your own system prompts, categorization, role base access and guardrails
- **Local Model Support** - Run local AI models with Ollama (completely offline)
- **Document Processing** - Upload documents into datasets and create agents to interact with them
- **Create Teams** - For setting up a workgroup that has Team based access to agents and dataasets
- **Observability** - See metrics dashboards including agents, models and dataset usage, chat logs and more

---

## Documentation

| Topic | Description |
|-------|-------------|
| [Installation](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Installation) | Detailed setup instructions |
| [Updating](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Updating) | Keep GT AI OS up to date |
| [NVIDIA NIM Setup](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Control-Panel-Guide#adding-nvidia-nim-models) | Enterprise GPU-accelerated inference |
| [Ollama Setup](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Ollama-Setup) | Set up local AI models |
| [Groq Cloud Setup](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Control-Panel-Guide#adding-groq-models) | Ultra-fast cloud inference |
| [Cloudflare Tunnel](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Cloudflare-Tunnel-Setup) | Access GT AI OS from anywhere |
| [Troubleshooting](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Troubleshooting) | Common issues and solutions |

---

## Community vs Enterprise

| Feature | Community (Free) | Enterprise (Paid) |
|---------|-----------|------------|
| **Users** | Up to 10 users | User licenses per seat |
| **Support** | GitHub Issues | Dedicated human support |
| **Billing & Reports** | Not included | Full financial tracking |
| **Pro Agents** | Not included | Pre-built professional agents |
| **AI Inference** | BYO/DIY | Fully Managed |
| **Setup** | DIY | Fully Managed |
| **Uptime Guarantee** | Self | 99.99% uptime SLA |

**Want Enterprise?** [Contact GT Edge AI](https://gtedge.ai/contact-us/)

---

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                          GT AI OS                              │
├──────────────────┬──────────────────────┬──────────────────────┤
│   Control Panel  │      Tenant App      │   Resource Cluster   │
│    (Admin UI)    │       (User UI)      │(AI Inference Routing)│
├──────────────────┴──────────────────────┴──────────────────────┤
│                          Postgres DB                            │
│                  Control DB  │  Tenant DB                      │
└────────────────────────────────────────────────────────────────┘
```

---

## Bug and issue reporting:

Found a bug? Have an idea? Open an issue: https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/issues

---

## Security

Found a security issue? Report via [our contact form](https://gtedge.ai/contact-us)

See [SECURITY.md](SECURITY.md) for our security policy.

---

## License

Apache License 2.0 - See [LICENSE](LICENSE)

---

**GT AI OS Community Edition** | Made by [GT Edge AI](https://gtedge.ai)
