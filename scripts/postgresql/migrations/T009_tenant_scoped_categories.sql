-- T009_tenant_scoped_categories.sql
-- Tenant-Scoped Editable/Deletable Agent Categories
-- Issue: #215 - FR: Editable/Deletable Default Agent Categories
--
-- Changes:
-- 1. Creates categories table in each tenant schema
-- 2. Seeds default categories (General, Coding, Writing, etc.)
-- 3. Migrates existing per-user custom categories to tenant-scoped
--
-- Rollback: See bottom of file

BEGIN;

-- Apply to all existing tenant schemas
DO $$
DECLARE
    tenant_schema TEXT;
BEGIN
    FOR tenant_schema IN
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name LIKE 'tenant_%' AND schema_name != 'tenant_template'
    LOOP
        -- Create categories table
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %I.categories (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id UUID NOT NULL,
                name VARCHAR(100) NOT NULL,
                slug VARCHAR(100) NOT NULL,
                description TEXT,
                icon VARCHAR(10),
                is_default BOOLEAN DEFAULT FALSE,
                created_by UUID,
                sort_order INTEGER DEFAULT 0,
                is_deleted BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

                CONSTRAINT fk_categories_tenant FOREIGN KEY (tenant_id)
                    REFERENCES %I.tenants(id) ON DELETE CASCADE,
                CONSTRAINT fk_categories_created_by FOREIGN KEY (created_by)
                    REFERENCES %I.users(id) ON DELETE SET NULL,
                CONSTRAINT uq_categories_tenant_slug UNIQUE (tenant_id, slug)
            )
        ', tenant_schema, tenant_schema, tenant_schema);

        -- Create indexes
        EXECUTE format('
            CREATE INDEX IF NOT EXISTS idx_categories_tenant_id
                ON %I.categories(tenant_id)
        ', tenant_schema);

        EXECUTE format('
            CREATE INDEX IF NOT EXISTS idx_categories_slug
                ON %I.categories(tenant_id, slug)
        ', tenant_schema);

        EXECUTE format('
            CREATE INDEX IF NOT EXISTS idx_categories_created_by
                ON %I.categories(created_by)
        ', tenant_schema);

        EXECUTE format('
            CREATE INDEX IF NOT EXISTS idx_categories_is_deleted
                ON %I.categories(is_deleted) WHERE is_deleted = FALSE
        ', tenant_schema);

        -- Seed default categories for each tenant in this schema
        EXECUTE format('
            INSERT INTO %I.categories (tenant_id, name, slug, description, icon, is_default, sort_order)
            SELECT
                t.id,
                c.name,
                c.slug,
                c.description,
                c.icon,
                TRUE,
                c.sort_order
            FROM %I.tenants t
            CROSS JOIN (VALUES
                (''General'', ''general'', ''All-purpose agent for various tasks'', NULL, 10),
                (''Coding'', ''coding'', ''Programming and development assistance'', NULL, 20),
                (''Writing'', ''writing'', ''Content creation and editing'', NULL, 30),
                (''Analysis'', ''analysis'', ''Data analysis and insights'', NULL, 40),
                (''Creative'', ''creative'', ''Creative projects and brainstorming'', NULL, 50),
                (''Research'', ''research'', ''Research and fact-checking'', NULL, 60),
                (''Business'', ''business'', ''Business strategy and operations'', NULL, 70),
                (''Education'', ''education'', ''Teaching and learning assistance'', NULL, 80)
            ) AS c(name, slug, description, icon, sort_order)
            ON CONFLICT (tenant_id, slug) DO NOTHING
        ', tenant_schema, tenant_schema);

        -- Migrate existing per-user custom categories from users.preferences
        -- Custom categories are stored as: preferences->'custom_categories' = [{"name": "...", "description": "..."}, ...]
        EXECUTE format('
            INSERT INTO %I.categories (tenant_id, name, slug, description, created_by, is_default, sort_order)
            SELECT DISTINCT ON (u.tenant_id, lower(regexp_replace(cc.name, ''[^a-zA-Z0-9]+'', ''-'', ''g'')))
                u.tenant_id,
                cc.name,
                lower(regexp_replace(cc.name, ''[^a-zA-Z0-9]+'', ''-'', ''g'')),
                COALESCE(cc.description, ''Custom category''),
                u.id,
                FALSE,
                100 + ROW_NUMBER() OVER (PARTITION BY u.tenant_id ORDER BY cc.name)
            FROM %I.users u
            CROSS JOIN LATERAL jsonb_array_elements(
                COALESCE(u.preferences->''custom_categories'', ''[]''::jsonb)
            ) AS cc_json
            CROSS JOIN LATERAL (
                SELECT
                    cc_json->>''name'' AS name,
                    cc_json->>''description'' AS description
            ) AS cc
            WHERE cc.name IS NOT NULL AND cc.name != ''''
            ON CONFLICT (tenant_id, slug) DO NOTHING
        ', tenant_schema, tenant_schema);

        RAISE NOTICE 'Applied T009 categories table to schema: %', tenant_schema;
    END LOOP;
END $$;

COMMIT;

-- Verification query (run manually):
-- SELECT schema_name,
--        (SELECT COUNT(*) FROM information_schema.tables
--         WHERE table_schema = s.schema_name AND table_name = 'categories') as has_categories_table
-- FROM information_schema.schemata s
-- WHERE schema_name LIKE 'tenant_%' AND schema_name != 'tenant_template';

-- Rollback (if needed):
-- DO $$
-- DECLARE tenant_schema TEXT;
-- BEGIN
--     FOR tenant_schema IN
--         SELECT schema_name FROM information_schema.schemata
--         WHERE schema_name LIKE 'tenant_%' AND schema_name != 'tenant_template'
--     LOOP
--         EXECUTE format('DROP TABLE IF EXISTS %I.categories CASCADE', tenant_schema);
--         RAISE NOTICE 'Dropped categories table from schema: %', tenant_schema;
--     END LOOP;
-- END $$;
