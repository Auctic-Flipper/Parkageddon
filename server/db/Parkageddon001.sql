-- ============================================================
-- PARKAGEDDON DATABASE SCHEMA v001
-- Complete parking garage tracking system with Fields Parking focus
-- ============================================================
-- 
-- Fields Parking Structure:
-- - Faculty: Level 1 only (97 spots)
-- - Student: Levels 2, 3, 4 (299 spots total)
-- 
-- Cameras:
-- - Camera A: Level 1 entrance (Faculty)
-- - Camera B: Crossover point (Level 1 → Level 2)
-- - Camera C: Level 2 entrance (Student)
--
-- Also supports:
-- - Hutson Marsh Griffith Parking
-- - Highrise Parking
-- - Vehicle counter system
-- ============================================================

BEGIN;

-- ============================================================
-- MAIN APP TABLES (for dashboard - matches SQLAlchemy models)
-- ============================================================

-- Garages: Main parking facilities
CREATE TABLE IF NOT EXISTS garages (
    garage_id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

-- Floors: Levels within each garage
CREATE TABLE IF NOT EXISTS floors (
    floor_id SERIAL PRIMARY KEY,
    garage_id INTEGER NOT NULL REFERENCES garages(garage_id) ON DELETE CASCADE,
    floor_number INTEGER NOT NULL,
    floor_name VARCHAR(100)
);

-- Unique floor per garage
CREATE UNIQUE INDEX IF NOT EXISTS floors_unique_garage_floor 
ON floors(garage_id, floor_number);

-- Current parking status for each floor
CREATE TABLE IF NOT EXISTS floor_status (
    floor_id INTEGER NOT NULL REFERENCES floors(floor_id) ON DELETE CASCADE,
    vehicle_type VARCHAR(20) CHECK (vehicle_type IN ('car', 'motorcycle', 'compact', 'truck')) NOT NULL,
    total_spots INTEGER NOT NULL DEFAULT 0,
    free_spots INTEGER NOT NULL DEFAULT 0 CHECK (free_spots >= 0),
    last_updated TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (floor_id, vehicle_type)
);

-- Historical log of parking changes
CREATE TABLE IF NOT EXISTS floor_history (
    history_id SERIAL PRIMARY KEY,
    floor_id INTEGER NOT NULL REFERENCES floors(floor_id) ON DELETE CASCADE,
    vehicle_type VARCHAR(20) CHECK (vehicle_type IN ('car', 'motorcycle', 'compact', 'truck')) NOT NULL,
    total_spots INTEGER NOT NULL,
    free_spots INTEGER NOT NULL,
    recorded_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- FIELDS PARKING SPECIFIC TABLES
-- ============================================================

-- Camera locations (Fields Parking specific)
CREATE TABLE IF NOT EXISTS cameras (
    camera_id SERIAL PRIMARY KEY,
    garage_id INTEGER NOT NULL REFERENCES garages(garage_id) ON DELETE CASCADE,
    camera_name VARCHAR(100) NOT NULL,
    camera_code VARCHAR(10) NOT NULL CHECK (camera_code IN ('A', 'B', 'C')),
    location_description TEXT,
    UNIQUE(garage_id, camera_code)
);

-- Vehicle events from cameras (Fields Parking specific)
CREATE TABLE IF NOT EXISTS camera_events (
    event_id SERIAL PRIMARY KEY,
    camera_code VARCHAR(10) NOT NULL,
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('in', 'out')),
    count INTEGER NOT NULL DEFAULT 0,
    timestamp TIMESTAMP DEFAULT NOW(),
    recorded_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- VEHICLE COUNTER TABLES (for general camera system)
-- ============================================================

-- Vehicle events: Logs every vehicle detection event
CREATE TABLE IF NOT EXISTS vehicle_events (
    event_id SERIAL PRIMARY KEY,
    location_id VARCHAR(100) NOT NULL,
    camera_name VARCHAR(200),
    count INTEGER NOT NULL,
    change_type VARCHAR(20) NOT NULL CHECK (change_type IN ('increase', 'decrease')),
    track_id INTEGER,
    timestamp TIMESTAMP,
    recorded_at TIMESTAMP DEFAULT NOW()
);

-- Current counts: Latest vehicle count per location
CREATE TABLE IF NOT EXISTS current_counts (
    location_id VARCHAR(100) PRIMARY KEY,
    camera_name VARCHAR(200),
    count INTEGER NOT NULL DEFAULT 0,
    last_change_type VARCHAR(20),
    last_update TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================

-- Floor history indexes
CREATE INDEX IF NOT EXISTS idx_floor_history_floor_time 
ON floor_history(floor_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_floor_history_time 
ON floor_history(recorded_at DESC);

-- Camera events indexes
CREATE INDEX IF NOT EXISTS idx_camera_events_time 
ON camera_events(recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_camera_events_camera 
ON camera_events(camera_code, recorded_at DESC);

-- Vehicle events indexes
CREATE INDEX IF NOT EXISTS idx_vehicle_events_location 
ON vehicle_events(location_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_vehicle_events_time 
ON vehicle_events(recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_vehicle_events_type 
ON vehicle_events(change_type, recorded_at DESC);

-- Floor status indexes
CREATE INDEX IF NOT EXISTS idx_floor_status_floor 
ON floor_status(floor_id);

CREATE INDEX IF NOT EXISTS idx_floor_status_vehicle_type 
ON floor_status(vehicle_type);

-- ============================================================
-- SEED DATA
-- ============================================================

-- Insert garages
INSERT INTO garages (name) VALUES
    ('Fields Parking'),
    ('Hutson Marsh Griffith Parking'),
    ('Highrise Parking')
ON CONFLICT (name) DO NOTHING;

-- Insert floors for Fields Parking (4 levels - Faculty:1, Student:2-4)
INSERT INTO floors (garage_id, floor_number, floor_name)
SELECT g.garage_id, floor_num, 
       CASE floor_num 
           WHEN 1 THEN 'Faculty Section'
           WHEN 2 THEN 'Student Level 2'
           WHEN 3 THEN 'Student Level 3' 
           WHEN 4 THEN 'Student Level 4'
       END
FROM garages g
CROSS JOIN (VALUES (1), (2), (3), (4)) AS floors(floor_num)
WHERE g.name = 'Fields Parking'
ON CONFLICT DO NOTHING;

-- Insert floors for Hutson Marsh Griffith Parking (4 floors)
INSERT INTO floors (garage_id, floor_number, floor_name)
SELECT g.garage_id, floor_num,
       CASE floor_num 
           WHEN 1 THEN 'Floor 1'
           WHEN 2 THEN 'Floor 2'
           WHEN 3 THEN 'Floor 3' 
           WHEN 4 THEN 'Floor 4'
       END
FROM garages g
CROSS JOIN (VALUES (1), (2), (3), (4)) AS floors(floor_num)
WHERE g.name = 'Hutson Marsh Griffith Parking'
ON CONFLICT DO NOTHING;

-- Insert floors for Highrise Parking (4 color-coded levels)
INSERT INTO floors (garage_id, floor_number, floor_name)
SELECT g.garage_id, floor_num, floor_name_colored
FROM garages g
CROSS JOIN (VALUES 
    (1, 'Green Level'), 
    (2, 'Purple Level'), 
    (3, 'Blue Level'), 
    (4, 'Gold Level')
) AS floors(floor_num, floor_name_colored)
WHERE g.name = 'Highrise Parking'
ON CONFLICT DO NOTHING;

-- Initialize floor_status with Fields Parking specific capacities
-- Fields Parking Floor 1 (Faculty): 97 car spots
INSERT INTO floor_status (floor_id, vehicle_type, total_spots, free_spots)
SELECT f.floor_id, 'car', 97, 97
FROM floors f
JOIN garages g ON g.garage_id = f.garage_id
WHERE g.name = 'Fields Parking' AND f.floor_number = 1
ON CONFLICT DO NOTHING;

-- Fields Parking Floors 2-4 (Student): 299 car spots total (100+99+100)
INSERT INTO floor_status (floor_id, vehicle_type, total_spots, free_spots)
SELECT f.floor_id, 'car', 
    CASE f.floor_number
        WHEN 2 THEN 100
        WHEN 3 THEN 99
        WHEN 4 THEN 100
    END,
    CASE f.floor_number
        WHEN 2 THEN 100
        WHEN 3 THEN 99
        WHEN 4 THEN 100
    END
FROM floors f
JOIN garages g ON g.garage_id = f.garage_id
WHERE g.name = 'Fields Parking' AND f.floor_number IN (2, 3, 4)
ON CONFLICT DO NOTHING;

-- Other garages: default 50 car and 50 motorcycle spots per floor
INSERT INTO floor_status (floor_id, vehicle_type, total_spots, free_spots)
SELECT f.floor_id, vt, 50, 50
FROM floors f
JOIN garages g ON g.garage_id = f.garage_id
CROSS JOIN (VALUES ('car'), ('motorcycle')) AS vehicle_types(vt)
WHERE g.name IN ('Hutson Marsh Griffith Parking', 'Highrise Parking')
ON CONFLICT DO NOTHING;

-- Insert Fields Parking cameras
INSERT INTO cameras (garage_id, camera_name, camera_code, location_description)
SELECT g.garage_id, name, code, description
FROM garages g
CROSS JOIN (VALUES 
    ('Camera A - Level 1 Entrance', 'A', 'Detects cars entering Level 1 (Faculty section)'),
    ('Camera B - Crossover Point', 'B', 'Detects cars moving from Level 1 to Level 2'),
    ('Camera C - Level 2 Entrance', 'C', 'Detects cars entering Level 2 (Student section)')
) AS cams(name, code, description)
WHERE g.name = 'Fields Parking'
ON CONFLICT DO NOTHING;

-- Initialize vehicle counter locations
INSERT INTO current_counts (location_id, camera_name, count, last_change_type)
VALUES 
    ('entrance_1', 'Camera 1 (107)', 0, 'increase'),
    ('entrance_2', 'Camera 2 (108)', 0, 'increase')
ON CONFLICT (location_id) DO NOTHING;

COMMIT;

-- ============================================================
-- STORED PROCEDURES
-- ============================================================

-- Process camera event for Fields Parking and update occupancy
CREATE OR REPLACE FUNCTION process_camera_event(
    p_camera_code VARCHAR,
    p_direction VARCHAR
) RETURNS JSONB
LANGUAGE plpgsql AS $$
DECLARE
    v_garage_id INTEGER;
    v_faculty_floor_id INTEGER;
    v_student_floor_ids INTEGER[];
    v_new_occupied INTEGER;
    v_result JSONB;
    v_faculty_occupied INTEGER;
    v_student_occupied INTEGER;
    v_faculty_total INTEGER;
    v_student_total INTEGER;
BEGIN
    -- Get Fields Parking garage_id
    SELECT garage_id INTO v_garage_id FROM garages WHERE name = 'Fields Parking';
    
    -- Get floor IDs
    SELECT floor_id INTO v_faculty_floor_id 
    FROM floors WHERE garage_id = v_garage_id AND floor_number = 1;
    
    SELECT ARRAY_AGG(floor_id) INTO v_student_floor_ids
    FROM floors WHERE garage_id = v_garage_id AND floor_number IN (2, 3, 4);
    
    -- Get current occupied counts
    SELECT COALESCE(SUM(total_spots - free_spots), 0) INTO v_faculty_occupied
    FROM floor_status WHERE floor_id = v_faculty_floor_id;
    
    SELECT COALESCE(SUM(total_spots - free_spots), 0) INTO v_student_occupied
    FROM floor_status WHERE floor_id = ANY(v_student_floor_ids);
    
    -- Get total spots
    SELECT COALESCE(SUM(total_spots), 0) INTO v_faculty_total
    FROM floor_status WHERE floor_id = v_faculty_floor_id;
    
    SELECT COALESCE(SUM(total_spots), 0) INTO v_student_total
    FROM floor_status WHERE floor_id = ANY(v_student_floor_ids);
    
    -- Process based on camera and direction
    IF p_camera_code = 'A' THEN
        -- Camera A: Level 1 entrance (Faculty only)
        IF p_direction = 'in' THEN
            IF v_faculty_occupied >= v_faculty_total THEN
                RAISE EXCEPTION 'Faculty parking is full (%)', v_faculty_total;
            END IF;
            UPDATE floor_status 
            SET free_spots = free_spots - 1, last_updated = NOW()
            WHERE floor_id = v_faculty_floor_id AND vehicle_type = 'car'
            AND free_spots > 0;
        ELSIF p_direction = 'out' THEN
            UPDATE floor_status 
            SET free_spots = LEAST(free_spots + 1, v_faculty_total), last_updated = NOW()
            WHERE floor_id = v_faculty_floor_id AND vehicle_type = 'car'
            AND free_spots < v_faculty_total;
        END IF;
        
    ELSIF p_camera_code = 'B' THEN
        -- Camera B: Crossover point (Level 1 to 2)
        -- Transfer from faculty to student section
        IF p_direction = 'in' THEN
            -- Student parking is increasing, faculty is decreasing
            IF v_student_occupied >= v_student_total THEN
                RAISE EXCEPTION 'Student parking is full (%)', v_student_total;
            END IF;
            -- Decrease faculty
            UPDATE floor_status 
            SET free_spots = LEAST(free_spots + 1, v_faculty_total), last_updated = NOW()
            WHERE floor_id = v_faculty_floor_id AND vehicle_type = 'car'
            AND free_spots < v_faculty_total;
            -- Increase student (update first floor with capacity)
            UPDATE floor_status 
            SET free_spots = free_spots - 1, last_updated = NOW()
            WHERE floor_id = v_student_floor_ids[1] AND vehicle_type = 'car'
            AND free_spots > 0;
        ELSIF p_direction = 'out' THEN
            -- Going from student back to faculty
            -- Decrease student
            UPDATE floor_status 
            SET free_spots = LEAST(free_spots + 1, v_student_total), last_updated = NOW()
            WHERE floor_id = v_student_floor_ids[1] AND vehicle_type = 'car'
            AND free_spots < v_student_total;
            -- Increase faculty
            UPDATE floor_status 
            SET free_spots = GREATEST(free_spots - 1, 0), last_updated = NOW()
            WHERE floor_id = v_faculty_floor_id AND vehicle_type = 'car'
            AND free_spots > 0;
        END IF;
        
    ELSIF p_camera_code = 'C' THEN
        -- Camera C: Level 2 entrance (Student section)
        IF p_direction = 'in' THEN
            IF v_student_occupied >= v_student_total THEN
                RAISE EXCEPTION 'Student parking is full (%)', v_student_total;
            END IF;
            UPDATE floor_status 
            SET free_spots = free_spots - 1, last_updated = NOW()
            WHERE floor_id = v_student_floor_ids[1] AND vehicle_type = 'car'
            AND free_spots > 0;
        ELSIF p_direction = 'out' THEN
            UPDATE floor_status 
            SET free_spots = LEAST(free_spots + 1, v_student_total), last_updated = NOW()
            WHERE floor_id = v_student_floor_ids[1] AND vehicle_type = 'car'
            AND free_spots < v_student_total;
        END IF;
    END IF;
    
    -- Log camera event
    INSERT INTO camera_events (camera_code, direction, count)
    VALUES (p_camera_code, p_direction, 
        CASE 
            WHEN p_camera_code = 'A' AND p_direction = 'in' THEN v_faculty_occupied + 1
            WHEN p_camera_code = 'B' AND p_direction = 'in' THEN v_student_occupied + 1
            WHEN p_camera_code = 'C' AND p_direction = 'in' THEN v_student_occupied + 1
            ELSE 0
        END
    );
    
    -- Get updated counts
    SELECT COALESCE(SUM(total_spots - free_spots), 0) INTO v_faculty_occupied
    FROM floor_status WHERE floor_id = v_faculty_floor_id;
    
    SELECT COALESCE(SUM(total_spots - free_spots), 0) INTO v_student_occupied
    FROM floor_status WHERE floor_id = ANY(v_student_floor_ids);
    
    -- Return result
    v_result := jsonb_build_object(
        'success', true,
        'camera', p_camera_code,
        'direction', p_direction,
        'faculty_occupied', v_faculty_occupied,
        'faculty_free', v_faculty_total - v_faculty_occupied,
        'student_occupied', v_student_occupied,
        'student_free', v_student_total - v_student_occupied
    );
    
    RETURN v_result;
END;
$$;

COMMIT;

-- ============================================================
-- USEFUL VIEWS FOR REPORTING
-- ============================================================

-- Garage summary with totals
CREATE OR REPLACE VIEW vw_garage_summary AS
SELECT 
    g.garage_id,
    g.name as garage_name,
    COUNT(DISTINCT f.floor_id) as total_floors,
    fs.vehicle_type,
    SUM(fs.total_spots) as total_spots,
    SUM(fs.free_spots) as total_free_spots,
    SUM(fs.total_spots - fs.free_spots) as total_occupied,
    ROUND(100.0 * SUM(fs.free_spots) / NULLIF(SUM(fs.total_spots), 0), 1) as availability_percent,
    MAX(fs.last_updated) as last_updated
FROM garages g
JOIN floors f ON f.garage_id = g.garage_id
JOIN floor_status fs ON fs.floor_id = f.floor_id
GROUP BY g.garage_id, g.name, fs.vehicle_type
ORDER BY g.garage_id, fs.vehicle_type;

-- Fields Parking specific summary
CREATE OR REPLACE VIEW vw_fields_parking_summary AS
SELECT 
    f.floor_number,
    f.floor_name,
    CASE 
        WHEN f.floor_number = 1 THEN 'Faculty'
        ELSE 'Student'
    END as section_type,
    fs.total_spots,
    fs.free_spots,
    (fs.total_spots - fs.free_spots) as occupied_spots,
    ROUND(100.0 * fs.free_spots / NULLIF(fs.total_spots, 0), 1) as availability_percent
FROM floors f
JOIN garages g ON g.garage_id = f.garage_id
JOIN floor_status fs ON fs.floor_id = f.floor_id
WHERE g.name = 'Fields Parking'
ORDER BY f.floor_number;

-- Overall occupancy view for Fields Parking
CREATE OR REPLACE VIEW vw_fields_current_occupancy AS
SELECT 
    COALESCE(SUM(CASE WHEN f.floor_number = 1 THEN (fs.total_spots - fs.free_spots) ELSE 0 END), 0) as faculty_occupied,
    COALESCE(SUM(CASE WHEN f.floor_number = 1 THEN fs.free_spots ELSE 0 END), 0) as faculty_free,
    97 as faculty_total,
    COALESCE(SUM(CASE WHEN f.floor_number IN (2,3,4) THEN (fs.total_spots - fs.free_spots) ELSE 0 END), 0) as student_occupied,
    COALESCE(SUM(CASE WHEN f.floor_number IN (2,3,4) THEN fs.free_spots ELSE 0 END), 0) as student_free,
    299 as student_total,
    COALESCE(SUM(fs.total_spots - fs.free_spots), 0) as total_occupied,
    COALESCE(SUM(fs.free_spots), 0) as total_free,
    396 as total_spots
FROM floors f
JOIN garages g ON g.garage_id = f.garage_id
JOIN floor_status fs ON fs.floor_id = f.floor_id
WHERE g.name = 'Fields Parking';

-- Recent camera activity
CREATE OR REPLACE VIEW vw_recent_camera_activity AS
SELECT 
    camera_code,
    direction,
    count,
    timestamp,
    recorded_at
FROM camera_events
ORDER BY recorded_at DESC
LIMIT 100;

-- Floor occupancy details view
CREATE OR REPLACE VIEW vw_floor_occupancy AS
SELECT 
    f.floor_id,
    f.floor_number,
    f.floor_name,
    g.name as garage_name,
    fs.vehicle_type,
    fs.total_spots,
    fs.free_spots,
    (fs.total_spots - fs.free_spots) as occupied_spots,
    ROUND(100.0 * fs.free_spots / NULLIF(fs.total_spots, 0), 1) as availability_percent,
    fs.last_updated
FROM floors f
JOIN garages g ON g.garage_id = f.garage_id
JOIN floor_status fs ON fs.floor_id = f.floor_id
ORDER BY g.name, f.floor_number, fs.vehicle_type;

-- ============================================================
-- HELPER FUNCTIONS
-- ============================================================

-- Function to update occupancy based on vehicle count (for other garages)
CREATE OR REPLACE FUNCTION update_floor_occupancy_from_counter()
RETURNS TRIGGER AS $$
BEGIN
    -- This function can be used to link vehicle counts to floor occupancy
    -- Example: when a vehicle enters at entrance_1, update Floor 1 occupancy
    -- You would customize this based on your mapping logic
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to log floor status changes to history
CREATE OR REPLACE FUNCTION log_floor_status_change()
RETURNS TRIGGER AS $$
BEGIN
    -- Only log if free_spots actually changed
    IF (OLD.free_spots IS DISTINCT FROM NEW.free_spots) OR (OLD.total_spots IS DISTINCT FROM NEW.total_spots) THEN
        INSERT INTO floor_history (floor_id, vehicle_type, total_spots, free_spots, recorded_at)
        VALUES (NEW.floor_id, NEW.vehicle_type, NEW.total_spots, NEW.free_spots, NOW());
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- TRIGGERS
-- ============================================================

-- Trigger to auto-log floor status changes to history
CREATE TRIGGER IF NOT EXISTS trigger_log_floor_status_change
AFTER UPDATE ON floor_status
FOR EACH ROW
WHEN (OLD.free_spots IS DISTINCT FROM NEW.free_spots OR OLD.total_spots IS DISTINCT FROM NEW.total_spots)
EXECUTE FUNCTION log_floor_status_change();

COMMIT;

-- ============================================================
-- VERIFICATION QUERIES
-- ============================================================

-- Verify garage setup
SELECT 
    g.name as garage,
    COUNT(DISTINCT f.floor_id) as floors,
    COUNT(DISTINCT fs.floor_id) as floors_with_status
FROM garages g
LEFT JOIN floors f ON f.garage_id = g.garage_id
LEFT JOIN floor_status fs ON fs.floor_id = f.floor_id
GROUP BY g.garage_id, g.name
ORDER BY g.name;

-- Verify Fields Parking setup
SELECT 
    g.name as garage,
    f.floor_number,
    f.floor_name,
    fs.vehicle_type,
    fs.total_spots,
    fs.free_spots
FROM garages g
JOIN floors f ON f.garage_id = g.garage_id
JOIN floor_status fs ON fs.floor_id = f.floor_id
WHERE g.name = 'Fields Parking'
ORDER BY f.floor_number;

-- Show cameras
SELECT camera_code, camera_name, location_description
FROM cameras
ORDER BY camera_code;

-- Show Fields Parking current occupancy
SELECT * FROM vw_fields_current_occupancy;

-- Show garage summary
SELECT * FROM vw_garage_summary ORDER BY garage_name, vehicle_type;

COMMIT;

-- ============================================================
-- EXAMPLE USAGE
-- ============================================================

/*
-- Test camera events for Fields Parking
SELECT process_camera_event('A', 'in');    -- Car enters Faculty section
SELECT process_camera_event('B', 'in');    -- Transfer to Student section
SELECT process_camera_event('C', 'in');    -- Car enters Student section directly
SELECT process_camera_event('A', 'out');   -- Car leaves Faculty section

-- View current state
SELECT * FROM vw_fields_current_occupancy;
SELECT * FROM vw_fields_parking_summary;

-- Update other garage floor occupancy manually
UPDATE floor_status 
SET free_spots = 45, 
    last_updated = NOW()
WHERE floor_id = 5 AND vehicle_type = 'car';

-- View garage summary
SELECT * FROM vw_garage_summary WHERE garage_name = 'Hutson Marsh Griffith Parking';

-- View recent camera activity
SELECT * FROM vw_recent_camera_activity LIMIT 10;
*/

COMMIT;

-- ============================================================
-- END OF SCRIPT
-- ============================================================
