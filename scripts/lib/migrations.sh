#!/bin/bash
# GT 2.0 Database Migration Functions
# Idempotent migration checks and execution for admin and tenant databases

# Check if admin postgres container is running
check_admin_db_running() {
    docker ps --filter "name=gentwo-controlpanel-postgres" --filter "status=running" --format "{{.Names}}" | grep -q "gentwo-controlpanel-postgres"
}

# Check if tenant postgres container is running
check_tenant_db_running() {
    docker ps --filter "name=gentwo-tenant-postgres-primary" --filter "status=running" --format "{{.Names}}" | grep -q "gentwo-tenant-postgres-primary"
}

# Wait for a container to be healthy (up to 60 seconds)
wait_for_container_healthy() {
    local container="$1"
    local max_wait=60
    local waited=0

    log_info "Waiting for $container to be healthy..."
    while [ $waited -lt $max_wait ]; do
        local status=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "none")
        if [ "$status" = "healthy" ]; then
            log_success "$container is healthy"
            return 0
        fi
        # Also accept running containers without healthcheck
        local running=$(docker inspect --format='{{.State.Running}}' "$container" 2>/dev/null || echo "false")
        if [ "$running" = "true" ] && [ "$status" = "none" ]; then
            sleep 5  # Give it a few seconds to initialize
            log_success "$container is running"
            return 0
        fi
        sleep 2
        waited=$((waited + 2))
    done
    log_error "$container failed to become healthy after ${max_wait}s"
    return 1
}

# Ensure admin database is running
ensure_admin_db_running() {
    if check_admin_db_running; then
        return 0
    fi

    log_info "Starting admin database containers..."
    dc up -d postgres 2>/dev/null || {
        log_error "Failed to start admin database"
        return 1
    }

    wait_for_container_healthy "gentwo-controlpanel-postgres" || return 1
    return 0
}

# Ensure tenant database is running
ensure_tenant_db_running() {
    if check_tenant_db_running; then
        return 0
    fi

    log_info "Starting tenant database containers..."
    dc up -d tenant-postgres-primary 2>/dev/null || {
        log_error "Failed to start tenant database"
        return 1
    }

    wait_for_container_healthy "gentwo-tenant-postgres-primary" || return 1
    return 0
}

# Run admin database migration
run_admin_migration() {
    local migration_num="$1"
    local migration_file="$2"
    local check_func="$3"

    # Run check function if provided
    if [ -n "$check_func" ] && type "$check_func" &>/dev/null; then
        if ! $check_func; then
            return 0  # Migration already applied
        fi
    fi

    log_info "Applying migration $migration_num..."

    if [ ! -f "$migration_file" ]; then
        log_error "Migration script not found: $migration_file"
        echo "Run: git pull"
        return 1
    fi

    if docker exec -i gentwo-controlpanel-postgres psql -U postgres -d gt2_admin < "$migration_file"; then
        log_success "Migration $migration_num applied successfully"
        return 0
    else
        log_error "Migration $migration_num failed"
        return 1
    fi
}

# Run tenant database migration
run_tenant_migration() {
    local migration_num="$1"
    local migration_file="$2"
    local check_func="$3"

    # Run check function if provided
    if [ -n "$check_func" ] && type "$check_func" &>/dev/null; then
        if ! $check_func; then
            return 0  # Migration already applied
        fi
    fi

    log_info "Applying migration $migration_num..."

    if [ ! -f "$migration_file" ]; then
        log_error "Migration script not found: $migration_file"
        echo "Run: git pull"
        return 1
    fi

    if docker exec -i gentwo-tenant-postgres-primary psql -U postgres -d gt2_tenants < "$migration_file"; then
        log_success "Migration $migration_num applied successfully"
        return 0
    else
        log_error "Migration $migration_num failed"
        return 1
    fi
}

# Admin migration checks
check_migration_006() {
    local exists=$(docker exec gentwo-controlpanel-postgres psql -U postgres -d gt2_admin -tAc \
        "SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_schema='public' AND table_name='tenants' AND column_name='frontend_url');" 2>/dev/null || echo "false")
    [ "$exists" != "t" ]
}

check_migration_008() {
    local exists=$(docker exec gentwo-controlpanel-postgres psql -U postgres -d gt2_admin -tAc \
        "SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_schema='public' AND table_name='password_reset_rate_limits' AND column_name='ip_address');" 2>/dev/null || echo "false")
    [ "$exists" = "t" ]
}

check_migration_009() {
    local exists=$(docker exec gentwo-controlpanel-postgres psql -U postgres -d gt2_admin -tAc \
        "SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_schema='public' AND table_name='users' AND column_name='tfa_enabled');" 2>/dev/null || echo "false")
    [ "$exists" != "t" ]
}

check_migration_010() {
    local count=$(docker exec gentwo-controlpanel-postgres psql -U postgres -d gt2_admin -tAc \
        "SELECT COUNT(*) FROM model_configs WHERE (context_window IS NULL OR max_tokens IS NULL) AND provider = 'groq';" 2>/dev/null || echo "error")
    [ "$count" != "0" ] && [ "$count" != "error" ] && [ -n "$count" ]
}

check_migration_011() {
    local exists=$(docker exec gentwo-controlpanel-postgres psql -U postgres -d gt2_admin -tAc \
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='system_versions');" 2>/dev/null || echo "false")
    [ "$exists" != "t" ]
}

check_migration_012() {
    local exists=$(docker exec gentwo-controlpanel-postgres psql -U postgres -d gt2_admin -tAc \
        "SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_schema='public' AND table_name='tenants' AND column_name='optics_enabled');" 2>/dev/null || echo "false")
    [ "$exists" != "t" ]
}

check_migration_013() {
    # Returns true (needs migration) if old column exists
    local exists=$(docker exec gentwo-controlpanel-postgres psql -U postgres -d gt2_admin -tAc \
        "SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_schema='public' AND table_name='model_configs' AND column_name='cost_per_1k_input');" 2>/dev/null || echo "false")
    [ "$exists" = "t" ]
}

check_migration_014() {
    # Returns true (needs migration) if any Groq model has NULL or 0 pricing
    local count=$(docker exec gentwo-controlpanel-postgres psql -U postgres -d gt2_admin -tAc \
        "SELECT COUNT(*) FROM model_configs WHERE provider = 'groq' AND (cost_per_million_input IS NULL OR cost_per_million_input = 0 OR cost_per_million_output IS NULL OR cost_per_million_output = 0);" 2>/dev/null || echo "0")
    [ "$count" != "0" ] && [ -n "$count" ]
}

check_migration_015() {
    # Returns true (needs migration) if pricing is outdated
    # Check if gpt-oss-120b has old pricing ($1.20) instead of new ($0.15)
    local price=$(docker exec gentwo-controlpanel-postgres psql -U postgres -d gt2_admin -tAc \
        "SELECT cost_per_million_input FROM model_configs WHERE model_id LIKE '%gpt-oss-120b%' LIMIT 1;" 2>/dev/null || echo "0")
    # Needs migration if price is > 1.0 (old pricing was $1.20)
    [ "$(echo "$price > 1.0" | bc -l 2>/dev/null || echo "0")" = "1" ]
}

check_migration_016() {
    # Returns true (needs migration) if is_compound column doesn't exist
    local exists=$(docker exec gentwo-controlpanel-postgres psql -U postgres -d gt2_admin -tAc \
        "SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_schema='public' AND table_name='model_configs' AND column_name='is_compound');" 2>/dev/null || echo "false")
    [ "$exists" != "t" ]
}

check_migration_017() {
    # Returns true (needs migration) if compound pricing is incorrect (> $0.50 input means old pricing)
    local price=$(docker exec gentwo-controlpanel-postgres psql -U postgres -d gt2_admin -tAc \
        "SELECT cost_per_million_input FROM model_configs WHERE model_id LIKE '%compound%' AND model_id NOT LIKE '%mini%' LIMIT 1;" 2>/dev/null || echo "0")
    [ "$(echo "$price > 0.50" | bc -l 2>/dev/null || echo "0")" = "1" ]
}

check_migration_018() {
    # Returns true (needs migration) if monthly_budget_cents column doesn't exist
    local exists=$(docker exec gentwo-controlpanel-postgres psql -U postgres -d gt2_admin -tAc \
        "SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_schema='public' AND table_name='tenants' AND column_name='monthly_budget_cents');" 2>/dev/null || echo "false")
    [ "$exists" != "t" ]
}

check_migration_019() {
    # Returns true (needs migration) if embedding_usage_logs table doesn't exist
    local exists=$(docker exec gentwo-controlpanel-postgres psql -U postgres -d gt2_admin -tAc \
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='embedding_usage_logs');" 2>/dev/null || echo "false")
    [ "$exists" != "t" ]
}

check_migration_020() {
    # Returns true (needs migration) if:
    # 1. GROQ_API_KEY env var exists and is not a placeholder
    # 2. AND test-company tenant exists
    # 3. AND groq key is NOT already in database for test-company

    # Check if GROQ_API_KEY env var exists
    local groq_key="${GROQ_API_KEY:-}"
    if [ -z "$groq_key" ] || [ "$groq_key" = "gsk_your_actual_groq_api_key_here" ] || [ "$groq_key" = "gsk_placeholder" ]; then
        # No valid env key to migrate
        return 1
    fi

    # Check if test-company tenant exists and has groq key already
    local has_key=$(docker exec gentwo-controlpanel-postgres psql -U postgres -d gt2_admin -tAc \
        "SELECT EXISTS (SELECT 1 FROM tenants WHERE domain = 'test-company' AND api_keys IS NOT NULL AND api_keys->>'groq' IS NOT NULL AND api_keys->'groq'->>'key' IS NOT NULL);" 2>/dev/null || echo "false")

    # If tenant already has key, no migration needed
    [ "$has_key" != "t" ]
}

check_migration_021() {
    # Returns true (needs migration) if NVIDIA models don't exist in model_configs
    local count=$(docker exec gentwo-controlpanel-postgres psql -U postgres -d gt2_admin -tAc \
        "SELECT COUNT(*) FROM model_configs WHERE provider = 'nvidia';" 2>/dev/null || echo "0")
    [ "$count" = "0" ] || [ -z "$count" ]
}

check_migration_022() {
    # Returns true (needs migration) if sessions table doesn't exist
    local exists=$(docker exec gentwo-controlpanel-postgres psql -U postgres -d gt2_admin -tAc \
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='sessions');" 2>/dev/null || echo "false")
    [ "$exists" != "t" ]
}

check_migration_023() {
    # Returns true (needs migration) if model_configs.id UUID column doesn't exist
    # This migration adds proper UUID primary key instead of using model_id string
    local exists=$(docker exec gentwo-controlpanel-postgres psql -U postgres -d gt2_admin -tAc \
        "SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_schema='public' AND table_name='model_configs' AND column_name='id' AND data_type='uuid');" 2>/dev/null || echo "false")
    [ "$exists" != "t" ]
}

check_migration_024() {
    # Returns true (needs migration) if model_configs still has unique constraint on model_id alone
    # (should be unique on model_id + provider instead)
    local exists=$(docker exec gentwo-controlpanel-postgres psql -U postgres -d gt2_admin -tAc \
        "SELECT EXISTS (SELECT FROM information_schema.table_constraints WHERE constraint_name='model_configs_model_id_unique' AND table_name='model_configs' AND table_schema='public');" 2>/dev/null || echo "false")
    [ "$exists" = "t" ]
}

check_migration_025() {
    # Returns true (needs migration) if old nvidia model format exists (nvidia/meta-* prefix)
    local count=$(docker exec gentwo-controlpanel-postgres psql -U postgres -d gt2_admin -tAc \
        "SELECT COUNT(*) FROM model_configs WHERE provider = 'nvidia' AND model_id LIKE 'nvidia/meta-%';" 2>/dev/null || echo "0")
    [ "$count" != "0" ] && [ -n "$count" ]
}

check_migration_026() {
    # Returns true (needs migration) if old format exists (moonshot-ai with hyphen instead of moonshotai)
    local count=$(docker exec gentwo-controlpanel-postgres psql -U postgres -d gt2_admin -tAc \
        "SELECT COUNT(*) FROM model_configs WHERE provider = 'nvidia' AND model_id LIKE 'moonshot-ai/%';" 2>/dev/null || echo "0")
    [ "$count" != "0" ] && [ -n "$count" ]
}

check_migration_027() {
    # Returns true (needs migration) if any tenant is missing NVIDIA model assignments
    # Counts tenants that don't have ALL active nvidia models assigned
    local nvidia_count=$(docker exec gentwo-controlpanel-postgres psql -U postgres -d gt2_admin -tAc \
        "SELECT COUNT(*) FROM model_configs WHERE provider = 'nvidia' AND is_active = true;" 2>/dev/null || echo "0")

    if [ "$nvidia_count" = "0" ] || [ -z "$nvidia_count" ]; then
        return 1  # No nvidia models, nothing to assign
    fi

    # Check if any tenant is missing nvidia assignments
    local missing=$(docker exec gentwo-controlpanel-postgres psql -U postgres -d gt2_admin -tAc \
        "SELECT COUNT(*) FROM tenants t WHERE NOT EXISTS (
            SELECT 1 FROM tenant_model_configs tmc
            JOIN model_configs mc ON mc.id = tmc.model_config_id
            WHERE tmc.tenant_id = t.id AND mc.provider = 'nvidia'
        );" 2>/dev/null || echo "0")

    [ "$missing" != "0" ] && [ -n "$missing" ]
}

check_migration_028() {
    # Returns true (needs migration) if any model has wrong max_tokens
    local wrong_value=$(docker exec gentwo-controlpanel-postgres psql -U postgres -d gt2_admin -tAc \
        "SELECT COUNT(*) FROM model_configs WHERE
         (model_id = 'llama-3.1-8b-instant' AND max_tokens != 32000) OR
         (model_id = 'meta-llama/llama-guard-4-12b' AND max_tokens != 1024);" 2>/dev/null || echo "0")
    [ "$wrong_value" != "0" ] && [ -n "$wrong_value" ]
}

# Tenant migration checks
check_migration_T001() {
    local exists=$(docker exec gentwo-tenant-postgres-primary psql -U postgres -d gt2_tenants -tAc \
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema='tenant_test_company' AND table_name='tenants');" 2>/dev/null || echo "false")
    [ "$exists" != "t" ]
}

check_migration_T002() {
    local exists=$(docker exec gentwo-tenant-postgres-primary psql -U postgres -d gt2_tenants -tAc \
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema='tenant_test_company' AND table_name='team_memberships');" 2>/dev/null || echo "false")
    [ "$exists" != "t" ]
}

check_migration_T002B() {
    local exists=$(docker exec gentwo-tenant-postgres-primary psql -U postgres -d gt2_tenants -tAc \
        "SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_schema='tenant_test_company' AND table_name='team_memberships' AND column_name='status');" 2>/dev/null || echo "false")
    [ "$exists" != "t" ]
}

check_migration_T003() {
    local exists=$(docker exec gentwo-tenant-postgres-primary psql -U postgres -d gt2_tenants -tAc \
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema='tenant_test_company' AND table_name='team_resource_shares');" 2>/dev/null || echo "false")
    [ "$exists" != "t" ]
}

check_migration_T005() {
    local exists=$(docker exec gentwo-tenant-postgres-primary psql -U postgres -d gt2_tenants -tAc \
        "SET search_path TO tenant_test_company; SELECT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'team_memberships'::regclass AND conname = 'check_team_permission' AND pg_get_constraintdef(oid) LIKE '%manager%');" 2>/dev/null || echo "false")
    [ "$exists" != "t" ]
}

check_migration_T006() {
    local exists=$(docker exec gentwo-tenant-postgres-primary psql -U postgres -d gt2_tenants -tAc \
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema='tenant_test_company' AND table_name='auth_logs');" 2>/dev/null || echo "false")
    [ "$exists" != "t" ]
}

check_migration_T009() {
    # Returns true (needs migration) if categories table doesn't exist
    local exists=$(docker exec gentwo-tenant-postgres-primary psql -U postgres -d gt2_tenants -tAc \
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema='tenant_test_company' AND table_name='categories');" 2>/dev/null || echo "false")
    [ "$exists" != "t" ]
}

# Run all admin migrations
run_admin_migrations() {
    log_header "Admin Database Migrations"

    # Ensure admin database is running (start if needed)
    if ! ensure_admin_db_running; then
        log_error "Could not start admin database, skipping admin migrations"
        return 1
    fi

    run_admin_migration "006" "scripts/migrations/006_add_tenant_frontend_url.sql" "check_migration_006" || return 1
    run_admin_migration "008" "scripts/migrations/008_remove_ip_address_from_rate_limits.sql" "check_migration_008" || return 1
    run_admin_migration "009" "scripts/migrations/009_add_tfa_schema.sql" "check_migration_009" || return 1
    run_admin_migration "010" "scripts/migrations/010_update_model_context_windows.sql" "check_migration_010" || return 1
    run_admin_migration "011" "scripts/migrations/011_add_system_management_tables.sql" "check_migration_011" || return 1
    run_admin_migration "012" "scripts/migrations/012_add_optics_enabled.sql" "check_migration_012" || return 1
    run_admin_migration "013" "scripts/migrations/013_rename_cost_columns.sql" "check_migration_013" || return 1
    run_admin_migration "014" "scripts/migrations/014_backfill_groq_pricing.sql" "check_migration_014" || return 1
    run_admin_migration "015" "scripts/migrations/015_update_groq_pricing_dec_2025.sql" "check_migration_015" || return 1
    run_admin_migration "016" "scripts/migrations/016_add_is_compound_column.sql" "check_migration_016" || return 1
    run_admin_migration "017" "scripts/migrations/017_fix_compound_pricing.sql" "check_migration_017" || return 1
    run_admin_migration "018" "scripts/migrations/018_add_budget_storage_pricing.sql" "check_migration_018" || return 1
    run_admin_migration "019" "scripts/migrations/019_add_embedding_usage.sql" "check_migration_019" || return 1

    # Migration 020: Import GROQ_API_KEY from environment to database (Python script)
    # This is a one-time migration for existing installations
    if check_migration_020 2>/dev/null; then
        log_info "Applying migration 020 (API key migration)..."
        if [ -f "scripts/migrations/020_migrate_env_api_keys.py" ]; then
            # Run the Python migration script
            if python3 scripts/migrations/020_migrate_env_api_keys.py; then
                log_success "Migration 020 applied successfully"
            else
                log_warning "Migration 020 skipped or failed (this is OK for fresh installs)"
            fi
        else
            log_warning "Migration 020 script not found, skipping"
        fi
    fi

    # Migration 021: Add NVIDIA NIM models to model_configs (Issue #266)
    run_admin_migration "021" "scripts/migrations/021_add_nvidia_models.sql" "check_migration_021" || return 1

    # Migration 022: Add sessions table for OWASP/NIST compliant session management (Issue #264)
    run_admin_migration "022" "scripts/migrations/022_add_session_management.sql" "check_migration_022" || return 1

    # Migration 023: Add UUID primary key to model_configs (fix using model_id string as PK)
    run_admin_migration "023" "scripts/migrations/023_add_uuid_primary_key_to_model_configs.sql" "check_migration_023" || return 1

    # Migration 024: Allow same model_id with different providers
    run_admin_migration "024" "scripts/migrations/024_allow_same_model_id_different_providers.sql" "check_migration_024" || return 1

    # Migration 025: Fix NVIDIA model names to match API format
    run_admin_migration "025" "scripts/migrations/025_fix_nvidia_model_names.sql" "check_migration_025" || return 1

    # Migration 026: Fix NVIDIA model_ids to exact API format
    run_admin_migration "026" "scripts/migrations/026_fix_nvidia_model_ids_api_format.sql" "check_migration_026" || return 1

    # Migration 027: Ensure NVIDIA models are assigned to all tenants
    # This fixes partial 021 migrations where models were added but not assigned
    run_admin_migration "027" "scripts/migrations/027_assign_nvidia_models_to_tenants.sql" "check_migration_027" || return 1

    # Migration 028: Fix Groq model max_tokens (llama-3.1-8b-instant and llama-guard)
    run_admin_migration "028" "scripts/migrations/028_fix_groq_max_tokens.sql" "check_migration_028" || return 1

    log_success "All admin migrations complete"
    return 0
}

# Run all tenant migrations
run_tenant_migrations() {
    log_header "Tenant Database Migrations"

    # Ensure tenant database is running (start if needed)
    if ! ensure_tenant_db_running; then
        log_error "Could not start tenant database, skipping tenant migrations"
        return 1
    fi

    run_tenant_migration "T001" "scripts/postgresql/migrations/T001_rename_teams_to_tenants.sql" "check_migration_T001" || return 1
    run_tenant_migration "T002" "scripts/postgresql/migrations/T002_create_collaboration_teams.sql" "check_migration_T002" || return 1
    run_tenant_migration "T002B" "scripts/postgresql/migrations/T002B_add_invitation_status.sql" "check_migration_T002B" || return 1
    run_tenant_migration "T003" "scripts/postgresql/migrations/T003_team_resource_shares.sql" "check_migration_T003" || return 1

    # T004 is always run (idempotent - updates trigger function)
    log_info "Applying migration T004 (update validate_resource_share)..."
    if [ -f "scripts/postgresql/migrations/T004_update_validate_resource_share.sql" ]; then
        docker exec -i gentwo-tenant-postgres-primary psql -U postgres -d gt2_tenants \
            < scripts/postgresql/migrations/T004_update_validate_resource_share.sql || return 1
        log_success "Migration T004 applied successfully"
    fi

    run_tenant_migration "T005" "scripts/postgresql/migrations/T005_team_observability.sql" "check_migration_T005" || return 1
    run_tenant_migration "T006" "scripts/postgresql/migrations/T006_auth_logs.sql" "check_migration_T006" || return 1

    # T007 is always run (idempotent - creates indexes if not exists)
    log_info "Applying migration T007 (query optimization indexes)..."
    if [ -f "scripts/postgresql/migrations/T007_optimize_queries.sql" ]; then
        docker exec -i gentwo-tenant-postgres-primary psql -U postgres -d gt2_tenants \
            < scripts/postgresql/migrations/T007_optimize_queries.sql || return 1
        log_success "Migration T007 applied successfully"
    fi

    # T008 is always run (idempotent - creates indexes if not exists)
    # Fixes GitHub Issue #173 - Database Optimizations
    log_info "Applying migration T008 (performance indexes for agents/datasets/teams)..."
    if [ -f "scripts/postgresql/migrations/T008_add_performance_indexes.sql" ]; then
        docker exec -i gentwo-tenant-postgres-primary psql -U postgres -d gt2_tenants \
            < scripts/postgresql/migrations/T008_add_performance_indexes.sql || return 1
        log_success "Migration T008 applied successfully"
    fi

    # T009 - Tenant-scoped agent categories (Issue #215)
    run_tenant_migration "T009" "scripts/postgresql/migrations/T009_tenant_scoped_categories.sql" "check_migration_T009" || return 1

    log_success "All tenant migrations complete"
    return 0
}

# Run all migrations
run_all_migrations() {
    run_admin_migrations || return 1
    run_tenant_migrations || return 1
    return 0
}
