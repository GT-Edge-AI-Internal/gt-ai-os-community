#!/bin/bash
# GT 2.0 PostgreSQL Custom Entrypoint
# Ensures pg_hba.conf is configured on EVERY startup, not just initialization

set -e

echo "🔧 GT 2.0 PostgreSQL Startup - Configuring replication..."

# Function to configure pg_hba.conf
configure_pg_hba() {
    local pg_hba_path="/var/lib/postgresql/data/pg_hba.conf"
    
    if [ -f "$pg_hba_path" ]; then
        echo "📝 Configuring pg_hba.conf for replication..."
        
        # Remove any existing GT 2.0 replication entries to avoid duplicates
        grep -v "# GT 2.0 Replication" "$pg_hba_path" > /tmp/pg_hba_clean.conf || true
        mv /tmp/pg_hba_clean.conf "$pg_hba_path"
        
        # Add replication entries
        cat >> "$pg_hba_path" << 'EOF'

# GT 2.0 Replication Configuration
host    replication     replicator      172.16.0.0/12           md5
host    replication     replicator      172.20.0.0/16           md5  
host    replication     replicator      172.18.0.0/16           md5
host    replication     replicator      10.0.0.0/8              md5
host    all             all             172.16.0.0/12           md5
host    all             all             172.20.0.0/16           md5
host    all             all             172.18.0.0/16           md5
host    all             all             10.0.0.0/8              md5
EOF
        
        echo "✅ pg_hba.conf configured for replication"
    else
        echo "⚠️  pg_hba.conf not found - will be created during initialization"
    fi
}

# If PostgreSQL data directory exists, configure it before starting
if [ -d /var/lib/postgresql/data ] && [ -f /var/lib/postgresql/data/PG_VERSION ]; then
    configure_pg_hba
fi

# Function to update user passwords from environment variables
update_user_passwords() {
    echo "🔐 Updating user passwords from environment variables..."

    # Update gt2_tenant_user password if TENANT_USER_PASSWORD is set
    if [ -n "$TENANT_USER_PASSWORD" ]; then
        psql -U postgres -d gt2_tenants -c "ALTER USER gt2_tenant_user WITH PASSWORD '$TENANT_USER_PASSWORD';" >/dev/null 2>&1 && \
            echo "✅ Updated gt2_tenant_user password" || \
            echo "⚠️  Could not update gt2_tenant_user password (user may not exist yet)"
    fi

    # Update replicator password if TENANT_REPLICATOR_PASSWORD is set
    if [ -n "$POSTGRES_REPLICATION_PASSWORD" ]; then
        psql -U postgres -d gt2_tenants -c "ALTER USER replicator WITH PASSWORD '$POSTGRES_REPLICATION_PASSWORD';" >/dev/null 2>&1 && \
            echo "✅ Updated replicator password" || \
            echo "⚠️  Could not update replicator password (user may not exist yet)"
    fi
}

# Function to configure after PostgreSQL starts
configure_after_start() {
    sleep 5  # Wait for PostgreSQL to fully start
    configure_pg_hba

    # Reload configuration if PostgreSQL is running
    if pg_isready -U postgres >/dev/null 2>&1; then
        echo "🔄 Reloading PostgreSQL configuration..."
        psql -U postgres -c "SELECT pg_reload_conf();" >/dev/null 2>&1 || true

        # Update passwords from environment variables
        update_user_passwords
    fi
}

# Configure after PostgreSQL starts (in background)
configure_after_start &

echo "🚀 Starting PostgreSQL with GT 2.0 configuration..."

# Pre-create tablespace directories with proper ownership for Linux compatibility
# Required for x86/DGX deployments where bind mounts preserve host ownership
echo "📁 Preparing tablespace directories..."
mkdir -p /var/lib/postgresql/tablespaces/tenant_test
chown postgres:postgres /var/lib/postgresql/tablespaces/tenant_test
chmod 700 /var/lib/postgresql/tablespaces/tenant_test
echo "✅ Tablespace directories ready"

# Call the original PostgreSQL entrypoint
exec docker-entrypoint.sh "$@"