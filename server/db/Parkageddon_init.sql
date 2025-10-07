-- Postgres init: create schema (if missing) and seed data (idempotent).
-- Safe to run multiple times.

BEGIN;

-- =========================
-- Schema
-- =========================

-- Garages
CREATE TABLE IF NOT EXISTS garages (
    garage_id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
);

-- Floors
CREATE TABLE IF NOT EXISTS floors (
    floor_id SERIAL PRIMARY KEY,
    garage_id INT NOT NULL REFERENCES garages(garage_id) ON DELETE CASCADE,
    floor_number INT NOT NULL,
    floor_name VARCHAR(50)  -- included to match seed for Highrise
);

-- Ensure uniqueness of floor per garage so seeds don't duplicate
-- Use a unique index since ADD CONSTRAINT IF NOT EXISTS isn't available.
CREATE UNIQUE INDEX IF NOT EXISTS floors_unique_garage_floor ON floors(garage_id, floor_number);

-- Current snapshot of each floor
CREATE TABLE IF NOT EXISTS floor_status (
    floor_id INT NOT NULL REFERENCES floors(floor_id) ON DELETE CASCADE,
    vehicle_type VARCHAR(20) CHECK (vehicle_type IN ('car', 'motorcycle')) NOT NULL,
    total_spots INT NOT NULL,
    free_spots INT NOT NULL,
    last_updated TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (floor_id, vehicle_type)
);

-- Historical log of updates
CREATE TABLE IF NOT EXISTS floor_history (
    history_id SERIAL PRIMARY KEY,
    floor_id INT NOT NULL REFERENCES floors(floor_id) ON DELETE CASCADE,
    vehicle_type VARCHAR(20) CHECK (vehicle_type IN ('car', 'motorcycle')) NOT NULL,
    total_spots INT NOT NULL,
    free_spots INT NOT NULL,
    recorded_at TIMESTAMP DEFAULT NOW()
);

-- Backfill column if schema existed without floor_name
ALTER TABLE floors ADD COLUMN IF NOT EXISTS floor_name VARCHAR(50);

-- =========================
-- Seed data
-- =========================

-- Garages
INSERT INTO garages (name) VALUES
    ('Fields Parking'),
    ('Hutson Marsh Griffith Parking'),
    ('Highrise Parking')
ON CONFLICT (name) DO NOTHING;

-- Floors for Fields Parking (3 floors)
INSERT INTO floors (garage_id, floor_number)
SELECT g.garage_id, fnum
FROM garages g
CROSS JOIN (VALUES (1), (2), (3)) AS f(fnum)
WHERE g.name = 'Fields Parking'
ON CONFLICT DO NOTHING;

-- Floors for Hutson Marsh Griffith Parking (4 floors)
INSERT INTO floors (garage_id, floor_number)
SELECT g.garage_id, fnum
FROM garages g
CROSS JOIN (VALUES (1), (2), (3), (4)) AS f(fnum)
WHERE g.name = 'Hutson Marsh Griffith Parking'
ON CONFLICT DO NOTHING;

-- Named floors for Highrise Parking (color levels)
INSERT INTO floors (garage_id, floor_number, floor_name)
SELECT g.garage_id, fnum, fname
FROM garages g
JOIN (VALUES
    (1, 'Green'),
    (2, 'Purple'),
    (3, 'Blue'),
    (4, 'Gold')
) AS f(fnum, fname) ON TRUE
WHERE g.name = 'Highrise Parking'
ON CONFLICT DO NOTHING;

-- Seed floor_status with base values for all floors (0 total, 0 free)
INSERT INTO floor_status (floor_id, vehicle_type, total_spots, free_spots)
SELECT f.floor_id, v.vehicle_type, 0, 0
FROM floors f
CROSS JOIN (VALUES ('car'), ('motorcycle')) AS v(vehicle_type)
ON CONFLICT DO NOTHING;

COMMIT;
