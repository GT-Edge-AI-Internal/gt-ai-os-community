#!/bin/bash
# GT 2.0 Ubuntu x86_64 Installer
# Installation script for Ubuntu 22.04+ on x86_64 architecture
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
MIN_UBUNTU_VERSION="22.04"
MIN_RAM_GB=16
MIN_DISK_GB=20
GITHUB_REPO="https://github.com/GT-Edge-AI-Internal/gt-ai-os-community.git"
RELEASE_URL="https://api.github.com/repos/GT-Edge-AI-Internal/gt-ai-os-community/releases/latest"

# Flags
UNATTENDED=false
SKIP_DOCKER_INSTALL=false
USE_RELEASE=false
BRANCH="main"
RUNNING_FROM_REPO=false

# Compose file configuration (set by setup_compose_environment)
COMPOSE_FILES=""

# Functions
print_header() {
    echo ""
    echo -e "${BLUE}================================================================${NC}"
    echo -e "${BLUE}  GT AI OS Community Edition${NC}"
    echo -e "${BLUE}  Ubuntu x86_64 Installer v${INSTALLER_VERSION}${NC}"
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

Install GT 2.0 Enterprise AI Platform on Ubuntu x86_64

OPTIONS:
    -h, --help              Show this help message
    -v, --version           Show installer version
    -u, --unattended        Run in non-interactive mode
    -d, --dir PATH          Installation directory (default: ${INSTALL_DIR})
    -b, --branch BRANCH     Git branch to clone (default: main)
    --skip-docker-install   Skip Docker installation (assumes Docker is installed)
    --use-release           Download latest release instead of cloning git repo

REQUIREMENTS:
    - Ubuntu 22.04 or higher
    - x86_64 architecture
    - 16GB+ RAM
    - 20GB+ free disk space
    - sudo access

EXAMPLES:
    # Interactive installation
    sudo $0

    # Unattended installation
    sudo $0 --unattended

    # Custom installation directory
    sudo $0 --dir /home/gt2/platform

    # Use pre-built release
    sudo $0 --use-release

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
                echo "GT 2.0 Ubuntu Installer v${INSTALLER_VERSION}"
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
            --skip-docker-install)
                SKIP_DOCKER_INSTALL=true
                shift
                ;;
            --use-release)
                USE_RELEASE=true
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

check_ubuntu_version() {
    print_info "Checking Ubuntu version..."

    if [ ! -f /etc/os-release ]; then
        print_error "/etc/os-release not found - is this Ubuntu?"
        exit 1
    fi

    source /etc/os-release

    if [ "$ID" != "ubuntu" ]; then
        print_error "This installer is for Ubuntu only (detected: $ID)"
        exit 1
    fi

    local version=$(echo "$VERSION_ID" | cut -d '.' -f 1,2)
    local min_version=$(echo "$MIN_UBUNTU_VERSION" | cut -d '.' -f 1,2)

    if [ "$(printf '%s\n' "$min_version" "$version" | sort -V | head -n1)" != "$min_version" ]; then
        print_error "Ubuntu ${MIN_UBUNTU_VERSION} or higher required (found: ${VERSION_ID})"
        exit 1
    fi

    print_success "Ubuntu version: ${VERSION_ID}"
}

check_architecture() {
    print_info "Checking CPU architecture..."

    local arch=$(uname -m)

    if [ "$arch" != "x86_64" ]; then
        print_error "This installer requires x86_64 architecture (found: $arch)"
        print_info "For ARM systems, please use the ARM installer"
        exit 1
    fi

    print_success "Architecture: x86_64"
}

check_ram() {
    print_info "Checking available RAM..."

    local ram_kb=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    local ram_gb=$((ram_kb / 1024 / 1024))

    if [ "$ram_gb" -lt "$MIN_RAM_GB" ]; then
        print_error "Minimum ${MIN_RAM_GB}GB RAM required (found: ${ram_gb}GB)"
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

# Detect NVIDIA GPU and Container Toolkit availability
detect_nvidia_gpu() {
    # Check for nvidia-smi command (indicates NVIDIA drivers installed)
    if ! command -v nvidia-smi &> /dev/null; then
        return 1
    fi

    # Verify GPU is accessible
    if ! nvidia-smi &> /dev/null; then
        return 1
    fi

    # Check NVIDIA Container Toolkit is configured in Docker
    if ! docker info 2>/dev/null | grep -qi "nvidia"; then
        print_warning "NVIDIA GPU detected but Container Toolkit not installed"
        print_info "Install with: sudo apt install nvidia-container-toolkit && sudo systemctl restart docker"
        return 1
    fi

    return 0
}

# Setup compose environment with appropriate overlays based on GPU detection
# Uses COMPOSE_FILE env var instead of command-line flags to avoid word-splitting issues
setup_compose_environment() {
    COMPOSE_FILES="docker-compose.yml:docker-compose.x86.yml"

    if detect_nvidia_gpu; then
        print_success "NVIDIA GPU detected - enabling GPU acceleration for embeddings"
        COMPOSE_FILES="$COMPOSE_FILES:docker-compose.x86-gpu.yml"
    else
        print_info "No NVIDIA GPU detected - using CPU mode for embeddings"
    fi

    export COMPOSE_FILE="$COMPOSE_FILES"
    print_info "Using compose files: $COMPOSE_FILES"
}

install_docker() {
    if [ "$SKIP_DOCKER_INSTALL" = true ]; then
        print_info "Skipping Docker installation (--skip-docker-install)"
        return
    fi

    print_info "Checking for Docker..."

    if command -v docker &> /dev/null; then
        print_success "Docker already installed: $(docker --version)"

        # Check if Docker daemon is running
        if ! docker info &> /dev/null; then
            print_info "Starting Docker daemon..."
            systemctl start docker
            systemctl enable docker
            print_success "Docker daemon started"
        else
            print_success "Docker daemon is running"
        fi

        return
    fi

    print_info "Installing Docker..."

    # Update package index
    apt-get update -qq

    # Install prerequisites
    apt-get install -y -qq \
        ca-certificates \
        curl \
        gnupg \
        lsb-release

    # Add Docker's official GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    # Set up Docker repository
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
        $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

    # Install Docker Engine
    apt-get update -qq
    apt-get install -y -qq \
        docker-ce \
        docker-ce-cli \
        containerd.io \
        docker-buildx-plugin \
        docker-compose-plugin

    # Add current user to docker group (if not root)
    if [ -n "$SUDO_USER" ]; then
        usermod -aG docker "$SUDO_USER"
        print_info "Added $SUDO_USER to docker group (logout/login required)"
    fi

    # Start and enable Docker
    systemctl start docker
    systemctl enable docker

    print_success "Docker installed and started"
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

    # COMPOSE_FILE env var is set by setup_compose_environment()
    # Docker compose will automatically use it

    # First attempt: try pull without auth (works for public repos)
    local pull_output
    local pull_exit_code
    pull_output=$(docker compose pull 2>&1) && pull_exit_code=0 || pull_exit_code=$?

    if [ $pull_exit_code -eq 0 ]; then
        print_success "Images pulled from registry"
        return
    fi

    # Log the pull error for debugging
    print_warning "Pull failed (exit code: $pull_exit_code)"
    echo "$pull_output" | head -20

    # Check if it's an auth error (private repo)
    if echo "$pull_output" | grep -qi "unauthorized\|denied\|403"; then
        print_info "Registry requires authentication..."

        # Try to authenticate with gh CLI
        if try_ghcr_auth; then
            # Retry pull after auth
            if docker compose pull 2>&1; then
                print_success "Images pulled after authentication"
                return
            fi
        fi
    fi

    # Fallback to local build
    print_info "Building images locally (this takes longer on first install)..."
    docker compose build
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

    # COMPOSE_FILE env var is set by setup_compose_environment()
    docker compose up -d

    print_success "Services started"
}

wait_for_health() {
    print_info "Waiting for services to become healthy (this may take 2-3 minutes)..."

    local max_wait=300
    local elapsed=0

    while [ $elapsed -lt $max_wait ]; do
        local healthy_count=0
        local total_services=5

        # Check Control Panel backend
        if curl -sf http://localhost:8001/health > /dev/null 2>&1; then
            healthy_count=$((healthy_count + 1))
        fi

        # Check Tenant backend
        if curl -sf http://localhost:8002/health > /dev/null 2>&1; then
            healthy_count=$((healthy_count + 1))
        fi

        # Check Resource Cluster
        if curl -sf http://localhost:8004/health > /dev/null 2>&1; then
            healthy_count=$((healthy_count + 1))
        fi

        # Check Control Panel frontend
        if curl -sf http://localhost:3001 > /dev/null 2>&1; then
            healthy_count=$((healthy_count + 1))
        fi

        # Check Tenant frontend
        if curl -sf http://localhost:3002 > /dev/null 2>&1; then
            healthy_count=$((healthy_count + 1))
        fi

        if [ $healthy_count -eq $total_services ]; then
            print_success "All services are healthy!"
            return 0
        fi

        echo -n "."
        sleep 5
        elapsed=$((elapsed + 5))
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

    # Convert COMPOSE_FILES (colon-separated) to -f flags for systemd
    # e.g., "docker-compose.yml:docker-compose.x86.yml" -> "-f docker-compose.yml -f docker-compose.x86.yml"
    local compose_flags=$(echo "$COMPOSE_FILES" | sed 's/:/ -f /g' | sed 's/^/-f /')

    cat > /etc/systemd/system/gt2.service << EOF
[Unit]
Description=GT 2.0 Enterprise AI Platform
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/docker compose ${compose_flags} up -d
ExecStop=/usr/bin/docker compose ${compose_flags} down
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
    echo -e "${GREEN}  GT 2.0 Installation Complete!${NC}"
    echo -e "${GREEN}================================================================${NC}"
    echo ""
    echo -e "${BLUE}Access URLs:${NC}"
    echo -e "  Control Panel:  ${GREEN}http://localhost:3001${NC}"
    echo -e "  Tenant App:     ${GREEN}http://localhost:3002${NC}"
    echo ""
    echo -e "${BLUE}Default Credentials:${NC}"
    echo -e "  Username: ${GREEN}gtadmin@test.com${NC}"
    echo -e "  Password: ${GREEN}Test@123${NC}"
    echo ""
    echo -e "${BLUE}Installation Directory:${NC} ${INSTALL_DIR}"
    echo ""
    echo -e "${BLUE}Useful Commands:${NC}"
    echo "  View logs:      cd ${INSTALL_DIR} && docker compose logs -f"
    echo "  Stop services:  cd ${INSTALL_DIR} && docker compose down"
    echo "  Start services: cd ${INSTALL_DIR} && docker compose up -d"
    echo "  View status:    cd ${INSTALL_DIR} && docker compose ps"
    echo ""
    if [ -n "$SUDO_USER" ]; then
        echo -e "${YELLOW}Note: You were added to the docker group.${NC}"
        echo -e "${YELLOW}Logout and login again to use docker without sudo.${NC}"
        echo ""
    fi
    echo -e "${GREEN}Enjoy GT 2.0!${NC}"
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

        # Sync TENANT_USER_PASSWORD with TENANT_POSTGRES_PASSWORD (required for docker-compose)
        if ! grep -q "^TENANT_USER_PASSWORD=" "$env_file" 2>/dev/null; then
            local tenant_pass=$(grep "^TENANT_POSTGRES_PASSWORD=" "$env_file" | cut -d'=' -f2)
            echo "TENANT_USER_PASSWORD=${tenant_pass}" >> "$env_file"
            print_success "Generated TENANT_USER_PASSWORD (synced with TENANT_POSTGRES_PASSWORD)"
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
    check_ubuntu_version
    check_architecture
    check_ram
    check_disk_space

    # Docker installation
    install_docker

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
    setup_compose_environment
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
