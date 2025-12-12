#!/bin/bash
# GT 2.0 Common Library Functions
# Shared utilities for deployment scripts

# Color codes for output formatting
export RED='\033[0;31m'
export GREEN='\033[0;32m'
export YELLOW='\033[1;33m'
export BLUE='\033[0;34m'
export NC='\033[0m' # No Color

# Logging functions with timestamps
log_info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] ℹ️  $*${NC}"
}

log_success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] ✅ $*${NC}"
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] ⚠️  $*${NC}"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ❌ $*${NC}"
}

log_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$*${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# Check if running from GT-2.0 root directory
check_root_directory() {
    if [ ! -f "docker-compose.yml" ]; then
        log_error "docker-compose.yml not found"
        echo "Please run this script from the GT-2.0 root directory"
        exit 1
    fi
}

# Prompt for user confirmation
confirm() {
    local message="$1"
    read -p "$(echo -e "${YELLOW}${message} (y/N) ${NC}")" -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]]
}

# Check if deployment is running
check_deployment_running() {
    if ! docker ps --filter "name=gentwo-" --format "{{.Names}}" | grep -q "gentwo-"; then
        log_warning "No running deployment found"
        return 1
    fi
    return 0
}
