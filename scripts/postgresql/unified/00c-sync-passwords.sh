#!/bin/bash
# GT 2.0 Password Synchronization Script
# Runs AFTER role creation to sync passwords from environment variables
# This ensures passwords match what's in .env, not the hardcoded defaults

set -e

echo "🔐 GT 2.0 Password Sync - Updating passwords from environment..."

# Wait for PostgreSQL to be ready
until pg_isready -U postgres -d gt2_tenants; do
    echo "Waiting for PostgreSQL to be ready..."
    sleep 1
done

# Update gt2_tenant_user password from environment
if [ -n "$TENANT_USER_PASSWORD" ]; then
    psql -U postgres -d gt2_tenants -c "ALTER USER gt2_tenant_user WITH PASSWORD '$TENANT_USER_PASSWORD';" && \
        echo "✅ Synced gt2_tenant_user password from environment" || \
        echo "❌ Failed to sync gt2_tenant_user password"
else
    echo "⚠️  TENANT_USER_PASSWORD not set - using default password"
fi

# Update replicator password from environment
if [ -n "$POSTGRES_REPLICATION_PASSWORD" ]; then
    psql -U postgres -d gt2_tenants -c "ALTER USER replicator WITH PASSWORD '$POSTGRES_REPLICATION_PASSWORD';" && \
        echo "✅ Synced replicator password from environment" || \
        echo "❌ Failed to sync replicator password"
else
    echo "⚠️  POSTGRES_REPLICATION_PASSWORD not set - using default password"
fi

echo "🔐 Password synchronization complete"
