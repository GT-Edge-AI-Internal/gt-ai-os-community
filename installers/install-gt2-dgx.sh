#!/bin/bash
# GT 2.0 NVIDIA DGX Installer
# Installation script for NVIDIA DGX systems with Grace ARM architecture
# Version: 1.0.0

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALLER_VERSION="1.0.0"
INSTALL_DIR="/opt/gt2"
MIN_RAM_GB=64
MIN_DISK_GB=50
GITHUB_REPO="https://github.com/GT-Edge-AI-Internal/gt-ai-os-community.git"
RELEASE_URL="https://api.github.com/repos/GT-Edge-AI-Internal/gt-ai-os-community/releases/latest"

# Flags
UNATTENDED=false
SKIP_DOCKER_CHECK=false
USE_RELEASE=false
INSTALL_OLLAMA=false
BRANCH="main"
RUNNING_FROM_REPO=false

# Functions
print_header() {
    echo ""
    echo -e "${BLUE}================================================================${NC}"
    echo -e "${BLUE}  GT AI OS Community Edition${NC}"
    echo -e "${BLUE}  NVIDIA DGX Installer v${INSTALLER_VERSION}${NC}"
    echo -e "${BLUE}================================================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Install GT 2.0 Enterprise AI Platform on NVIDIA DGX systems

OPTIONS:
    -h, --help              Show this help message
    -v, --version           Show installer version
    -u, --unattended        Run in non-interactive mode
    -d, --dir PATH          Installation directory (default: ${INSTALL_DIR})
    -b, --branch BRANCH     Git branch to clone (default: main)
    --skip-docker-check     Skip Docker installation check
    --use-release           Download latest release instead of cloning git repo
    --install-ollama        Install and configure Ollama for local LLM inference

REQUIREMENTS:
    - NVIDIA DGX OS or Ubuntu with NVIDIA drivers
    - ARM64 architecture (Grace)
    - 64GB+ RAM
    - 50GB+ free disk space
    - NVIDIA Container Runtime
    - sudo access

EXAMPLES:
    # Interactive installation
    sudo $0

    # Unattended installation with Ollama
    sudo $0 --unattended --install-ollama

    # Custom directory with pre-built release
    sudo $0 --dir /data/gt2 --use-release

EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -v|--version)
                echo "GT 2.0 DGX Installer v${INSTALLER_VERSION}"
                exit 0
                ;;
            -u|--unattended)
                UNATTENDED=true
                shift
                ;;
            -d|--dir)
                INSTALL_DIR="$2"
                shift 2
                ;;
            -b|--branch)
                BRANCH="$2"
                shift 2
                ;;
            --skip-docker-check)
                SKIP_DOCKER_CHECK=true
                shift
                ;;
            --use-release)
                USE_RELEASE=true
                shift
                ;;
            --install-ollama)
                INSTALL_OLLAMA=true
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "This installer must be run as root (use sudo)"
        exit 1
    fi

    print_success "Running as root"
}

# Detect if running from within an already-cloned GT repo
detect_existing_repo() {
    # Get the directory where the script is located
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local repo_root="$(dirname "$script_dir")"

    # Check if this looks like a GT repo (has key files)
    if [ -f "$repo_root/docker-compose.yml" ] && \
       [ -d "$repo_root/apps" ] && \
       [ -d "$repo_root/.git" ]; then
        print_info "Detected: Running from within cloned repository"
        INSTALL_DIR="$repo_root"
        RUNNING_FROM_REPO=true
        print_success "Using existing repo at: ${INSTALL_DIR}"
    fi
}

check_dgx_system() {
    print_info "Checking DGX system..."

    # Check for DGX OS or Ubuntu
    if [ -f /etc/os-release ]; then
        source /etc/os-release
        if [[ "$ID" == "dgx" ]] || [[ "$ID" == "ubuntu" ]]; then
            print_success "System: $PRETTY_NAME"
        else
            print_warning "Not DGX OS or Ubuntu (found: $ID)"
            if [ "$UNATTENDED" = false ]; then
                read -p "Continue anyway? (y/n): " continue_install
                if [ "$continue_install" != "y" ]; then
                    exit 1
                fi
            fi
        fi
    else
        print_warning "Cannot determine OS type"
    fi
}

check_architecture() {
    print_info "Checking CPU architecture..."

    local arch=$(uname -m)

    if [[ "$arch" != "arm64" && "$arch" != "aarch64" ]]; then
        print_warning "Expected ARM64 architecture (found: $arch)"
        if [ "$UNATTENDED" = false ]; then
            read -p "Continue anyway? (y/n): " continue_install
            if [ "$continue_install" != "y" ]; then
                exit 1
            fi
        fi
    else
        print_success "Architecture: $arch (ARM64)"
    fi
}

check_nvidia_gpu() {
    print_info "Checking for NVIDIA GPU..."

    if ! command -v nvidia-smi &> /dev/null; then
        print_warning "nvidia-smi not found - GPU may not be available"
        return
    fi

    if nvidia-smi > /dev/null 2>&1; then
        local gpu_info=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
        print_success "GPU detected: $gpu_info"

        # Display GPU count
        local gpu_count=$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l)
        print_info "GPU count: $gpu_count"
    else
        print_warning "nvidia-smi failed - GPU drivers may not be loaded"
    fi
}

check_nvidia_container_runtime() {
    print_info "Checking NVIDIA Container Runtime..."

    if [ "$SKIP_DOCKER_CHECK" = true ]; then
        return
    fi

    if ! command -v docker &> /dev/null; then
        print_error "Docker not found. Install Docker first."
        exit 1
    fi

    # Check if nvidia runtime is available
    if docker info 2>/dev/null | grep -q "nvidia"; then
        print_success "NVIDIA Container Runtime detected"
    else
        print_warning "NVIDIA Container Runtime not found"

        if [ "$UNATTENDED" = false ]; then
            read -p "Install NVIDIA Container Toolkit? (y/n): " install_nvidia
            if [ "$install_nvidia" = "y" ]; then
                install_nvidia_container_toolkit
            fi
        fi
    fi
}

install_nvidia_container_toolkit() {
    print_info "Installing NVIDIA Container Toolkit..."

    # Add NVIDIA repository
    distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
        tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

    # Install
    apt-get update -qq
    apt-get install -y -qq nvidia-container-toolkit

    # Configure Docker
    nvidia-ctk runtime configure --runtime=docker
    systemctl restart docker

    print_success "NVIDIA Container Toolkit installed"
}

check_ram() {
    print_info "Checking available RAM..."

    local ram_kb=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    local ram_gb=$((ram_kb / 1024 / 1024))

    if [ "$ram_gb" -lt "$MIN_RAM_GB" ]; then
        print_error "Minimum ${MIN_RAM_GB}GB RAM required for DGX (found: ${ram_gb}GB)"
        exit 1
    fi

    print_success "RAM: ${ram_gb}GB"
}

check_disk_space() {
    print_info "Checking available disk space..."

    local install_parent=$(dirname "$INSTALL_DIR")
    local available_gb=$(df -BG "$install_parent" | tail -1 | awk '{print $4}' | sed 's/G//')

    if [ "$available_gb" -lt "$MIN_DISK_GB" ]; then
        print_error "Minimum ${MIN_DISK_GB}GB free disk space required (found: ${available_gb}GB)"
        exit 1
    fi

    print_success "Available disk space: ${available_gb}GB"
}

check_ollama() {
    if [ "$INSTALL_OLLAMA" = false ] && [ "$UNATTENDED" = true ]; then
        return
    fi

    print_info "Checking for Ollama..."

    if command -v ollama &> /dev/null; then
        print_success "Ollama found: $(ollama --version 2>&1 | head -1)"
        return
    fi

    print_info "Ollama not found"

    if [ "$INSTALL_OLLAMA" = false ] && [ "$UNATTENDED" = false ]; then
        read -p "Install Ollama for local LLM inference? (y/n): " install_ollama_choice
        if [ "$install_ollama_choice" = "y" ]; then
            INSTALL_OLLAMA=true
        fi
    fi

    if [ "$INSTALL_OLLAMA" = true ]; then
        install_ollama_service
    fi
}

install_ollama_service() {
    print_info "Installing Ollama..."

    # Download and install Ollama
    curl -fsSL https://ollama.ai/install.sh | sh

    # Configure Ollama to listen on all interfaces
    mkdir -p /etc/systemd/system/ollama.service.d

    cat > /etc/systemd/system/ollama.service.d/override.conf << 'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_ORIGINS=*"
Environment="CUDA_VISIBLE_DEVICES=0"
Environment="OLLAMA_NUM_PARALLEL=4"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
EOF

    # Reload and start Ollama
    systemctl daemon-reload
    systemctl enable ollama
    systemctl start ollama

    # Wait for Ollama to be ready
    sleep 5

    print_success "Ollama installed and running"

    # Pull a default model
    if [ "$UNATTENDED" = false ]; then
        read -p "Pull llama3.1:8b model now? (y/n): " pull_model
        if [ "$pull_model" = "y" ]; then
            print_info "Pulling llama3.1:8b (this may take several minutes)..."
            ollama pull llama3.1:8b
            print_success "Model downloaded"
        fi
    fi
}

cleanup_existing_containers() {
    # Find all containers with gentwo- prefix (running or stopped)
    local existing_containers=$(docker ps -a --filter "name=gentwo-" --format "{{.Names}}" 2>/dev/null || true)

    if [ -n "$existing_containers" ]; then
        print_warning "Found existing GT 2.0 containers"

        # Stop running containers
        print_info "Stopping existing containers..."
        docker ps -q --filter "name=gentwo-" | xargs -r docker stop 2>/dev/null || true

        # Remove all containers
        print_info "Removing existing containers..."
        docker ps -aq --filter "name=gentwo-" | xargs -r docker rm -f 2>/dev/null || true

        print_success "Existing containers removed"
    fi

    # Also clean up orphaned volumes and networks
    # Match both internal (gt-20, gt2) and community (gt-ai-os-community) naming
    print_info "Cleaning up volumes..."
    docker volume ls -q --filter "name=gt-20" --filter "name=gt2" --filter "name=gt-ai-os-community" | xargs -r docker volume rm 2>/dev/null || true

    print_info "Cleaning up networks..."
    docker network ls -q --filter "name=gt2" --filter "name=gt-ai-os-community" | xargs -r docker network rm 2>/dev/null || true
}

check_existing_installation() {
    # Check for existing installation BEFORE any cleanup
    if [ -d "$INSTALL_DIR" ]; then
        print_warning "Existing installation found: ${INSTALL_DIR}"

        # Check for existing containers too
        local existing_containers=$(docker ps -a --filter "name=gentwo-" --format "{{.Names}}" 2>/dev/null || true)
        if [ -n "$existing_containers" ]; then
            print_info "Running containers: $(echo $existing_containers | tr '\n' ' ')"
        fi

        if [ "$UNATTENDED" = false ]; then
            echo ""
            read -p "Remove existing installation and reinstall? (y/n): " remove_existing
            if [ "$remove_existing" != "y" ]; then
                print_error "Installation cancelled"
                exit 1
            fi
        fi

        print_info "Removing existing installation..."
        return 0  # Proceed with cleanup
    fi

    return 0  # No existing installation
}

create_installation_directory() {
    # Remove existing directory if it exists (user already confirmed in check_existing_installation)
    if [ -d "$INSTALL_DIR" ]; then
        rm -rf "$INSTALL_DIR"
    fi

    mkdir -p "$INSTALL_DIR"

    # Set ownership to sudo user if available
    if [ -n "$SUDO_USER" ]; then
        chown -R "$SUDO_USER:$SUDO_USER" "$INSTALL_DIR"
    fi

    print_success "Installation directory created: ${INSTALL_DIR}"
}

download_gt2() {
    print_info "Downloading GT 2.0..."

    # Install git if not present
    if ! command -v git &> /dev/null; then
        print_info "Installing git..."
        apt-get update -qq
        apt-get install -y -qq git
    fi

    if [ "$USE_RELEASE" = true ]; then
        print_info "Downloading latest release..."

        # Install curl if not present
        if ! command -v curl &> /dev/null; then
            apt-get install -y -qq curl
        fi

        # Get latest release download URL
        local release_url=$(curl -s "$RELEASE_URL" | grep "tarball_url" | cut -d '"' -f 4)

        if [ -z "$release_url" ]; then
            print_error "Failed to fetch latest release"
            exit 1
        fi

        # Download and extract
        curl -L "$release_url" -o "${INSTALL_DIR}/gt2.tar.gz"
        tar -xzf "${INSTALL_DIR}/gt2.tar.gz" -C "$INSTALL_DIR" --strip-components=1
        rm "${INSTALL_DIR}/gt2.tar.gz"

        print_success "Release downloaded and extracted"
    else
        print_info "Cloning from Git repository (branch: ${BRANCH})..."

        git clone --depth 1 -b "$BRANCH" "$GITHUB_REPO" "$INSTALL_DIR"

        print_success "Repository cloned (branch: ${BRANCH})"
    fi

    # Set ownership
    if [ -n "$SUDO_USER" ]; then
        chown -R "$SUDO_USER:$SUDO_USER" "$INSTALL_DIR"
    fi
}

# Try to authenticate Docker with GHCR using gh CLI (optional, for private repos)
# Returns 0 if auth succeeds, 1 if not available or fails
try_ghcr_auth() {
    # Check if gh CLI is available
    if ! command -v gh &> /dev/null; then
        return 1
    fi

    # Check if gh is authenticated
    if ! gh auth status &>/dev/null 2>&1; then
        return 1
    fi

    # Get GitHub username and token
    local gh_user=$(gh api user --jq '.login' 2>/dev/null)
    local gh_token=$(gh auth token 2>/dev/null)

    if [ -n "$gh_user" ] && [ -n "$gh_token" ]; then
        if echo "$gh_token" | docker login ghcr.io -u "$gh_user" --password-stdin &>/dev/null; then
            print_success "Authenticated with GHCR as $gh_user"
            return 0
        fi
    fi

    return 1
}

pull_docker_images() {
    print_info "Pulling Docker images (this may take several minutes)..."

    cd "$INSTALL_DIR"

    # Use DGX compose overlay
    local compose_cmd="docker compose -f docker-compose.yml -f docker-compose.dgx.yml"

    # First attempt: try pull without auth (works for public repos)
    local pull_output
    if pull_output=$($compose_cmd pull 2>&1); then
        print_success "Images pulled from registry"
        return
    fi

    # Check if it's an auth error (private repo)
    if echo "$pull_output" | grep -qi "unauthorized\|denied\|403"; then
        print_info "Registry requires authentication..."

        # Try to authenticate with gh CLI
        if try_ghcr_auth; then
            # Retry pull after auth
            if $compose_cmd pull 2>&1; then
                print_success "Images pulled after authentication"
                return
            fi
        fi
    fi

    # Fallback to local build
    print_info "Building images locally (this takes longer on first install)..."
    $compose_cmd build
    print_success "Images built successfully"
}

start_services() {
    print_info "Starting GT 2.0 services..."

    cd "$INSTALL_DIR"

    # Create required directories
    mkdir -p volumes/tenants/test/tablespaces
    mkdir -p volumes/tenants/test/files

    # Set permissions
    if [ -n "$SUDO_USER" ]; then
        chown -R "$SUDO_USER:$SUDO_USER" volumes/
    fi

    docker compose -f docker-compose.yml -f docker-compose.dgx.yml up -d

    print_success "Services started"
}

wait_for_health() {
    print_info "Waiting for services to become healthy (DGX may take 3-5 minutes)..."

    local max_wait=400
    local elapsed=0

    while [ $elapsed -lt $max_wait ]; do
        local healthy_count=0
        local total_services=5

        # Check Control Panel backend
        if curl -sf http://localhost:8001/health > /dev/null 2>&1; then
            ((healthy_count++))
        fi

        # Check Tenant backend
        if curl -sf http://localhost:8002/health > /dev/null 2>&1; then
            ((healthy_count++))
        fi

        # Check Resource Cluster
        if curl -sf http://localhost:8004/health > /dev/null 2>&1; then
            ((healthy_count++))
        fi

        # Check Control Panel frontend
        if curl -sf http://localhost:3001 > /dev/null 2>&1; then
            ((healthy_count++))
        fi

        # Check Tenant frontend
        if curl -sf http://localhost:3002 > /dev/null 2>&1; then
            ((healthy_count++))
        fi

        if [ $healthy_count -eq $total_services ]; then
            print_success "All services are healthy!"
            return 0
        fi

        echo -n "."
        sleep 5
        ((elapsed+=5))
    done

    echo ""
    print_warning "Some services may still be starting. Check with: docker compose ps"
}

create_systemd_service() {
    if [ "$UNATTENDED" = false ]; then
        read -p "Create systemd service for auto-start on boot? (y/n): " create_service
        if [ "$create_service" != "y" ]; then
            return
        fi
    else
        return
    fi

    print_info "Creating systemd service..."

    cat > /etc/systemd/system/gt2.service << EOF
[Unit]
Description=GT 2.0 Enterprise AI Platform (DGX)
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/docker compose -f docker-compose.yml -f docker-compose.dgx.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.yml -f docker-compose.dgx.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable gt2.service

    print_success "Systemd service created and enabled"
}

display_access_info() {
    echo ""
    echo -e "${GREEN}================================================================${NC}"
    echo -e "${GREEN}  GT 2.0 Installation Complete on NVIDIA DGX!${NC}"
    echo -e "${GREEN}================================================================${NC}"
    echo ""
    echo -e "${BLUE}Access URLs:${NC}"
    echo -e "  Control Panel:  ${GREEN}http://localhost:3001${NC}"
    echo -e "  Tenant App:     ${GREEN}http://localhost:3002${NC}"

    if [ "$INSTALL_OLLAMA" = true ]; then
        echo -e "  Ollama API:     ${GREEN}http://localhost:11434${NC}"
    fi

    echo ""
    echo -e "${BLUE}Default Credentials:${NC}"
    echo -e "  Username: ${GREEN}gtadmin@test.com${NC}"
    echo -e "  Password: ${GREEN}Test@123${NC}"
    echo ""
    echo -e "${BLUE}Installation Directory:${NC} ${INSTALL_DIR}"
    echo ""
    echo -e "${BLUE}DGX-Specific Notes:${NC}"
    echo "  - Platform: NVIDIA DGX with Grace ARM architecture"
    echo "  - Embeddings: Optimized for 20-core ARM CPU"
    echo "  - Memory: High-memory configuration enabled"

    if [ "$INSTALL_OLLAMA" = true ]; then
        echo "  - Ollama: Running on port 11434 for local LLM inference"
        echo ""
        echo -e "${BLUE}Ollama Commands:${NC}"
        echo "  Test Ollama:    ollama list"
        echo "  Ollama status:  systemctl status ollama"
        echo "  Pull models:    ollama pull <model-name>"
    fi

    echo ""
    echo -e "${BLUE}Useful Commands:${NC}"
    echo "  View logs:      cd ${INSTALL_DIR} && docker compose logs -f"
    echo "  Stop services:  cd ${INSTALL_DIR} && docker compose down"
    echo "  Start services: cd ${INSTALL_DIR} && docker compose up -d"
    echo "  View status:    cd ${INSTALL_DIR} && docker compose ps"
    echo "  GPU status:     nvidia-smi"
    echo ""
    if [ -n "$SUDO_USER" ]; then
        echo -e "${YELLOW}Note: You were added to the docker group.${NC}"
        echo -e "${YELLOW}Logout and login again to use docker without sudo.${NC}"
        echo ""
    fi
    echo -e "${GREEN}Enjoy GT 2.0 on NVIDIA DGX!${NC}"
    echo ""
}

cleanup_on_error() {
    print_error "Installation failed!"

    if [ -d "$INSTALL_DIR" ]; then
        print_info "Cleaning up..."
        cd "$INSTALL_DIR"
        docker compose down -v 2>/dev/null || true
        cd ..
        rm -rf "$INSTALL_DIR"
    fi

    exit 1
}

setup_demo_data() {
    print_info "Setting up model configurations..."

    cd "$INSTALL_DIR"

    if [ -f "scripts/demo/setup-demo-data.sh" ]; then
        chmod +x scripts/demo/setup-demo-data.sh
        ./scripts/demo/setup-demo-data.sh
        print_success "Model configurations complete"
    else
        print_warning "Model config script not found, skipping"
    fi
}

generate_security_tokens() {
    print_info "Generating security tokens..."

    cd "$INSTALL_DIR"

    # Use centralized secrets library if available
    if [ -f "scripts/lib/secrets.sh" ]; then
        source scripts/lib/secrets.sh
        generate_all_secrets ".env"
        print_success "Generated all required secrets"
    else
        # Fallback to inline generation for standalone installer
        local env_file=".env"

        # Create .env if it doesn't exist
        if [ ! -f "$env_file" ]; then
            touch "$env_file"
        fi

        # Generate SERVICE_AUTH_TOKEN if not already set
        if ! grep -q "^SERVICE_AUTH_TOKEN=" "$env_file" 2>/dev/null; then
            local service_token=$(openssl rand -hex 32)
            echo "SERVICE_AUTH_TOKEN=${service_token}" >> "$env_file"
            print_success "Generated SERVICE_AUTH_TOKEN"
        else
            print_info "SERVICE_AUTH_TOKEN already configured"
        fi

        # Generate JWT_SECRET if not already set
        if ! grep -q "^JWT_SECRET=" "$env_file" 2>/dev/null; then
            local jwt_secret=$(openssl rand -hex 32)
            echo "JWT_SECRET=${jwt_secret}" >> "$env_file"
            print_success "Generated JWT_SECRET"
        fi

        # Generate MASTER_ENCRYPTION_KEY if not already set
        if ! grep -q "^MASTER_ENCRYPTION_KEY=" "$env_file" 2>/dev/null; then
            if command -v python3 &> /dev/null && python3 -c "from cryptography.fernet import Fernet" 2>/dev/null; then
                local encryption_key=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
            else
                local encryption_key=$(openssl rand -base64 32)
            fi
            echo "MASTER_ENCRYPTION_KEY=${encryption_key}" >> "$env_file"
            print_success "Generated MASTER_ENCRYPTION_KEY"
        fi

        # Generate API_KEY_ENCRYPTION_KEY if not already set
        if ! grep -q "^API_KEY_ENCRYPTION_KEY=" "$env_file" 2>/dev/null; then
            if command -v python3 &> /dev/null && python3 -c "from cryptography.fernet import Fernet" 2>/dev/null; then
                local encryption_key=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
            else
                local encryption_key=$(openssl rand -base64 32)
            fi
            echo "API_KEY_ENCRYPTION_KEY=${encryption_key}" >> "$env_file"
            print_success "Generated API_KEY_ENCRYPTION_KEY"
        fi

        # Generate database passwords if not already set
        if ! grep -q "^ADMIN_POSTGRES_PASSWORD=" "$env_file" 2>/dev/null; then
            local admin_pw=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32)
            echo "ADMIN_POSTGRES_PASSWORD=${admin_pw}" >> "$env_file"
            print_success "Generated ADMIN_POSTGRES_PASSWORD"
        fi

        if ! grep -q "^TENANT_POSTGRES_PASSWORD=" "$env_file" 2>/dev/null; then
            local tenant_pw=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32)
            echo "TENANT_POSTGRES_PASSWORD=${tenant_pw}" >> "$env_file"
            print_success "Generated TENANT_POSTGRES_PASSWORD"
        fi
    fi

    # Set ownership if sudo user is available
    if [ -n "$SUDO_USER" ]; then
        chown "$SUDO_USER:$SUDO_USER" ".env"
    fi
}

run_migrations() {
    print_info "Running database migrations..."

    cd "$INSTALL_DIR"

    # Source migration functions if available
    if [ -f "scripts/lib/migrations.sh" ] && [ -f "scripts/lib/common.sh" ]; then
        source scripts/lib/common.sh
        source scripts/lib/migrations.sh

        if run_all_migrations; then
            print_success "Database migrations completed"
        else
            print_warning "Some migrations may have failed - check logs"
        fi
    else
        print_warning "Migration scripts not found, skipping migrations"
    fi
}

# Main installation flow
main() {
    trap cleanup_on_error ERR

    parse_args "$@"

    print_header

    # Detect if running from within an already-cloned repo
    detect_existing_repo

    # Pre-flight checks
    check_root
    check_dgx_system
    check_architecture
    check_nvidia_gpu
    check_nvidia_container_runtime
    check_ram
    check_disk_space
    check_ollama

    # Check for existing installation FIRST (prompts user before any cleanup)
    # Skip if we're running from within the repo we'd be checking
    if [ "$RUNNING_FROM_REPO" = false ]; then
        check_existing_installation
    fi

    # Now safe to cleanup (user has confirmed or no existing installation)
    cleanup_existing_containers

    # Installation - skip clone if already in repo
    if [ "$RUNNING_FROM_REPO" = false ]; then
        create_installation_directory
        download_gt2
    fi

    generate_security_tokens
    pull_docker_images
    start_services
    wait_for_health

    # Post-installation
    setup_demo_data
    run_migrations  # Apply any migrations not in init scripts (idempotent)
    create_systemd_service
    display_access_info
}

# Run installer
main "$@"
