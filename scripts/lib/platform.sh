#!/bin/bash
# GT 2.0 Platform Detection and Compose File Selection
# Handles ARM64, x86_64, and DGX platform differences

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
        return 1
    fi

    return 0
}

# Detect platform architecture
detect_platform() {
    local arch=$(uname -m)
    local os=$(uname -s)

    # Check for DGX specific environment
    if [ -f "/etc/dgx-release" ] || [ -n "${DGX_PLATFORM}" ]; then
        echo "dgx"
        return 0
    fi

    # Detect architecture
    case "$arch" in
        aarch64|arm64)
            echo "arm64"
            ;;
        x86_64|amd64)
            echo "x86"
            ;;
        *)
            log_error "Unsupported architecture: $arch"
            exit 1
            ;;
    esac
}

# Get compose file for platform
get_compose_file() {
    local platform="${1:-$(detect_platform)}"
    local dev_mode="${2:-false}"
    local files=""

    case "$platform" in
        arm64)
            files="docker-compose.yml -f docker-compose.arm64.yml"
            ;;
        x86)
            files="docker-compose.yml -f docker-compose.x86.yml"
            # Add GPU overlay if NVIDIA GPU detected
            if detect_nvidia_gpu; then
                files="$files -f docker-compose.x86-gpu.yml"
            fi
            ;;
        dgx)
            files="docker-compose.yml -f docker-compose.dgx.yml"
            ;;
        *)
            log_error "Unknown platform: $platform"
            exit 1
            ;;
    esac

    # Add dev overlay if requested
    if [ "$dev_mode" = "true" ]; then
        files="$files -f docker-compose.dev.yml"
    fi

    echo "$files"
}

# Get platform-specific settings
get_platform_info() {
    local platform="${1:-$(detect_platform)}"

    case "$platform" in
        arm64)
            echo "Platform: Apple Silicon (ARM64)"
            echo "Compose: docker-compose.yml + docker-compose.arm64.yml"
            echo "PgBouncer: pgbouncer/pgbouncer:latest"
            ;;
        x86)
            echo "Platform: x86_64 Linux"
            if detect_nvidia_gpu; then
                echo "Compose: docker-compose.yml + docker-compose.x86.yml + docker-compose.x86-gpu.yml"
                echo "GPU: NVIDIA (accelerated embeddings)"
            else
                echo "Compose: docker-compose.yml + docker-compose.x86.yml"
                echo "GPU: None (CPU mode)"
            fi
            echo "PgBouncer: pgbouncer/pgbouncer:latest"
            ;;
        dgx)
            echo "Platform: NVIDIA DGX (ARM64 Grace + Blackwell GPU)"
            echo "Compose: docker-compose.yml + docker-compose.dgx.yml"
            echo "PgBouncer: bitnamilegacy/pgbouncer:latest"
            ;;
    esac
}

# Check platform-specific prerequisites
check_platform_prerequisites() {
    local platform="${1:-$(detect_platform)}"

    case "$platform" in
        x86|dgx)
            # Check if user is in docker group
            if ! groups | grep -q '\bdocker\b'; then
                log_error "User $USER is not in the docker group"
                log_warning "Docker group membership is required on Linux"
                echo ""
                echo "Please run the following command:"
                echo -e "${BLUE}  sudo usermod -aG docker $USER${NC}"
                echo ""
                echo "Then either:"
                echo "  1. Log out and log back in (recommended)"
                echo "  2. Run: newgrp docker (temporary for this session)"
                return 1
            fi
            log_success "Docker group membership confirmed"
            ;;
        arm64)
            # macOS - no docker group check needed
            log_success "Platform prerequisites OK (macOS)"
            ;;
    esac
    return 0
}
