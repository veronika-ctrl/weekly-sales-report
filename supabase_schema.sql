-- Supabase Database Schema for Weekly Report System
-- Run this SQL in your Supabase SQL Editor after project setup is complete

-- Table 1: weekly_report_metrics
-- Stores precomputed metrics for each week to speed up frontend loading
CREATE TABLE IF NOT EXISTS weekly_report_metrics (
    base_week TEXT PRIMARY KEY,
    metrics JSONB NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    file_hashes JSONB,
    num_weeks INTEGER DEFAULT 8,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_weekly_report_metrics_base_week ON weekly_report_metrics(base_week);
CREATE INDEX IF NOT EXISTS idx_weekly_report_metrics_computed_at ON weekly_report_metrics(computed_at);

-- Table 2: budget_files
-- Stores budget CSV files by year for reuse across weeks
CREATE TABLE IF NOT EXISTS budget_files (
    id BIGSERIAL PRIMARY KEY,
    year INTEGER NOT NULL UNIQUE,
    week TEXT,
    filename TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for year lookups
CREATE INDEX IF NOT EXISTS idx_budget_files_year ON budget_files(year);

-- Table 3: budget_general
-- Stores budget general data (monthly breakdown by customer and metric)
CREATE TABLE IF NOT EXISTS budget_general (
    id BIGSERIAL PRIMARY KEY,
    base_week TEXT NOT NULL,
    metric TEXT NOT NULL,
    customer TEXT NOT NULL,
    month TEXT NOT NULL,
    value NUMERIC NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('budget', 'actuals')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(base_week, metric, customer, month, kind)
);

-- Indexes for budget_general
CREATE INDEX IF NOT EXISTS idx_budget_general_base_week ON budget_general(base_week);
CREATE INDEX IF NOT EXISTS idx_budget_general_metric ON budget_general(metric);
CREATE INDEX IF NOT EXISTS idx_budget_general_customer ON budget_general(customer);

-- Table 4: budget_general_totals
-- Stores budget general totals (aggregated by scope)
CREATE TABLE IF NOT EXISTS budget_general_totals (
    id BIGSERIAL PRIMARY KEY,
    base_week TEXT NOT NULL,
    metric TEXT NOT NULL,
    customer TEXT NOT NULL,
    scope TEXT NOT NULL,
    value NUMERIC NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('budget', 'actuals')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(base_week, metric, customer, scope, kind)
);

-- Indexes for budget_general_totals
CREATE INDEX IF NOT EXISTS idx_budget_general_totals_base_week ON budget_general_totals(base_week);
CREATE INDEX IF NOT EXISTS idx_budget_general_totals_metric ON budget_general_totals(metric);

-- Table 5: budget_markets_detailed
-- Stores budget markets detailed data (monthly breakdown by market and metric)
CREATE TABLE IF NOT EXISTS budget_markets_detailed (
    id BIGSERIAL PRIMARY KEY,
    base_week TEXT NOT NULL,
    market TEXT NOT NULL,
    metric TEXT NOT NULL,
    month TEXT NOT NULL,
    value NUMERIC NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('budget', 'actuals')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(base_week, market, metric, month, kind)
);

-- Indexes for budget_markets_detailed
CREATE INDEX IF NOT EXISTS idx_budget_markets_detailed_base_week ON budget_markets_detailed(base_week);
CREATE INDEX IF NOT EXISTS idx_budget_markets_detailed_market ON budget_markets_detailed(market);

-- Table 6: budget_markets_totals
-- Stores budget markets totals (aggregated by scope)
CREATE TABLE IF NOT EXISTS budget_markets_totals (
    id BIGSERIAL PRIMARY KEY,
    base_week TEXT NOT NULL,
    market TEXT NOT NULL,
    metric TEXT NOT NULL,
    scope TEXT NOT NULL,
    value NUMERIC NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('budget', 'actuals')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(base_week, market, metric, scope, kind)
);

-- Indexes for budget_markets_totals
CREATE INDEX IF NOT EXISTS idx_budget_markets_totals_base_week ON budget_markets_totals(base_week);
CREATE INDEX IF NOT EXISTS idx_budget_markets_totals_market ON budget_markets_totals(market);

-- Table 7: weeks
-- Tracks which weeks have been processed
CREATE TABLE IF NOT EXISTS weeks (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table 8: sync_runs
-- Tracks sync operations for debugging and monitoring
CREATE TABLE IF NOT EXISTS sync_runs (
    id TEXT PRIMARY KEY,
    base_week TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    row_counts JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for sync_runs
CREATE INDEX IF NOT EXISTS idx_sync_runs_base_week ON sync_runs(base_week);
CREATE INDEX IF NOT EXISTS idx_sync_runs_started_at ON sync_runs(started_at);
CREATE INDEX IF NOT EXISTS idx_sync_runs_success ON sync_runs(success);

-- Enable Row Level Security (RLS) - adjust policies as needed
ALTER TABLE weekly_report_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE budget_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE budget_general ENABLE ROW LEVEL SECURITY;
ALTER TABLE budget_general_totals ENABLE ROW LEVEL SECURITY;
ALTER TABLE budget_markets_detailed ENABLE ROW LEVEL SECURITY;
ALTER TABLE budget_markets_totals ENABLE ROW LEVEL SECURITY;
ALTER TABLE weeks ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_runs ENABLE ROW LEVEL SECURITY;

-- Create policies for anon access (adjust based on your security needs)
-- These policies allow read access for anonymous users (frontend)
-- and full access for service role (backend)
-- DROP IF EXISTS makes the script safe to run multiple times (idempotent)

-- Policy for weekly_report_metrics
DROP POLICY IF EXISTS "Allow anon read access" ON weekly_report_metrics;
DROP POLICY IF EXISTS "Allow service role full access" ON weekly_report_metrics;
CREATE POLICY "Allow anon read access" ON weekly_report_metrics
    FOR SELECT USING (true);
CREATE POLICY "Allow service role full access" ON weekly_report_metrics
    FOR ALL USING (auth.role() = 'service_role');

-- Policy for budget_files
DROP POLICY IF EXISTS "Allow anon read access" ON budget_files;
DROP POLICY IF EXISTS "Allow service role full access" ON budget_files;
CREATE POLICY "Allow anon read access" ON budget_files
    FOR SELECT USING (true);
CREATE POLICY "Allow service role full access" ON budget_files
    FOR ALL USING (auth.role() = 'service_role');

-- Policy for budget_general
DROP POLICY IF EXISTS "Allow anon read access" ON budget_general;
DROP POLICY IF EXISTS "Allow service role full access" ON budget_general;
CREATE POLICY "Allow anon read access" ON budget_general
    FOR SELECT USING (true);
CREATE POLICY "Allow service role full access" ON budget_general
    FOR ALL USING (auth.role() = 'service_role');

-- Policy for budget_general_totals
DROP POLICY IF EXISTS "Allow anon read access" ON budget_general_totals;
DROP POLICY IF EXISTS "Allow service role full access" ON budget_general_totals;
CREATE POLICY "Allow anon read access" ON budget_general_totals
    FOR SELECT USING (true);
CREATE POLICY "Allow service role full access" ON budget_general_totals
    FOR ALL USING (auth.role() = 'service_role');

-- Policy for budget_markets_detailed
DROP POLICY IF EXISTS "Allow anon read access" ON budget_markets_detailed;
DROP POLICY IF EXISTS "Allow service role full access" ON budget_markets_detailed;
CREATE POLICY "Allow anon read access" ON budget_markets_detailed
    FOR SELECT USING (true);
CREATE POLICY "Allow service role full access" ON budget_markets_detailed
    FOR ALL USING (auth.role() = 'service_role');

-- Policy for budget_markets_totals
DROP POLICY IF EXISTS "Allow anon read access" ON budget_markets_totals;
DROP POLICY IF EXISTS "Allow service role full access" ON budget_markets_totals;
CREATE POLICY "Allow anon read access" ON budget_markets_totals
    FOR SELECT USING (true);
CREATE POLICY "Allow service role full access" ON budget_markets_totals
    FOR ALL USING (auth.role() = 'service_role');

-- Policy for weeks
DROP POLICY IF EXISTS "Allow anon read access" ON weeks;
DROP POLICY IF EXISTS "Allow service role full access" ON weeks;
CREATE POLICY "Allow anon read access" ON weeks
    FOR SELECT USING (true);
CREATE POLICY "Allow service role full access" ON weeks
    FOR ALL USING (auth.role() = 'service_role');

-- Policy for sync_runs
DROP POLICY IF EXISTS "Allow anon read access" ON sync_runs;
DROP POLICY IF EXISTS "Allow service role full access" ON sync_runs;
CREATE POLICY "Allow anon read access" ON sync_runs
    FOR SELECT USING (true);
CREATE POLICY "Allow service role full access" ON sync_runs
    FOR ALL USING (auth.role() = 'service_role');

-- Comments for documentation
COMMENT ON TABLE weekly_report_metrics IS 'Cached weekly report metrics for fast frontend loading';
COMMENT ON TABLE budget_files IS 'Budget CSV files stored by year for reuse';
COMMENT ON TABLE budget_general IS 'Budget general data (monthly breakdown by customer and metric)';
COMMENT ON TABLE budget_general_totals IS 'Budget general totals (aggregated by scope)';
COMMENT ON TABLE budget_markets_detailed IS 'Budget markets detailed data (monthly breakdown by market and metric)';
COMMENT ON TABLE budget_markets_totals IS 'Budget markets totals (aggregated by scope)';
COMMENT ON TABLE weeks IS 'Tracks which weeks have been processed';
COMMENT ON TABLE sync_runs IS 'Tracks sync operations for debugging and monitoring';
