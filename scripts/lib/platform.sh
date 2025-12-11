#!/bin/bash
# GT 2.0 Platform Detection and Compose File Selection
# Handles ARM64, x86_64, and DGX platform differences

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

    case "$platform" in
        arm64)
            echo "docker-compose.yml -f docker-compose.arm64.yml"
            ;;
        x86)
            echo "docker-compose.yml -f docker-compose.x86.yml"
            ;;
        dgx)
            echo "docker-compose.yml -f docker-compose.dgx.yml"
            ;;
        *)
            log_error "Unknown platform: $platform"
            exit 1
            ;;
    esac

    # Add dev overlay if requested
    if [ "$dev_mode" = "true" ]; then
        echo "-f docker-compose.dev.yml"
    fi
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
            echo "Compose: docker-compose.yml + docker-compose.x86.yml"
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
