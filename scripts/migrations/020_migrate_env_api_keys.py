#!/usr/bin/env python3
"""
Migration 020: Import GROQ_API_KEY from environment to database

Migrates API keys from .env file to encrypted database storage for test-company tenant.
This is part of the move away from environment variables for API keys (#158, #219).

Idempotency: Checks if key already exists before importing
Target: test-company tenant only (as specified in requirements)

Usage:
    python scripts/migrations/020_migrate_env_api_keys.py

Environment variables required:
    - GROQ_API_KEY: The Groq API key to migrate (optional - skips if not set)
    - API_KEY_ENCRYPTION_KEY: Fernet encryption key (auto-generated if not set)
    - CONTROL_PANEL_DB_HOST: Database host (default: localhost)
    - CONTROL_PANEL_DB_PORT: Database port (default: 5432)
    - CONTROL_PANEL_DB_NAME: Database name (default: gt2_admin)
    - CONTROL_PANEL_DB_USER: Database user (default: postgres)
    - ADMIN_POSTGRES_PASSWORD: Database password
"""
import os
import sys
import json
import logging
from datetime import datetime

try:
    from cryptography.fernet import Fernet
    import psycopg2
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Run: pip install cryptography psycopg2-binary")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Migration constants
TARGET_TENANT_DOMAIN = "test-company"
PROVIDER = "groq"
MIGRATION_ID = "020"


def get_db_connection():
    """Get database connection using environment variables or defaults"""
    try:
        conn = psycopg2.connect(
            host=os.getenv("CONTROL_PANEL_DB_HOST", "localhost"),
            port=os.getenv("CONTROL_PANEL_DB_PORT", "5432"),
            database=os.getenv("CONTROL_PANEL_DB_NAME", "gt2_admin"),
            user=os.getenv("CONTROL_PANEL_DB_USER", "postgres"),
            password=os.getenv("ADMIN_POSTGRES_PASSWORD", "dev_password_change_in_prod")
        )
        return conn
    except psycopg2.Error as e:
        logger.error(f"Database connection failed: {e}")
        raise


def get_encryption_key() -> str:
    """Get or generate Fernet encryption key"""
    key = os.getenv("API_KEY_ENCRYPTION_KEY")
    if not key:
        # Generate a new key - in production this should be persisted
        key = Fernet.generate_key().decode()
        logger.warning("Generated new API_KEY_ENCRYPTION_KEY - add to .env for persistence:")
        logger.warning(f"  API_KEY_ENCRYPTION_KEY={key}")
    return key


def check_env_key_exists() -> str | None:
    """Check if GROQ_API_KEY environment variable exists and is valid"""
    groq_key = os.getenv("GROQ_API_KEY")

    # Skip placeholder values
    placeholder_values = [
        "gsk_your_actual_groq_api_key_here",
        "gsk_placeholder",
        "",
        None
    ]

    if groq_key in placeholder_values:
        logger.info("GROQ_API_KEY not set or is placeholder - skipping migration")
        return None

    # Validate format
    if not groq_key.startswith("gsk_"):
        logger.warning(f"GROQ_API_KEY has invalid format (should start with 'gsk_')")
        return None

    return groq_key


def get_tenant_id(conn, domain: str) -> int | None:
    """Get tenant ID by domain"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM tenants WHERE domain = %s AND deleted_at IS NULL",
            (domain,)
        )
        row = cur.fetchone()
        return row[0] if row else None


def check_db_key_exists(conn, tenant_id: int) -> bool:
    """Check if Groq key already exists in database for tenant"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT api_keys FROM tenants WHERE id = %s",
            (tenant_id,)
        )
        row = cur.fetchone()
        if row and row[0]:
            api_keys = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            if PROVIDER in api_keys and api_keys[PROVIDER].get("key"):
                return True
    return False


def migrate_api_key(conn, tenant_id: int, api_key: str, encryption_key: str) -> bool:
    """Encrypt and store API key in database"""
    try:
        cipher = Fernet(encryption_key.encode())
        encrypted_key = cipher.encrypt(api_key.encode()).decode()

        api_keys_data = {
            PROVIDER: {
                "key": encrypted_key,
                "secret": None,
                "enabled": True,
                "metadata": {
                    "migrated_from": "environment",
                    "migration_id": MIGRATION_ID,
                    "migration_date": datetime.utcnow().isoformat()
                },
                "updated_at": datetime.utcnow().isoformat(),
                "updated_by": f"migration-{MIGRATION_ID}"
            }
        }

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tenants
                SET api_keys = %s::jsonb,
                    api_key_encryption_version = 'v1',
                    updated_at = NOW()
                WHERE id = %s
                """,
                (json.dumps(api_keys_data), tenant_id)
            )
        conn.commit()
        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to migrate API key: {e}")
        return False


def run_migration() -> bool:
    """Main migration logic"""
    logger.info(f"=== Migration {MIGRATION_ID}: Import GROQ_API_KEY from environment ===")

    # Step 1: Check if env var exists
    groq_key = check_env_key_exists()
    if not groq_key:
        logger.info("Migration skipped: No valid GROQ_API_KEY in environment")
        return True  # Not an error - just nothing to migrate

    logger.info(f"Found GROQ_API_KEY in environment (length: {len(groq_key)})")

    # Step 2: Connect to database
    try:
        conn = get_db_connection()
        logger.info("Connected to database")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return False

    try:
        # Step 3: Get tenant ID
        tenant_id = get_tenant_id(conn, TARGET_TENANT_DOMAIN)
        if not tenant_id:
            logger.warning(f"Tenant '{TARGET_TENANT_DOMAIN}' not found - skipping migration")
            logger.info("This is expected for fresh installs before tenant creation")
            return True

        logger.info(f"Found tenant '{TARGET_TENANT_DOMAIN}' with ID: {tenant_id}")

        # Step 4: Check if DB key already exists (idempotency)
        if check_db_key_exists(conn, tenant_id):
            logger.info("Migration already complete - Groq key exists in database")
            return True

        # Step 5: Get/generate encryption key
        encryption_key = get_encryption_key()

        # Step 6: Migrate the key
        logger.info(f"Migrating GROQ_API_KEY to database for tenant {tenant_id}...")
        if migrate_api_key(conn, tenant_id, groq_key, encryption_key):
            logger.info(f"=== Migration {MIGRATION_ID} completed successfully ===")
            logger.info("The GROQ_API_KEY env var can now be removed from docker-compose.yml")
            return True
        else:
            logger.error(f"Migration {MIGRATION_ID} failed")
            return False

    except Exception as e:
        logger.error(f"Migration failed with error: {e}")
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
