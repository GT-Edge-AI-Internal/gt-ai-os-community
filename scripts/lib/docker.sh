#!/bin/bash
# GT 2.0 Docker Compose Wrapper Functions
# Unified interface for platform-specific compose operations

# ==============================================
# VOLUME MIGRATION (DEPRECATED - Removed Dec 2025)
# This function has been removed because:
# 1. It could overwrite good data with stale data from old volumes
# 2. Docker Compose handles volumes naturally - let it manage them
# 3. Manual migration is safer for deployments with custom volume names
#
# For manual migration (if needed):
#   1. docker compose down
#   2. docker run --rm -v old_vol:/src -v new_vol:/dst alpine cp -a /src/. /dst/
#   3. docker compose up -d
# ==============================================

# migrate_volumes_if_needed() - REMOVED
# Function body removed to prevent accidental data loss

# ==============================================
# PROJECT MIGRATION (DEPRECATED - Removed Dec 2025)
# This function has been removed because:
# 1. It aggressively stops/removes all containers
# 2. Different project names don't cause issues if volumes persist
# 3. Docker Compose derives project name from directory naturally
#
# Containers from different project names can coexist. If you need
# to clean up old containers manually:
#   docker ps -a --format '{{.Names}}' | grep gentwo- | xargs docker rm -f
# ==============================================

# migrate_project_if_needed() - REMOVED
# Function body removed to prevent accidental container/data loss

# ==============================================
# CONTAINER CLEANUP
# Removes existing containers to prevent name conflicts during restart
# ==============================================

remove_existing_container() {
    local service="$1"

    # Get container name from compose config for this service
    local container_name=$(dc config --format json 2>/dev/null | jq -r ".services[\"$service\"].container_name // empty" 2>/dev/null)

    if [ -n "$container_name" ]; then
        # Check if container exists (running or stopped)
        if docker ps -a --format '{{.Names}}' | grep -q "^${container_name}$"; then
            log_info "Removing existing container $container_name..."
            docker rm -f "$container_name" 2>/dev/null || true
        fi
    fi
}

# Remove ALL gentwo-* containers to handle project name conflicts
# This is needed when switching between project names (gt2 vs gt-20)
cleanup_conflicting_containers() {
    # Skip in dry-run mode
    if [ "$DRY_RUN" = "true" ]; then
        echo "[DRY RUN] Would remove all gentwo-* containers"
        return 0
    fi

    log_info "Checking for conflicting containers..."

    local containers=$(docker ps -a --format '{{.Names}}' | grep "^gentwo-" || true)

    if [ -n "$containers" ]; then
        log_info "Removing existing gentwo-* containers to prevent conflicts..."
        for container in $containers; do
            docker rm -f "$container" 2>/dev/null || true
        done
        log_success "Removed conflicting containers"
    fi
}

# ==============================================
# DOCKER COMPOSE WRAPPER
# ==============================================

# Execute docker compose with platform-specific files
# No explicit project name - Docker Compose derives it from directory name
# This ensures existing volumes (gt-20_*, gt2_*, etc.) continue to be used
dc() {
    local platform="${PLATFORM:-$(detect_platform)}"
    local compose_files=$(get_compose_file "$platform" "$DEV_MODE")

    if [ "$DRY_RUN" = "true" ]; then
        echo "[DRY RUN] docker compose -f $compose_files $*"
        return 0
    fi

    # Pipe 'n' to auto-answer "no" to volume recreation prompts
    # This handles cases where bind mount paths don't match existing volumes
    yes n 2>/dev/null | docker compose -f $compose_files "$@"
}

# Detect IMAGE_TAG from current git branch if not already set
detect_image_tag() {
    # If IMAGE_TAG is already set, use it
    if [ -n "$IMAGE_TAG" ]; then
        log_info "Using IMAGE_TAG=$IMAGE_TAG (from environment)"
        return 0
    fi

    # Detect current git branch
    local branch=$(git branch --show-current 2>/dev/null)

    case "$branch" in
        main|master)
            IMAGE_TAG="latest"
            ;;
        dev|develop)
            IMAGE_TAG="dev"
            ;;
        *)
            # Feature branches: sanitize branch name for Docker tag
            # Docker tags only allow [a-zA-Z0-9_.-], so replace / with -
            IMAGE_TAG="${branch//\//-}"
            ;;
    esac

    export IMAGE_TAG
    log_info "Auto-detected IMAGE_TAG=$IMAGE_TAG (branch: $branch)"
}

# Try to authenticate Docker with GHCR using gh CLI (optional, for private repos)
# Returns 0 if auth succeeds, 1 if not available or fails
try_ghcr_auth() {
    # Skip in dry-run mode
    if [ "$DRY_RUN" = "true" ]; then
        echo "[DRY RUN] Try GHCR authentication"
        return 0
    fi

    # Check if gh CLI is available
    if ! command -v gh &>/dev/null; then
        log_info "gh CLI not installed - skipping GHCR auth"
        return 1
    fi

    # Check if gh is authenticated
    if ! gh auth status &>/dev/null 2>&1; then
        log_info "gh CLI not authenticated - skipping GHCR auth"
        return 1
    fi

    # Get GitHub username
    local gh_user=$(gh api user --jq '.login' 2>/dev/null)
    if [ -z "$gh_user" ]; then
        return 1
    fi

    # Get token and authenticate Docker
    local gh_token=$(gh auth token 2>/dev/null)
    if [ -z "$gh_token" ]; then
        return 1
    fi

    if echo "$gh_token" | docker login ghcr.io -u "$gh_user" --password-stdin &>/dev/null; then
        log_success "Authenticated with GHCR as $gh_user"
        return 0
    fi

    return 1
}

# Pull images with simplified auth flow
# 1. Try pull without auth (works for public repos)
# 2. If auth error, try gh CLI auth and retry
# 3. If still fails, fall back to local build
pull_images() {
    # Auto-detect image tag from git branch
    detect_image_tag

    log_info "Pulling Docker images (tag: $IMAGE_TAG)..."

    # Skip in dry-run mode
    if [ "$DRY_RUN" = "true" ]; then
        echo "[DRY RUN] docker compose pull"
        return 0
    fi

    # First attempt: try pull without auth (works for public repos)
    local pull_output
    pull_output=$(dc pull 2>&1) && {
        log_success "Successfully pulled images"
        return 0
    }

    # Check if it's an auth error (private repo)
    if echo "$pull_output" | grep -qi "unauthorized\|denied\|authentication required\|403"; then
        log_info "Registry requires authentication, attempting GHCR login..."

        # Try to authenticate with gh CLI
        if try_ghcr_auth; then
            # Retry pull after auth
            if dc pull 2>&1; then
                log_success "Successfully pulled images after authentication"
                return 0
            fi
        fi

        log_warning "Could not pull from registry - will build images locally"
        log_info "For faster deploys, install gh CLI and run: gh auth login"
        return 1
    fi

    # Check for rate limiting
    if echo "$pull_output" | grep -qi "rate limit\|too many requests"; then
        log_warning "Rate limited - continuing with existing images"
        return 0
    fi

    # Other error - log and continue
    log_warning "Pull failed: ${pull_output:0:200}"
    log_info "Continuing with existing or locally built images"
    return 1
}

# Restart application service (uses pulled images by default, --build in dev mode)
restart_app_service() {
    local service="$1"
    local build_flag=""

    # Only use --build in dev mode (to apply local code changes)
    # In production mode, use pre-pulled GHCR images
    if [ "$DEV_MODE" = "true" ]; then
        build_flag="--build"
        log_info "Rebuilding and restarting $service (dev mode)..."
    else
        log_info "Restarting $service with pulled image..."
    fi

    # In dry-run mode, just show the command that would be executed
    if [ "$DRY_RUN" = "true" ]; then
        dc up -d $build_flag "$service"
        return 0
    fi

    # Remove existing container to prevent name conflicts
    remove_existing_container "$service"

    # Start/restart service regardless of current state
    # dc up -d handles both starting new and restarting existing containers
    # Use --force-recreate to ensure container uses new image
    dc up -d --force-recreate $build_flag "$service" || {
        log_warning "Service $service may not be defined in compose files, skipping"
        return 0
    }
    sleep 2
    return 0
}

# Legacy alias for backward compatibility
rebuild_service() {
    restart_app_service "$@"
}

# Restart service without rebuild
restart_service() {
    local service="$1"

    log_info "Restarting $service..."

    # In dry-run mode, just show the command
    if [ "$DRY_RUN" = "true" ]; then
        dc up -d "$service"
        return 0
    fi

    # Remove existing container to prevent name conflicts
    remove_existing_container "$service"

    # Use dc up -d which handles both starting and restarting
    # Use --force-recreate to ensure container is recreated cleanly
    dc up -d --force-recreate "$service" || {
        log_warning "Service $service may not be defined in compose files, skipping"
        return 0
    }
    sleep 2
    return 0
}

# Check service health
check_service_health() {
    log_info "Checking service health..."

    local unhealthy=$(dc ps --format json | jq -r 'select(.Health == "unhealthy") | .Service' 2>/dev/null || true)

    if [ -n "$unhealthy" ]; then
        log_error "Unhealthy services detected: $unhealthy"
        echo "Check logs with: docker compose logs $unhealthy"
        return 1
    fi

    log_success "All services healthy"
    return 0
}

# Display service status
show_service_status() {
    log_info "Service Status:"
    dc ps --format "table {{.Service}}\t{{.Status}}"
}

# Clean up unused Docker resources after deployment
cleanup_docker_resources() {
    log_info "Cleaning up unused Docker resources..."

    if [ "$DRY_RUN" = "true" ]; then
        echo "[DRY RUN] docker image prune -f"
        echo "[DRY RUN] docker builder prune -f"
        return 0
    fi

    # NOTE: Volume prune removed - too risky, can delete important data
    # if containers were stopped earlier in the deployment process

    # Remove dangling images (untagged, not used by any container)
    local images_removed=$(docker image prune -f 2>/dev/null | grep "Total reclaimed space" || echo "0B")

    # Remove build cache
    local cache_removed=$(docker builder prune -f 2>/dev/null | grep "Total reclaimed space" || echo "0B")

    log_success "Cleanup complete"
    log_info "  Images: $images_removed"
    log_info "  Build cache: $cache_removed"
}
