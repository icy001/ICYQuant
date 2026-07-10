CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS system_info (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    version TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO system_info(version)
VALUES
('0.3.0-beta2');