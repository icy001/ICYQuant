CREATE TABLE reconciliation (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(36) UNIQUE NOT NULL,
    status VARCHAR(20) NOT NULL,
    differences JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    action VARCHAR(50) NOT NULL,
    symbol VARCHAR(50),
    before_value DECIMAL(20, 8),
    after_value DECIMAL(20, 8),
    reason VARCHAR(255),
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_reconciliation_run_id ON reconciliation(run_id);
CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_symbol ON audit_logs(symbol);
