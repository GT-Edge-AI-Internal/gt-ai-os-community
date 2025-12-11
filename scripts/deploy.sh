#!/bin/bash
# GT 2.0 Unified Deployment Script
# Platform-agnostic deployment and update system
# Supports: ARM64 (Mac M2+), x86_64 (Ubuntu), DGX (Grace ARM + Blackwell GPU)

set -e

# Script directory for sourcing libraries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source library functions
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/lib/platform.sh"
source "$SCRIPT_DIR/lib/docker.sh"
source "$SCRIPT_DIR/lib/migrations.sh"
source "$SCRIPT_DIR/lib/health.sh"
source "$SCRIPT_DIR/lib/secrets.sh"

# Default options
DRY_RUN=false
DEV_MODE=false
SKIP_MIGRATIONS=false
SKIP_PULL=false
SKIP_CLEANUP=false
FORCE=false
PLATFORM=""

# Display help
show_help() {
    cat <<EOF
GT 2.0 Unified Deployment Script

Usage: $0 [OPTIONS]

Options:
  --platform PLATFORM   Force specific platform (arm64, x86, dgx)
  --dev                 Enable development mode (rebuild locally with hot reload)
  --dry-run             Show commands without executing
  --skip-migrations     Skip database migration checks
  --skip-pull           Skip Docker image pull
  --skip-cleanup        Skip Docker cleanup (prune volumes/images/cache)
  --force               Skip confirmation prompts
  --help                Show this help message

Modes:
  Production (default)  Pulls pre-built images from GHCR, restarts services
  Development (--dev)   Rebuilds containers locally, enables hot reload

Examples:
  # Auto-detect platform and deploy (uses GHCR images)
  $0

  # Deploy with development mode (rebuilds locally)
  $0 --dev

  # Deploy on specific platform
  $0 --platform x86

  # Dry run to see what would happen
  $0 --dry-run

  # Force update without confirmation
  $0 --force

Platforms:
  arm64    Apple Silicon (M2+)
  x86      x86_64 Linux (Ubuntu)
  dgx      NVIDIA DGX (Grace ARM + Blackwell GPU)

Environment Variables:
  PLATFORM         Override platform detection
  DEV_MODE         Enable development mode (true/false)
  DRY_RUN          Dry run mode (true/false)
  IMAGE_TAG        Docker image tag to use (default: latest)
EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --platform)
                PLATFORM="$2"
                shift 2
                ;;
            --dev)
                DEV_MODE=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --skip-migrations)
                SKIP_MIGRATIONS=true
                shift
                ;;
            --skip-pull)
                SKIP_PULL=true
                shift
                ;;
            --skip-cleanup)
                SKIP_CLEANUP=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Main deployment function
main() {
    parse_args "$@"

    log_header "GT 2.0 Unified Deployment"

    # Check root directory
    check_root_directory

    # Detect platform if not specified
    if [ -z "$PLATFORM" ]; then
        PLATFORM=$(detect_platform)
    fi

    log_info "Platform: $PLATFORM"

    # Create bind mount directories (always safe, required for fresh installs)
    mkdir -p volumes/tenants/test/tablespaces
    mkdir -p volumes/tenants/test/files

    if [ "$DEV_MODE" = "true" ]; then
        log_info "Mode: Development (hot reload enabled)"
    else
        log_info "Mode: Production"
    fi

    # Show platform info
    get_platform_info "$PLATFORM"
    echo ""

    # Check platform prerequisites
    if ! check_platform_prerequisites "$PLATFORM"; then
        exit 1
    fi

    # Generate any missing secrets (for fresh installs)
    log_info "Checking and generating secrets..."
    generate_all_secrets ".env"
    echo ""

    # Check if deployment is running
    if check_deployment_running; then
        log_info "Current deployment status:"
        show_service_status
        echo ""

        # Ask for confirmation unless forced
        if [ "$FORCE" != "true" ]; then
            if ! confirm "Continue with update and restart?"; then
                log_info "Update cancelled"
                exit 0
            fi
        fi
    else
        log_info "No running deployment found - starting fresh deployment"
    fi

    # Git status checks
    if [ -d ".git" ]; then
        log_info "Git repository information:"
        echo "Current branch: $(git branch --show-current)"
        echo "Current commit: $(git rev-parse --short HEAD)"

        # Check for uncommitted changes
        if [ -n "$(git status --porcelain)" ]; then
            log_warning "Uncommitted changes detected"
            if [ "$FORCE" != "true" ]; then
                if ! confirm "Continue anyway?"; then
                    exit 0
                fi
            fi
        fi

        # Offer to pull latest
        if [ "$FORCE" != "true" ]; then
            if confirm "Pull latest from git?"; then
                log_info "Pulling latest changes..."
                git pull
            fi
        fi
    fi
    echo ""

    # Pull Docker images
    if [ "$SKIP_PULL" != "true" ]; then
        pull_images
        echo ""
    fi

    # Restart services
    if [ "$DEV_MODE" = "true" ]; then
        log_header "Rebuilding and Restarting Services (Dev Mode)"
    else
        log_header "Restarting Services with Pulled Images"
    fi

    # Remove all existing gentwo-* containers to prevent name conflicts
    # This handles cases where project name changed (gt2 -> gt-20 or vice versa)
    cleanup_conflicting_containers

    # Database services must start first (migrations depend on them)
    DB_SERVICES=(
        "postgres"
        "tenant-postgres-primary"
    )

    # Application services (uses pulled images in prod, rebuilds in dev)
    APP_SERVICES=(
        "control-panel-backend"
        "control-panel-frontend"
        "tenant-backend"
        "tenant-app"
        "resource-cluster"
    )

    # Other infrastructure services
    INFRA_SERVICES=(
        "vllm-embeddings"
    )

    # Start database services first and wait for them to be healthy
    log_info "Starting database services..."
    for service in "${DB_SERVICES[@]}"; do
        restart_service "$service"
    done

    # Wait for databases to be healthy before running migrations
    log_info "Waiting for databases to be healthy..."
    wait_for_stability 15

    # Run database migrations (now that databases are confirmed running)
    if [ "$SKIP_MIGRATIONS" != "true" ]; then
        if ! run_all_migrations; then
            log_error "Migrations failed - aborting deployment"
            exit 1
        fi
        echo ""
    fi

    # Restart/rebuild application services based on mode
    for service in "${APP_SERVICES[@]}"; do
        restart_app_service "$service"
    done

    # Restart other infrastructure services
    for service in "${INFRA_SERVICES[@]}"; do
        restart_service "$service"
    done

    # Wait for stability
    wait_for_stability 10

    # Health check
    if ! check_all_services_healthy; then
        log_error "Health check failed"
        exit 1
    fi

    # Clean up unused Docker resources
    if [ "$SKIP_CLEANUP" != "true" ]; then
        cleanup_docker_resources
    fi

    # Show final status
    show_access_points
}

# Run main function
main "$@"
