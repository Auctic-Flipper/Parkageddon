-- Simple Parking Counter Database
-- Just counts and events - nothing fancy

BEGIN;

-- =========================
-- Schema (2 Tables Only)
-- =========================

-- Table 1: Current count for each location (website reads this)
CREATE TABLE IF NOT EXISTS current_counts (
    location_id VARCHAR(100) PRIMARY KEY,
    camera_name VARCHAR(200) NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    last_change_type VARCHAR(20),
    last_update TIMESTAMPTZ NOT NULL
);

-- Table 2: Log of every count change (audit trail)
CREATE TABLE IF NOT EXISTS vehicle_events (
    event_id BIGSERIAL PRIMARY KEY,
    location_id VARCHAR(100) NOT NULL,
    camera_name VARCHAR(200) NOT NULL,
    count INTEGER NOT NULL,
    change_type VARCHAR(20) NOT NULL,
    track_id INTEGER,
    timestamp TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_location ON vehicle_events(location_id);
CREATE INDEX IF NOT EXISTS idx_timestamp ON vehicle_events(timestamp DESC);

-- =========================
-- Seed Data
-- =========================

-- Initialize your locations with 0 count
INSERT INTO current_counts (location_id, camera_name, count, last_update) VALUES
    ('entrance_1', 'Camera 1 (107)', 0, NOW()),
    ('entrance_2', 'Camera 2 (108)', 0, NOW())
ON CONFLICT (location_id) DO NOTHING;

COMMIT;