#!/bin/bash
# GT 2.0 Admin PostgreSQL Custom Entrypoint
# Ensures postgres user password is synced from environment variable on every startup

set -e

echo "🔧 GT 2.0 Admin PostgreSQL Startup..."

# Function to update postgres user password from environment variable
update_postgres_password() {
    echo "🔐 Syncing postgres user password from environment..."

    # Update postgres superuser password if POSTGRES_PASSWORD is set
    if [ -n "$POSTGRES_PASSWORD" ]; then
        psql -U postgres -d gt2_admin -c "ALTER USER postgres WITH PASSWORD '$POSTGRES_PASSWORD';" >/dev/null 2>&1 && \
            echo "✅ Updated postgres user password" || \
            echo "⚠️  Could not update postgres password (database may not be ready yet)"
    fi

    # Also update gt2_admin if it exists and ADMIN_USER_PASSWORD is set
    if [ -n "$ADMIN_USER_PASSWORD" ]; then
        psql -U postgres -d gt2_admin -c "ALTER USER gt2_admin WITH PASSWORD '$ADMIN_USER_PASSWORD';" >/dev/null 2>&1 && \
            echo "✅ Updated gt2_admin user password" || \
            echo "⚠️  Could not update gt2_admin password (user may not exist yet)"
    fi
}

# Function to configure after PostgreSQL starts
configure_after_start() {
    sleep 5  # Wait for PostgreSQL to fully start

    # Update passwords from environment variables if PostgreSQL is running
    if pg_isready -U postgres >/dev/null 2>&1; then
        update_postgres_password
    fi
}

# Configure after PostgreSQL starts (in background)
configure_after_start &

echo "🚀 Starting Admin PostgreSQL..."

# Call the original PostgreSQL entrypoint
exec docker-entrypoint.sh "$@"
