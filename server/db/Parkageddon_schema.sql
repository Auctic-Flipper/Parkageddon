<<<<<<< HEAD
-- Garages
CREATE TABLE IF NOT EXISTS garages (
    garage_id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
);

-- Floors
CREATE TABLE IF NOT EXISTS floors (
    floor_id SERIAL PRIMARY KEY,
    garage_id INT NOT NULL REFERENCES garages(garage_id) ON DELETE CASCADE,
    floor_number INT NOT NULL
);

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
=======
-- Garages
CREATE TABLE IF NOT EXISTS garages (
    garage_id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
);

-- Floors
CREATE TABLE IF NOT EXISTS floors (
    floor_id SERIAL PRIMARY KEY,
    garage_id INT NOT NULL REFERENCES garages(garage_id) ON DELETE CASCADE,
    floor_number INT NOT NULL
);

-- Current snapshot of each floor
CREATE TABLE IF NOT EXISTS floor_status (
    floor_id INT NOT NULL REFERENCES floors(floor_id) ON DELETE CASCADE,
    vehicle_type VARCHAR(20) CHECK (vehicle_type IN ('car', 'motorcycle')),
    total_spots INT NOT NULL,
    free_spots INT NOT NULL,
    last_updated TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (floor_id, vehicle_type)
);

-- Historical log of updates
CREATE TABLE IF NOT EXISTS floor_history (
    history_id SERIAL PRIMARY KEY,
    floor_id INT NOT NULL REFERENCES floors(floor_id) ON DELETE CASCADE,
    vehicle_type VARCHAR(20) CHECK (vehicle_type IN ('car', 'motorcycle')),
    total_spots INT NOT NULL,
    free_spots INT NOT NULL,
    recorded_at TIMESTAMP DEFAULT NOW()
);
>>>>>>> 79cbb883bd0a5b1f196a96f1f39058011e757e03
