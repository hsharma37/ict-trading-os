-- TradingOS durable storage foundation for the active top-level app.
-- Apply to separate dev and production Postgres databases.

BEGIN;

DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS vector;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'pgvector extension is unavailable; durable JSONB tables will still be created.';
END
$$;

CREATE TABLE IF NOT EXISTS app_documents (
    collection TEXT NOT NULL,
    id TEXT NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    PRIMARY KEY (collection, id)
);

CREATE INDEX IF NOT EXISTS idx_app_documents_collection ON app_documents(collection);
CREATE INDEX IF NOT EXISTS idx_app_documents_data_gin ON app_documents USING gin(data);

CREATE TABLE IF NOT EXISTS kb_sources (
    id TEXT PRIMARY KEY,
    title TEXT,
    url TEXT,
    source_type TEXT,
    tags TEXT[] NOT NULL DEFAULT '{}',
    concepts TEXT[] NOT NULL DEFAULT '{}',
    confidence_score NUMERIC,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_kb_sources_url
    ON kb_sources(url)
    WHERE url IS NOT NULL AND url <> '';
CREATE INDEX IF NOT EXISTS idx_kb_sources_data_gin ON kb_sources USING gin(data);

CREATE TABLE IF NOT EXISTS kb_chunks (
    id TEXT PRIMARY KEY,
    source_id TEXT REFERENCES kb_sources(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    chunk_text TEXT NOT NULL DEFAULT '',
    tokens TEXT[] NOT NULL DEFAULT '{}',
    lexical_vector JSONB NOT NULL DEFAULT '{}',
    embedding_json JSONB NOT NULL DEFAULT '[]',
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_kb_chunks_source_id ON kb_chunks(source_id);
CREATE INDEX IF NOT EXISTS idx_kb_chunks_data_gin ON kb_chunks USING gin(data);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        EXECUTE 'ALTER TABLE kb_chunks ADD COLUMN IF NOT EXISTS embedding vector(384)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_kb_chunks_embedding ON kb_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)';
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS trade_plans (
    id TEXT PRIMARY KEY,
    symbol TEXT,
    bias TEXT,
    status TEXT,
    strategy TEXT,
    session_name TEXT,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_trade_plans_symbol_status ON trade_plans(symbol, status);

CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY,
    symbol TEXT,
    side TEXT,
    status TEXT,
    plan_id TEXT,
    risk_pct NUMERIC,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_trades_symbol_status ON trades(symbol, status);

CREATE TABLE IF NOT EXISTS journal_entries (
    id TEXT PRIMARY KEY,
    trade_id TEXT,
    plan_id TEXT,
    symbol TEXT,
    session_name TEXT,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_journal_entries_symbol ON journal_entries(symbol);

CREATE TABLE IF NOT EXISTS market_snapshots (
    id TEXT PRIMARY KEY,
    symbol TEXT,
    timeframe TEXT,
    session_name TEXT,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_market_snapshots_symbol_created
    ON market_snapshots(symbol, created_at DESC);

CREATE TABLE IF NOT EXISTS risk_settings (
    id TEXT PRIMARY KEY,
    mode TEXT,
    kill_switch BOOLEAN NOT NULL DEFAULT FALSE,
    max_daily_loss NUMERIC,
    max_position_size NUMERIC,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    actor_id TEXT,
    action TEXT,
    entity_type TEXT,
    entity_id TEXT,
    risk_decision TEXT,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs(entity_type, entity_id);

CREATE TABLE IF NOT EXISTS workspace_settings (
    id TEXT PRIMARY KEY,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

COMMIT;
