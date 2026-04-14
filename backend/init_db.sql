-- ===============================================================
-- CITMS 3.6 - Database Initialization Script
-- Triggers & Materialized Views
-- ===============================================================

-- 0. Core Auth Tables Generation
CREATE TABLE IF NOT EXISTS roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_roles_name_active ON roles(name) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(100) NOT NULL,
    name VARCHAR(150) NOT NULL,
    module VARCHAR(50) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_permissions_code_active ON permissions(code) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS role_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_role_permissions_unique_active ON role_permissions(role_id, permission_id) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    parent_id UUID REFERENCES departments(id),
    manager_id UUID,
    level SMALLINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    address VARCHAR(255),
    city VARCHAR(100),
    country VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    employee_id VARCHAR(20),
    department_id UUID REFERENCES departments(id),
    location_id UUID REFERENCES locations(id),
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMPTZ,
    auth_provider VARCHAR(20) DEFAULT 'LOCAL',
    preferences JSONB DEFAULT '{}'::jsonb,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMPTZ,
    password_history JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_username_active ON users(username) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_email_active ON users(email) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS user_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    assigned_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

-- 1. Trigger: update_updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply update_updated_at to all tables
DO $$
DECLARE
    t text;
BEGIN
    FOR t IN (SELECT table_name FROM information_schema.columns WHERE table_schema = 'public' AND column_name = 'updated_at') LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trigger_update_updated_at ON %I', t);
        EXECUTE format('CREATE TRIGGER trigger_update_updated_at BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()', t);
    END LOOP;
END;
$$;

-- 2. Trigger: manage_license_seats_v36
CREATE OR REPLACE FUNCTION manage_license_seats_v36()
RETURNS TRIGGER AS $$
BEGIN
    -- CASE 1: INSERT (New installation)
    IF (TG_OP = 'INSERT') THEN
        IF NEW.license_id IS NOT NULL AND NEW.deleted_at IS NULL THEN
            UPDATE software_licenses SET used_seats = used_seats + 1 WHERE id = NEW.license_id;
        END IF;

    -- CASE 2: DELETE (Hard delete - rarely used but handled for safety)
    ELSIF (TG_OP = 'DELETE') THEN
        IF OLD.license_id IS NOT NULL AND OLD.deleted_at IS NULL THEN
            UPDATE software_licenses SET used_seats = GREATEST(0, used_seats - 1) WHERE id = OLD.license_id;
        END IF;

    -- CASE 3: UPDATE (Soft-delete, Restore, or Change License)
    ELSIF (TG_OP = 'UPDATE') THEN
        -- Case 3.1: Soft-delete (deleted_at set)
        IF OLD.deleted_at IS NULL AND NEW.deleted_at IS NOT NULL THEN
            IF OLD.license_id IS NOT NULL THEN
                UPDATE software_licenses SET used_seats = GREATEST(0, used_seats - 1) WHERE id = OLD.license_id;
            END IF;
        
        -- Case 3.2: Restore (deleted_at cleared)
        ELSIF OLD.deleted_at IS NOT NULL AND NEW.deleted_at IS NULL THEN
            IF NEW.license_id IS NOT NULL THEN
                UPDATE software_licenses SET used_seats = used_seats + 1 WHERE id = NEW.license_id;
            END IF;

        -- Case 3.3: Change License (while active)
        ELSIF NEW.deleted_at IS NULL AND OLD.license_id IS DISTINCT FROM NEW.license_id THEN
            IF OLD.license_id IS NOT NULL THEN
                UPDATE software_licenses SET used_seats = GREATEST(0, used_seats - 1) WHERE id = OLD.license_id;
            END IF;
            IF NEW.license_id IS NOT NULL THEN
                UPDATE software_licenses SET used_seats = used_seats + 1 WHERE id = NEW.license_id;
            END IF;
        END IF;
    END IF;
    RETURN NULL;
END;
$$ language 'plpgsql';

-- Check if table exists before creating trigger
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'software_installations') THEN
        -- Drop if exists to ensure clean update
        DROP TRIGGER IF EXISTS trigger_manage_license_seats ON software_installations;
        
        CREATE TRIGGER trigger_manage_license_seats
        AFTER INSERT OR UPDATE OR DELETE ON software_installations
        FOR EACH ROW EXECUTE FUNCTION manage_license_seats_v36();
    END IF;
END;
$$;

-- 3. Materialized Views
-- ... (existing MV definitions) ...

-- 4. pg_cron Schedule for Materialized Views (SRS §9.2)
-- Ensure pg_cron extension is available (usually in RDS/Cloud SQL or custom postgres)
-- Note: This requires pg_cron to be installed in the database.
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_extension WHERE extname = 'pg_cron') THEN
        -- Refresh according to Spec 3.6
        PERFORM cron.schedule('refresh-depreciation-daily', '0 2 * * *', 'REFRESH MATERIALIZED VIEW CONCURRENTLY mv_asset_depreciation');
        PERFORM cron.schedule('refresh-usage-15m', '*/15 * * * *', 'REFRESH MATERIALIZED VIEW CONCURRENTLY mv_software_usage_top10');
        PERFORM cron.schedule('refresh-sla-20m', '*/20 * * * *', 'REFRESH MATERIALIZED VIEW CONCURRENTLY mv_ticket_sla_stats');
        PERFORM cron.schedule('refresh-offline-10m', '*/10 * * * *', 'REFRESH MATERIALIZED VIEW CONCURRENTLY mv_offline_missing_devices');
    END IF;
END;
$$;

-- ===============================================================

-- MV: Asset Depreciation
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_asset_depreciation AS
SELECT 
    id,
    hostname,
    purchase_price,
    purchase_date,
    depreciation_years,
    salvage_value,
    GREATEST(
        salvage_value,
        purchase_price - (purchase_price - salvage_value) * (EXTRACT(YEAR FROM age(NOW(), purchase_date)) + EXTRACT(MONTH FROM age(NOW(), purchase_date))/12.0) / NULLIF(depreciation_years, 0)
    ) as current_value
FROM devices
WHERE deleted_at IS NULL AND purchase_price IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_asset_depreciation_id ON mv_asset_depreciation(id);

-- MV: Software Usage Top 10
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_software_usage_top10 AS
SELECT 
    sc.id,
    sc.name,
    COUNT(si.id) as installation_count
FROM software_catalog sc
JOIN software_installations si ON sc.id = si.software_catalog_id
WHERE sc.deleted_at IS NULL AND si.deleted_at IS NULL
GROUP BY sc.id, sc.name
ORDER BY installation_count DESC
LIMIT 10;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_software_usage_top10_id ON mv_software_usage_top10(id);

-- MV: Ticket SLA Stats
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_ticket_sla_stats AS
SELECT 
    location_id,
    department_id,
    COUNT(*) as total_tickets,
    COUNT(*) FILTER (WHERE status = 'RESOLVED' AND resolved_at <= sla_deadline) as met_sla,
    COUNT(*) FILTER (WHERE status = 'RESOLVED' AND resolved_at > sla_deadline) as missed_sla,
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'RESOLVED' AND resolved_at <= sla_deadline) / NULLIF(COUNT(*) FILTER (WHERE status = 'RESOLVED'), 0), 2) as sla_compliance_pct
FROM tickets
WHERE deleted_at IS NULL
GROUP BY location_id, department_id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_ticket_sla_stats_loc_dept ON mv_ticket_sla_stats(location_id, department_id);

-- MV: Offline/Missing Devices
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_offline_missing_devices AS
SELECT 
    id,
    hostname,
    last_seen,
    status,
    location_id
FROM devices
WHERE deleted_at IS NULL 
AND (last_seen < NOW() - INTERVAL '7 days' OR last_seen IS NULL)
AND status != 'RETIRED';

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_offline_missing_devices_id ON mv_offline_missing_devices(id);

-- ===============================================================
-- Remediation Patch v3.6.2
-- ===============================================================

-- Partitioning for history_logs
CREATE TABLE IF NOT EXISTS history_logs (
    id UUID DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL,
    table_name VARCHAR(50) NOT NULL,
    record_id UUID NOT NULL,
    action VARCHAR(20) NOT NULL,
    diff_json JSONB,
    changed_by_user_id UUID,
    ip_address VARCHAR(45),
    user_agent VARCHAR(255),
    request_id UUID NOT NULL,
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Create initial partitions for history_logs
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = 'history_logs_' || to_char(now(), 'YYYY_MM')) THEN
        EXECUTE 'CREATE TABLE history_logs_' || to_char(now(), 'YYYY_MM') || ' PARTITION OF history_logs FOR VALUES FROM (''' || date_trunc('month', now()) || ''') TO (''' || date_trunc('month', now() + interval '1 month') || ''')';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = 'history_logs_' || to_char(now() + interval '1 month', 'YYYY_MM')) THEN
        EXECUTE 'CREATE TABLE history_logs_' || to_char(now() + interval '1 month', 'YYYY_MM') || ' PARTITION OF history_logs FOR VALUES FROM (''' || date_trunc('month', now() + interval '1 month') || ''') TO (''' || date_trunc('month', now() + interval '2 months') || ''')';
    END IF;
END
$$;

-- ===============================================================
-- Remediation Patch v3.6.2
-- ===============================================================

-- Add bluetooth_mac to devices
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'devices' AND column_name = 'bluetooth_mac') THEN
        ALTER TABLE devices ADD COLUMN bluetooth_mac VARCHAR(17);
    END IF;
END;
$$;

-- Create audit_logs table
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(100),
    status VARCHAR(20) NOT NULL,
    details JSONB,
    ip_address VARCHAR(45)
);
