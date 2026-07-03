-- ICYQuant V1 core schema
-- Target database: PostgreSQL
-- V1 only creates 6 core tables:
-- users, accounts, positions, orders, trades, instruments

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    user_code VARCHAR(64) NOT NULL UNIQUE,
    username VARCHAR(64) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'DISABLED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS accounts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users (id),
    account_no VARCHAR(64) NOT NULL UNIQUE,
    account_type VARCHAR(32) NOT NULL DEFAULT 'SPOT',
    base_currency VARCHAR(16) NOT NULL DEFAULT 'USD',
    cash_balance NUMERIC(20, 4) NOT NULL DEFAULT 0,
    frozen_cash NUMERIC(20, 4) NOT NULL DEFAULT 0,
    status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'FROZEN', 'CLOSED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS instruments (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(64) NOT NULL UNIQUE,
    exchange VARCHAR(32) NOT NULL,
    instrument_type VARCHAR(32) NOT NULL,
    base_currency VARCHAR(16),
    quote_currency VARCHAR(16),
    tick_size NUMERIC(20, 8) NOT NULL DEFAULT 0.0001,
    lot_size NUMERIC(20, 8) NOT NULL DEFAULT 1,
    status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'HALTED', 'DELISTED')),
    listed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS positions (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES accounts (id),
    instrument_id BIGINT NOT NULL REFERENCES instruments (id),
    direction VARCHAR(8) NOT NULL CHECK (direction IN ('LONG', 'SHORT')),
    quantity NUMERIC(20, 8) NOT NULL DEFAULT 0,
    available_quantity NUMERIC(20, 8) NOT NULL DEFAULT 0,
    avg_price NUMERIC(20, 8) NOT NULL DEFAULT 0,
    market_value NUMERIC(20, 8) NOT NULL DEFAULT 0,
    unrealized_pnl NUMERIC(20, 8) NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_positions_account_instrument_direction UNIQUE (account_id, instrument_id, direction)
);

CREATE TABLE IF NOT EXISTS orders (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES accounts (id),
    instrument_id BIGINT NOT NULL REFERENCES instruments (id),
    client_order_id VARCHAR(64) NOT NULL UNIQUE,
    side VARCHAR(8) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    position_effect VARCHAR(8) NOT NULL DEFAULT 'OPEN' CHECK (position_effect IN ('OPEN', 'CLOSE')),
    order_type VARCHAR(16) NOT NULL CHECK (order_type IN ('MARKET', 'LIMIT')),
    time_in_force VARCHAR(8) NOT NULL DEFAULT 'GTC' CHECK (time_in_force IN ('GTC', 'IOC', 'FOK')),
    quantity NUMERIC(20, 8) NOT NULL,
    price NUMERIC(20, 8),
    filled_quantity NUMERIC(20, 8) NOT NULL DEFAULT 0,
    avg_fill_price NUMERIC(20, 8) NOT NULL DEFAULT 0,
    status VARCHAR(16) NOT NULL DEFAULT 'NEW' CHECK (status IN ('NEW', 'PARTIAL', 'FILLED', 'CANCELED', 'REJECTED')),
    placed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS trades (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES orders (id),
    account_id BIGINT NOT NULL REFERENCES accounts (id),
    instrument_id BIGINT NOT NULL REFERENCES instruments (id),
    trade_no VARCHAR(64) NOT NULL UNIQUE,
    side VARCHAR(8) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity NUMERIC(20, 8) NOT NULL,
    price NUMERIC(20, 8) NOT NULL,
    fee NUMERIC(20, 8) NOT NULL DEFAULT 0,
    traded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON accounts (user_id);
CREATE INDEX IF NOT EXISTS idx_positions_account_id ON positions (account_id);
CREATE INDEX IF NOT EXISTS idx_positions_instrument_id ON positions (instrument_id);
CREATE INDEX IF NOT EXISTS idx_orders_account_id ON orders (account_id);
CREATE INDEX IF NOT EXISTS idx_orders_instrument_id ON orders (instrument_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status);
CREATE INDEX IF NOT EXISTS idx_trades_order_id ON trades (order_id);
CREATE INDEX IF NOT EXISTS idx_trades_account_id ON trades (account_id);
CREATE INDEX IF NOT EXISTS idx_trades_instrument_id ON trades (instrument_id);
