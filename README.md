# GT AI OS Community Edition

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

A self-hosted AI platform for teams and small businesses. Build and deploy custom AI agents with full data privacy and bring-your-own inference via Ollama, Groq, NVIDIA NIM, vLLM, and more.

## Table of Contents

- [Quick Start](#quick-start)
- [Features](#features)
- [Community vs Enterprise](#community-vs-enterprise)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Updating](#updating)
- [Local Models with Ollama](#local-models-with-ollama)
- [Architecture](#architecture)
- [Troubleshooting](#troubleshooting)
- [Ollama Setup](#ollama-setup)
  - [Mac Setup](#mac-setup)
  - [Ubuntu Setup](#ubuntu-setup)
  - [DGX Setup](#dgx-setup)
  - [Verify Ollama is Working](#verify-ollama-is-working)
- [Cloudflare Tunnel Setup](#cloudflare-tunnel-setup)
- [Contributing](#contributing)
- [Security](#security)
- [License](#license)

## Quick Start

**What you need before starting:** (see [System Requirements](#system-requirements) for details)
- Docker Desktop installed and running (see [Installation](#installation) for setup instructions)
- At least 16GB of RAM on your computer
- At least 20GB of free disk space

**Step 1:** Open Terminal (Mac) or Command Prompt (Linux) and paste these commands:

```bash
git clone https://github.com/GT-Edge-AI-Internal/gt-ai-os-community.git
cd gt-ai-os-community
```

**Step 2:** Run the installer for your computer type:

- **Mac (M1, M2, M3, or newer):** `./installers/install-gt2-mac.sh` ([detailed instructions](#mac-apple-silicon---m1m2m3-or-newer))
- **Ubuntu Linux:** `./installers/install-gt2-ubuntu.sh` ([detailed instructions](#ubuntu-linux))
- **NVIDIA DGX:** `sudo ./installers/install-gt2-dgx.sh` ([detailed instructions](#nvidia-dgx))

**Step 3:** Wait for installation to complete (about 10-15 minutes).

**Step 4:** Open your web browser and go to:
- **Main App:** http://localhost:3002
- **Admin Panel:** http://localhost:3001
- **Login with:** Email: `gtadmin@test.com` Password: `Test@123`

You're done! GT AI OS is now running on your computer.

**Next steps:**
- [Set up local AI models with Ollama](#local-models-with-ollama) for offline, private AI
- [Configure Cloudflare Tunnel](#cloudflare-tunnel-setup) to access from anywhere
- Having issues? Check the [Troubleshooting](#troubleshooting) section

---

## Features

- **AI Agent Builder** - Create custom AI agents with your own instructions
- **Local Model Support** - Run AI models on your own computer (completely offline)
- **Document Processing** - Upload documents and ask questions about them
- **File Management** - Securely store and organize files
- **Team Management** - Create teams and control who can access what
- **Usage Tracking** - See how your AI agents are being used

---

## Community vs Enterprise

| Feature | Community (Free) | Enterprise (Paid) |
|---------|-----------|------------|
| **Users** | Up to 5 users | Unlimited users |
| **Support** | GitHub Issues | Dedicated human support |
| **Billing & Reports** | Not included | Full financial tracking |
| **Pro Agents** | Not included | Pre-built professional agents |
| **AI Models** | Bring your own (Ollama, Groq, etc.) | Managed cloud AI included |
| **Setup** | You install it yourself | We set it up for you |
| **Cloudflare** | You configure it yourself | We manage it for you |
| **Uptime Guarantee** | None (you manage it) | 99.99% uptime guaranteed |
| **Supported Systems** | Mac, Ubuntu, DGX | Ubuntu 24.04, NVIDIA DGX |
| **Certified Hardware** | Any compatible computer | Dell, NVIDIA RTX Pro |

**Want Enterprise?** [Contact GT Edge AI](https://gtedge.ai/contact-us/)

---

## System Requirements

| Computer Type | Processor | Memory (RAM) | Storage | Notes |
|---------------|-----------|--------------|---------|-------|
| Mac | Apple M1, M2, M3, or newer | 16GB or more | 20GB free | Must install Docker Desktop first |
| Ubuntu Linux | Intel or AMD (64-bit) | 8GB or more | 50GB free | Works with Docker Desktop or Docker Engine |
| NVIDIA DGX | ARM Grace | 128GB | 1TB | Docker comes pre-installed |

---

## Installation

### Mac (Apple Silicon - M1/M2/M3 or newer)

**Step 1: Install Docker Desktop**

1. Go to https://www.docker.com/products/docker-desktop/
2. Click the blue **Download for Mac - Apple Silicon** button
3. Open the downloaded file (it ends in `.dmg`)
4. Drag the Docker icon to your Applications folder
5. Open Docker from your Applications folder
6. Wait for Docker to finish starting (you'll see a whale icon in your menu bar at the top of the screen)

**Step 2: Install Homebrew and Git**

1. Open the **Terminal** app (press Command + Space, type "Terminal", press Enter)
2. Copy and paste this entire command, then press Enter:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

3. When it asks for your password, type your Mac password (you won't see the characters as you type - that's normal)
4. Press Enter when asked to continue
5. Wait for it to finish (this takes a few minutes)
6. Then run these commands one at a time:

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
brew install git
```

**Step 3: Download and Install GT AI OS**

1. In Terminal, paste these commands one at a time:

```bash
cd ~/Desktop
git clone https://github.com/GT-Edge-AI-Internal/gt-ai-os-community.git
cd gt-ai-os-community
./installers/install-gt2-mac.sh
```

2. Wait for installation to complete (10-15 minutes)

**Step 4: Open GT AI OS**

1. Open your web browser (Safari, Chrome, etc.)
2. Go to http://localhost:3002
3. Log in with:
   - Email: `gtadmin@test.com`
   - Password: `Test@123`

---

### Ubuntu Linux

**Step 1: Install Docker**

1. Open a Terminal window
2. Copy and paste this command, then press Enter:

```bash
curl -fsSL https://get.docker.com | sh
```

3. Add yourself to the Docker group:

```bash
sudo usermod -aG docker $USER
```

4. **Important:** Log out of your computer completely, then log back in. This step is required!

**Step 2: Download and Install GT AI OS**

1. Open Terminal again and paste these commands one at a time:

```bash
git clone https://github.com/GT-Edge-AI-Internal/gt-ai-os-community.git
cd gt-ai-os-community
./installers/install-gt2-ubuntu.sh
```

2. Wait for installation to complete (10-15 minutes)

**Step 3: Open GT AI OS**

1. Open your web browser
2. Go to http://localhost:3002
3. Log in with:
   - Email: `gtadmin@test.com`
   - Password: `Test@123`

---

### NVIDIA DGX

Docker is already installed on DGX systems.

1. Open a Terminal and paste these commands:

```bash
git clone https://github.com/GT-Edge-AI-Internal/gt-ai-os-community.git
cd gt-ai-os-community
sudo ./installers/install-gt2-dgx.sh
```

2. Wait for installation to complete
3. Open http://localhost:3002 in your browser
4. Log in with: `gtadmin@test.com` / `Test@123`

---

## Updating

When a new version is available, update GT AI OS with these steps:

1. Open Terminal
2. Go to your GT AI OS folder:

```bash
cd gt-ai-os-community
```

3. Download the latest version:

```bash
git pull
```

4. Apply the update:

```bash
./scripts/deploy.sh
```

5. Wait for the update to complete

---

## Local Models with Ollama

Ollama lets you run AI models locally on your computer. Your conversations stay completely private and you don't need internet access for inference.

**Quick Setup:**

1. Install Ollama from https://ollama.com/download
2. Pull a model: `ollama pull dolphin3`
3. Add the model to GT AI OS (see [Ollama Setup](#ollama-setup) for detailed platform-specific instructions)

**Quick Reference - Endpoint URLs:**

| Platform | Endpoint URL |
|----------|--------------|
| Mac | `http://host.docker.internal:11434/v1/chat/completions` |
| Ubuntu | `http://host.docker.internal:11434/v1/chat/completions` |
| DGX | `http://ollama-host:11434/v1/chat/completions` |

---

## Architecture

GT AI OS runs as several connected services:

```
┌─────────────────────────────────────────────────────────────┐
│                      GT AI OS                               │
├─────────────────┬─────────────────┬─────────────────────────┤
│  Control Panel  │   Tenant App    │    Resource Cluster     │
│  (Admin UI)     │   (User UI)     │    (AI Inference)       │
├─────────────────┴─────────────────┴─────────────────────────┤
│                    PostgreSQL                               │
│              Control DB  │  Tenant DB (with PGVector)       │
└─────────────────────────────────────────────────────────────┘
```

**What each part does:**
- **Control Panel** - Where admins manage users, models, and settings
- **Tenant App** - Where users chat with AI agents
- **Resource Cluster** - Handles AI model requests
- **PostgreSQL** - Stores all your data securely

---

## Troubleshooting

Having problems? Find your issue below and follow the steps.

---

### "I see 'docker: command not found'"

**What this means:** Docker isn't installed on your computer.

**How to fix it:**

1. Go back to the [Installation](#installation) section
2. Follow the steps for your computer type to install Docker Desktop
3. Make sure Docker is running before trying again

---

### "I see 'permission denied' when running docker"

**What this means:** Your computer user account doesn't have permission to use Docker.

**How to fix it (Ubuntu/Linux only):**

1. Open Terminal
2. Copy and paste this command, then press Enter:
   ```bash
   sudo usermod -aG docker $USER
   ```
3. Type your password when asked (you won't see characters as you type - that's normal)
4. **Important:** You must log out of your computer completely, then log back in
5. Try your command again

---

### "I see 'port already in use'"

**What this means:** Another program on your computer is using the same connection port that GT AI OS needs.

**How to fix it:**

1. Open Terminal
2. Go to your GT AI OS folder:
   ```bash
   cd ~/Desktop/gt-ai-os-community
   ```
   (Or wherever you installed it)
3. Stop everything:
   ```bash
   docker compose down
   ```
4. Wait 10 seconds, then start again:
   ```bash
   docker compose up -d
   ```

**Still not working?** Restart your computer and try again.

---

### "The page won't load in my browser"

**What this means:** Either Docker isn't running, or the services haven't started yet.

**How to fix it:**

**Step 1: Check if Docker is running**

- **Mac:** Look at the top-right of your screen (menu bar). Do you see a whale icon? 🐳
  - If yes, Docker is running
  - If no, open the **Docker** app from your Applications folder
- **Ubuntu:** Open Terminal and type:
  ```bash
  docker ps
  ```
  - If you see a list of containers, Docker is running
  - If you see an error, start Docker with: `sudo systemctl start docker`

**Step 2: Wait for services to start**

After starting GT AI OS, wait 2-3 minutes for everything to load. The first time takes longer.

**Step 3: Try a different browser**

If one browser doesn't work, try another (Chrome, Firefox, Safari).

**Step 4: Check if services are running**

Open Terminal and type:
```bash
docker ps
```

You should see about 10 containers listed. If you see fewer, or none, run:
```bash
cd ~/Desktop/gt-ai-os-community
docker compose up -d
```

---

### "Services show 'unhealthy' or 'starting'"

**What this means:** The services are still loading. This is normal!

**How to fix it:**

1. Wait 2-3 minutes
2. Refresh your browser page
3. If still unhealthy after 5 minutes, restart everything:
   ```bash
   cd ~/Desktop/gt-ai-os-community
   docker compose down
   docker compose up -d
   ```

---

### "I forgot the login password"

**Default login credentials:**
- **Email:** `gtadmin@test.com`
- **Password:** `Test@123`

These work for both the Control Panel (http://localhost:3001) and Tenant App (http://localhost:3002).

---

### "My AI agent doesn't respond"

**What this means:** The AI model might not be connected or configured correctly.

**How to fix it:**

1. **Check if you have a model configured:**
   - Open Control Panel: http://localhost:3001
   - Go to **Models** in the left sidebar
   - You should see at least one model listed
   - If empty, you need to [set up Ollama](#ollama-setup) or add an API-based model

2. **Check if the model is assigned to your tenant:**
   - In Control Panel, go to **Tenant Access**
   - Make sure your model is assigned to a tenant

3. **If using Ollama, check it's running:**
   ```bash
   ollama list
   ```
   - If you see "command not found", [install Ollama first](#ollama-setup)
   - If you see your models listed, Ollama is working

---

### "How do I see what's happening behind the scenes?"

If something isn't working and you want to see the error messages:

1. Open Terminal
2. Go to your GT AI OS folder:
   ```bash
   cd ~/Desktop/gt-ai-os-community
   ```
3. View the logs:
   ```bash
   docker compose logs -f
   ```
4. To stop viewing logs, press `Ctrl+C` (hold Control and press C)

**Tip:** To see logs for just one service:
```bash
docker compose logs -f tenant-backend
```

---

### "I want to start completely fresh (delete everything)"

**Warning:** This will delete ALL your data, including users, agents, and conversations.

1. Open Terminal
2. Go to your GT AI OS folder:
   ```bash
   cd ~/Desktop/gt-ai-os-community
   ```
3. Stop and remove everything:
   ```bash
   docker compose down -v
   ```
4. Run the installer again:
   - **Mac:** `./installers/install-gt2-mac.sh`
   - **Ubuntu:** `./installers/install-gt2-ubuntu.sh`
   - **DGX:** `sudo ./installers/install-gt2-dgx.sh`

---

### "Nothing above helped - I need more support"

1. **Check GitHub Issues:** Someone might have had the same problem:
   https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/issues

2. **Open a new issue:** Describe your problem and include:
   - What you were trying to do
   - What error message you saw
   - What computer you're using (Mac, Ubuntu, DGX)
   - The output of `docker compose logs` (last 50 lines)

---

## Ollama Setup

Set up local AI models with Ollama for offline inference. Ollama runs on your host machine (outside Docker) and GT AI OS containers connect to it.

### Recommended Models

| Model | Size | VRAM Required | Best For |
|-------|------|---------------|----------|
| dolphin3 | ~5GB | 6GB+ | General chat, coding help |
| qwen3-coder:30b | ~19GB | 24GB+ | Code generation, agentic coding |
| gemma3:27b | ~17GB | 20GB+ | General tasks, multilingual |

### Quick Reference

| Platform | Model Endpoint URL |
|----------|-------------------|
| macOS | `http://host.docker.internal:11434/v1/chat/completions` |
| Ubuntu | `http://host.docker.internal:11434/v1/chat/completions` |
| DGX | `http://ollama-host:11434/v1/chat/completions` |

---

### Mac Setup

#### Step 1: Install Ollama

Download from https://ollama.com/download or run:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

#### Step 2: Pull a Model

```bash
ollama pull dolphin3
```

#### Step 3: Add Model to GT AI OS

1. Open Control Panel: http://localhost:3001
2. Log in with `gtadmin@test.com` / `Test@123`
3. Go to **Models** → **Add Model**
4. Fill in:
   - **Model ID:** `dolphin3` (must match exactly what you pulled)
   - **Provider:** `Local Inference (Manual)`
   - **Endpoint URL:** `http://host.docker.internal:11434/v1/chat/completions`
   - **Model Type:** `LLM`
   - **Context Length:** `131072`
   - **Max Tokens:** `4096`
5. Click **Save**
6. Go to **Tenant Access** → **Assign Model to Tenant**
7. Select your model, tenant, and rate limit

---

### Ubuntu Setup

#### Step 1: Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

#### Step 2: Configure Systemd

Create the override configuration for optimal performance:

```bash
sudo mkdir -p /etc/systemd/system/ollama.service.d

sudo tee /etc/systemd/system/ollama.service.d/override.conf > /dev/null <<'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_CONTEXT_LENGTH=131072"
Environment="OLLAMA_FLASH_ATTENTION=1"
Environment="OLLAMA_KEEP_ALIVE=4h"
Environment="OLLAMA_MAX_LOADED_MODELS=2"
EOF
```

**Configuration explained:**
- `OLLAMA_HOST=0.0.0.0:11434` - Listen on all network interfaces (required for Docker)
- `OLLAMA_CONTEXT_LENGTH=131072` - 128K token context window
- `OLLAMA_FLASH_ATTENTION=1` - Enable flash attention for better performance
- `OLLAMA_KEEP_ALIVE=4h` - Keep models loaded for 4 hours
- `OLLAMA_MAX_LOADED_MODELS=2` - Allow 2 models loaded simultaneously (adjust based on VRAM)

#### Step 3: Start Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable ollama
sudo systemctl start ollama
```

#### Step 4: Pull a Model

```bash
ollama pull dolphin3
```

#### Step 5: Add Model to GT AI OS

1. Open Control Panel: http://localhost:3001
2. Log in with `gtadmin@test.com` / `Test@123`
3. Go to **Models** → **Add Model**
4. Fill in:
   - **Model ID:** `dolphin3` (must match exactly what you pulled)
   - **Provider:** `Local Inference (Manual)`
   - **Endpoint URL:** `http://host.docker.internal:11434/v1/chat/completions`
   - **Model Type:** `LLM`
   - **Context Length:** `131072`
   - **Max Tokens:** `4096`
5. Click **Save**
6. Go to **Tenant Access** → **Assign Model to Tenant**
7. Select your model, tenant, and rate limit

---

### DGX Setup

#### Step 1: Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

#### Step 2: Configure Systemd

```bash
sudo mkdir -p /etc/systemd/system/ollama.service.d

sudo tee /etc/systemd/system/ollama.service.d/override.conf > /dev/null <<'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_CONTEXT_LENGTH=131072"
Environment="OLLAMA_FLASH_ATTENTION=1"
Environment="OLLAMA_KEEP_ALIVE=4h"
Environment="OLLAMA_MAX_LOADED_MODELS=3"
EOF
```

#### Step 3: Start Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable ollama
sudo systemctl start ollama
```

#### Step 4: Pull Models

DGX systems have more VRAM, so you can run larger models:

```bash
ollama pull dolphin3
ollama pull qwen3-coder:30b
ollama pull gemma3:27b
```

#### Step 5: Add Model to GT AI OS

1. Open Control Panel: http://localhost:3001
2. Log in with `gtadmin@test.com` / `Test@123`
3. Go to **Models** → **Add Model**
4. Fill in:
   - **Model ID:** `dolphin3` (or `qwen3-coder:30b`, `gemma3:27b`)
   - **Provider:** `Local Inference (Manual)`
   - **Endpoint URL:** `http://ollama-host:11434/v1/chat/completions`
   - **Model Type:** `LLM`
   - **Context Length:** `131072`
   - **Max Tokens:** `4096`
5. Click **Save**
6. Go to **Tenant Access** → **Assign Model to Tenant**
7. Select your model, tenant, and rate limit

---

### Verify Ollama is Working

**Check Ollama is running:**

```bash
ollama list                              # Shows installed models
curl http://localhost:11434/api/version  # Should return version JSON
```

**Test from GT AI OS container:**

```bash
# Mac/Ubuntu
docker exec gentwo-resource-cluster curl http://host.docker.internal:11434/api/version

# DGX
docker exec gentwo-resource-cluster curl http://ollama-host:11434/api/version
```

**Test in application:**

1. Open Tenant App: http://localhost:3002
2. Create or select an agent using your Ollama model
3. Send a test message

---

## Cloudflare Tunnel Setup

A Cloudflare Tunnel lets you access GT AI OS from anywhere on the internet, without complicated network configuration.

### What You Need Before Starting

- A free Cloudflare account (sign up at https://cloudflare.com)
- A domain name that's connected to Cloudflare

---

### Step 1: Create a Tunnel

1. Go to the Cloudflare Zero Trust Dashboard: https://one.dash.cloudflare.com/
2. If prompted, select your account
3. In the left sidebar, click **Networks**
4. Click **Tunnels**
5. Click the **Create a tunnel** button
6. Choose **Cloudflared** and click **Next**
7. Give your tunnel a name like `gt-ai-os` and click **Save tunnel**

---

### Step 2: Install the Tunnel Software

After creating the tunnel, Cloudflare shows you install commands. The page will look different depending on your computer type.

**For Mac:**
1. Look for the macOS tab on the Cloudflare page
2. Copy the command shown (it will look something like `brew install cloudflared && cloudflared service install eyJhI...`)
3. Open Terminal on your Mac
4. Paste the command and press Enter

**For Ubuntu/DGX:**
1. Look for the Debian tab on the Cloudflare page
2. You'll see commands to download and install cloudflared
3. Copy and paste each command into your Terminal

**How to know it worked:** Go back to the Cloudflare dashboard. Under your tunnel, you should see "Connected" with a green dot.

---

### Step 3: Set Up Your Web Addresses

Now you'll tell Cloudflare which addresses should connect to GT AI OS.

**Add the main app:**
1. On the tunnel page, click **Add a public hostname**
2. Fill in:
   - **Subdomain:** `app` (or whatever you want, like `ai`)
   - **Domain:** Select your domain from the dropdown
   - **Type:** `HTTP`
   - **URL:** `localhost:3002`
3. Click **Save hostname**

**Add the admin panel:**
1. Click **Add a public hostname** again
2. Fill in:
   - **Subdomain:** `admin`
   - **Domain:** Select your domain
   - **Type:** `HTTP`
   - **URL:** `localhost:3001`
3. Click **Save hostname**

---

### Step 4: Update GT AI OS Settings

Tell GT AI OS about its new public web address:

1. Open the Control Panel: http://localhost:3001
2. Log in with `gtadmin@test.com` / `Test@123`
3. Click **Tenants** in the left sidebar
4. Click on your tenant name
5. Find the **App URL** field
6. Change it to your new address (for example: `https://app.yourdomain.com`)
7. Click **Save**

---

### You're Done!

Your GT AI OS is now accessible from anywhere:
- **Main App:** `https://app.yourdomain.com`
- **Admin Panel:** `https://admin.yourdomain.com`

To check that everything is working, go to the Cloudflare dashboard and look at **Networks** > **Tunnels**. Your tunnel should show "Connected" with a green dot.

---

## Contributing

Found a bug? Have an idea for a new feature?

Open an issue on GitHub: https://github.com/GT-Edge-AI-Internal/gt-ai-os-community/issues

See [CONTRIBUTING.md](CONTRIBUTING.md) for more details.

---

## Security

Found a security problem? Please report it privately to: security@gtedge.ai

See [SECURITY.md](SECURITY.md) for our full security policy.

---

## License

GT AI OS Community Edition is free to use under the Apache License 2.0.

See the [LICENSE](LICENSE) file for full details.

---

**GT AI OS Community Edition** | Made by [GT Edge AI](https://gtedge.ai)
