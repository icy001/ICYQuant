CREATE TABLE positions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    quantity DECIMAL(20, 8) NOT NULL,
    avg_cost DECIMAL(20, 8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_positions_symbol ON positions(symbol);
