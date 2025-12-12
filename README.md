# GT AI OS Community Edition

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

A self-hosted AI platform for teams and small businesses. Build and deploy custom AI agents with full data privacy and bring-your-own inference via NVIDIA NIM, Ollama, Groq, vLLM, and more.

## Supported Platforms

| Platform | Host Architecture | Status |
|----------|--------------|--------|
| **Ubuntu Linux** 24.04 | x86_64 | Supported |
| **NVIDIA DGX OS 7** (Optimized for Grace Blackwell Architecture) | ARM64 | Supported |
| **macOS** (Apple Silicon M1+) | ARM64 | Supported |

---

## Features

- **AI Agent Builder** - Create custom AI agents with your own instructions
- **Local Model Support** - Run local AI models with Ollama (completely offline)
- **Document Processing** - Upload documents and ask questions about them
- **Team Management** - Create teams and control who can access what
- **Usage Tracking** - See how your AI agents are being used

---

## Documentation

| Topic | Description |
|-------|-------------|
| [Installation](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Installation) | Detailed setup instructions |
| [Updating](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Updating) | Keep GT AI OS up to date |
| [NVIDIA NIM Setup](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/NVIDIA-NIM-Setup) | Enterprise GPU-accelerated inference |
| [Ollama Setup](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Ollama-Setup) | Set up local AI models |
| [Groq Cloud Setup](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Groq-Cloud-Setup) | Ultra-fast cloud inference |
| [Cloudflare Tunnel](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Cloudflare-Tunnel-Setup) | Access GT AI OS from anywhere |
| [Troubleshooting](https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/wiki/Troubleshooting) | Common issues and solutions |

---

## Community vs Enterprise

| Feature | Community (Free) | Enterprise (Paid) |
|---------|-----------|------------|
| **Users** | Up to 50 users | User licenses per seat |
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
│                          PostgreSQL                            │
│                  Control DB  │  Tenant DB                      │
└────────────────────────────────────────────────────────────────┘
```

---

## Contributing

Found a bug? Have an idea? Open an issue: https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/issues

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## Security

Found a security issue? Report via [our contact form](https://gtedge.ai/contact-us)

See [SECURITY.md](SECURITY.md) for our security policy.

---

## License

Apache License 2.0 - See [LICENSE](LICENSE)

---

**GT AI OS Community Edition** | Made by [GT Edge AI](https://gtedge.ai)
