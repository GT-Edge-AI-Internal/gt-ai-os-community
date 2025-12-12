#!/bin/bash
# GT AI OS Secret Generation Library
# Centralized, idempotent secret generation for deployment scripts
#
# Usage: source scripts/lib/secrets.sh
#        generate_all_secrets  # Populates .env with missing secrets only

set -e

# Source common functions if available
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/common.sh" ]; then
    source "$SCRIPT_DIR/common.sh"
fi

# =============================================================================
# SECRET GENERATION FUNCTIONS
# =============================================================================

# Generate a random hex string (for JWT secrets, encryption keys)
# Usage: generate_secret_hex [length]
# Default length: 64 characters (32 bytes)
generate_secret_hex() {
    local length=${1:-64}
    openssl rand -hex $((length / 2))
}

# Generate a Fernet key (for TFA encryption, API key encryption)
# Fernet requires base64-encoded 32-byte key
generate_fernet_key() {
    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || \
    openssl rand -base64 32
}

# Generate a secure password (for database passwords)
# Usage: generate_password [length]
# Default length: 32 characters
generate_password() {
    local length=${1:-32}
    # Use alphanumeric + special chars, avoiding problematic shell chars
    openssl rand -base64 48 | tr -dc 'a-zA-Z0-9!@#$%^&*()_+-=' | head -c "$length"
}

# Generate a simple alphanumeric password (for services that don't handle special chars well)
# Usage: generate_simple_password [length]
generate_simple_password() {
    local length=${1:-32}
    openssl rand -base64 48 | tr -dc 'a-zA-Z0-9' | head -c "$length"
}

# =============================================================================
# ENV FILE MANAGEMENT
# =============================================================================

# Get value from .env file
# Usage: get_env_value "KEY_NAME" ".env"
get_env_value() {
    local key="$1"
    local env_file="${2:-.env}"

    if [ -f "$env_file" ]; then
        grep "^${key}=" "$env_file" 2>/dev/null | cut -d'=' -f2- | head -1
    fi
}

# Set value in .env file (preserves existing, only sets if missing or empty)
# Usage: set_env_value "KEY_NAME" "value" ".env"
set_env_value() {
    local key="$1"
    local value="$2"
    local env_file="${3:-.env}"

    # Create file if it doesn't exist
    touch "$env_file"

    local existing=$(get_env_value "$key" "$env_file")

    if [ -z "$existing" ]; then
        # Key doesn't exist or is empty, add/update it
        if grep -q "^${key}=" "$env_file" 2>/dev/null; then
            # Key exists but is empty, update it
            if [[ "$OSTYPE" == "darwin"* ]]; then
                sed -i '' "s|^${key}=.*|${key}=${value}|" "$env_file"
            else
                sed -i "s|^${key}=.*|${key}=${value}|" "$env_file"
            fi
        else
            # Key doesn't exist, append it
            echo "${key}=${value}" >> "$env_file"
        fi
        return 0  # Secret was generated
    fi
    return 1  # Secret already exists
}

# =============================================================================
# MAIN SECRET GENERATION
# =============================================================================

# Generate all required secrets for GT AI OS
# This function is IDEMPOTENT - it only generates missing secrets
# Usage: generate_all_secrets [env_file]
generate_all_secrets() {
    local env_file="${1:-.env}"
    local generated_count=0

    echo "Checking and generating missing secrets..."

    # JWT and Authentication Secrets
    if set_env_value "JWT_SECRET" "$(generate_secret_hex 64)" "$env_file"; then
        echo "  Generated: JWT_SECRET"
        ((++generated_count))
    fi

    if set_env_value "CONTROL_PANEL_JWT_SECRET" "$(generate_secret_hex 64)" "$env_file"; then
        echo "  Generated: CONTROL_PANEL_JWT_SECRET"
        ((++generated_count))
    fi

    if set_env_value "RESOURCE_CLUSTER_SECRET_KEY" "$(generate_secret_hex 64)" "$env_file"; then
        echo "  Generated: RESOURCE_CLUSTER_SECRET_KEY"
        ((++generated_count))
    fi

    # Encryption Keys
    if set_env_value "TFA_ENCRYPTION_KEY" "$(generate_fernet_key)" "$env_file"; then
        echo "  Generated: TFA_ENCRYPTION_KEY"
        ((++generated_count))
    fi

    if set_env_value "API_KEY_ENCRYPTION_KEY" "$(generate_fernet_key)" "$env_file"; then
        echo "  Generated: API_KEY_ENCRYPTION_KEY"
        ((++generated_count))
    fi

    # Database Passwords (use simple passwords for PostgreSQL compatibility)
    if set_env_value "ADMIN_POSTGRES_PASSWORD" "$(generate_simple_password 32)" "$env_file"; then
        echo "  Generated: ADMIN_POSTGRES_PASSWORD"
        ((++generated_count))
    fi

    if set_env_value "TENANT_POSTGRES_PASSWORD" "$(generate_simple_password 32)" "$env_file"; then
        echo "  Generated: TENANT_POSTGRES_PASSWORD"
        ((++generated_count))
    fi

    # Sync TENANT_USER_PASSWORD with TENANT_POSTGRES_PASSWORD
    local tenant_pass=$(get_env_value "TENANT_POSTGRES_PASSWORD" "$env_file")
    if set_env_value "TENANT_USER_PASSWORD" "$tenant_pass" "$env_file"; then
        echo "  Set: TENANT_USER_PASSWORD (synced with TENANT_POSTGRES_PASSWORD)"
        ((++generated_count))
    fi

    if set_env_value "TENANT_REPLICATOR_PASSWORD" "$(generate_simple_password 32)" "$env_file"; then
        echo "  Generated: TENANT_REPLICATOR_PASSWORD"
        ((++generated_count))
    fi

    # Other Service Passwords
    if set_env_value "RABBITMQ_PASSWORD" "$(generate_simple_password 24)" "$env_file"; then
        echo "  Generated: RABBITMQ_PASSWORD"
        ((++generated_count))
    fi

    if [ $generated_count -eq 0 ]; then
        echo "  All secrets already present (no changes needed)"
    else
        echo "  Generated $generated_count new secret(s)"
    fi

    return 0
}

# Validate that all required secrets are present (non-empty)
# Usage: validate_secrets [env_file]
validate_secrets() {
    local env_file="${1:-.env}"
    local missing=0

    local required_secrets=(
        "JWT_SECRET"
        "CONTROL_PANEL_JWT_SECRET"
        "RESOURCE_CLUSTER_SECRET_KEY"
        "TFA_ENCRYPTION_KEY"
        "API_KEY_ENCRYPTION_KEY"
        "ADMIN_POSTGRES_PASSWORD"
        "TENANT_POSTGRES_PASSWORD"
        "TENANT_USER_PASSWORD"
        "RABBITMQ_PASSWORD"
    )

    echo "Validating required secrets..."

    for secret in "${required_secrets[@]}"; do
        local value=$(get_env_value "$secret" "$env_file")
        if [ -z "$value" ]; then
            echo "  MISSING: $secret"
            ((missing++))
        fi
    done

    if [ $missing -gt 0 ]; then
        echo "  $missing required secret(s) missing!"
        return 1
    fi

    echo "  All required secrets present"
    return 0
}

# =============================================================================
# TEMPLATE CREATION
# =============================================================================

# Create a .env.template file with placeholder values
# Usage: create_env_template [output_file]
create_env_template() {
    local output_file="${1:-.env.template}"

    cat > "$output_file" << 'EOF'
# GT AI OS Environment Configuration
# Copy this file to .env and customize values
# Secrets are auto-generated on first install if not provided

# =============================================================================
# AUTHENTICATION (Auto-generated if empty)
# =============================================================================
JWT_SECRET=
CONTROL_PANEL_JWT_SECRET=
RESOURCE_CLUSTER_SECRET_KEY=

# =============================================================================
# ENCRYPTION KEYS (Auto-generated if empty)
# =============================================================================
PASSWORD_RESET_ENCRYPTION_KEY=
TFA_ENCRYPTION_KEY=
API_KEY_ENCRYPTION_KEY=

# =============================================================================
# DATABASE PASSWORDS (Auto-generated if empty)
# =============================================================================
ADMIN_POSTGRES_PASSWORD=
TENANT_POSTGRES_PASSWORD=
TENANT_USER_PASSWORD=
TENANT_REPLICATOR_PASSWORD=
RABBITMQ_PASSWORD=

# =============================================================================
# API KEYS (Configure via Control Panel UI after installation)
# =============================================================================
# Note: LLM API keys (Groq, OpenAI, Anthropic) are configured through
# the Control Panel UI, not environment variables.

# =============================================================================
# SMTP (Enterprise Edition Only - Password Reset)
# =============================================================================
# Set via environment variables or configure below
# SMTP_HOST=smtp-relay.brevo.com
# SMTP_PORT=587
# SMTP_USERNAME=
# SMTP_PASSWORD=
# SMTP_FROM_EMAIL=noreply@yourdomain.com
# SMTP_FROM_NAME=GT AI OS

# =============================================================================
# DEPLOYMENT
# =============================================================================
COMPOSE_PROJECT_NAME=gentwo
ENVIRONMENT=production
EOF

    echo "Created $output_file"
}
