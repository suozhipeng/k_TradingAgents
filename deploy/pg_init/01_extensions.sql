-- PostgreSQL init for AStock Pro production database.
-- Compatible with plain postgres:16 (no TimescaleDB, no pg_cron required).

-- ── Extensions (optional, plain postgres compatible) ────────────────
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Schema ─────────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS astock;
ALTER DATABASE astock SET search_path TO astock, public;

-- ── Application user ───────────────────────────────────────────────
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'astock_app') THEN
    CREATE ROLE astock_app WITH LOGIN PASSWORD 'astock_app_2026';
  END IF;
END$$;

GRANT USAGE ON SCHEMA astock TO astock_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA astock TO astock_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA astock TO astock_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA astock GRANT ALL ON TABLES TO astock_app;

-- ── Migration versions tracking (matches app's migration_versions table) ─
CREATE TABLE IF NOT EXISTS astock.migration_versions (
    version_id TEXT NOT NULL,
    description TEXT,
    applied_by TEXT,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checksum TEXT,
    duration_ms BIGINT DEFAULT 0,
    status TEXT DEFAULT 'applied',
    rollback_sql TEXT,
    PRIMARY KEY (version_id)
);

-- ── Monthly partition maintenance function ─────────────────────────
-- The app's PGStore.init_schema() creates the main tables via SQLAlchemy.
-- This function creates monthly partitions for kline_bars.
-- Run manually or via a scheduler (cron, systemd timer, etc.):
--   SELECT astock.create_kline_partition();
CREATE OR REPLACE FUNCTION astock.create_kline_partition()
RETURNS void AS $$
DECLARE
    next_month TEXT;
BEGIN
    next_month := to_char(CURRENT_DATE + INTERVAL '1 month', 'YYYY_MM');
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS astock.kline_bars_%s PARTITION OF astock.kline_bars
         FOR VALUES FROM (%L) TO (%L)',
        next_month,
        date_trunc('month', CURRENT_DATE + INTERVAL '1 month'),
        date_trunc('month', CURRENT_DATE + INTERVAL '2 months')
    );
END;
$$ LANGUAGE plpgsql;

-- TimescaleDB / pg_cron notes (uncomment if using TimescaleDB image):
-- CREATE EXTENSION IF NOT EXISTS timescaledb;
-- CREATE EXTENSION IF NOT EXISTS pg_cron;
-- SELECT cron.schedule('create-kline-partition', '0 2 * * *', 'SELECT astock.create_kline_partition();');
