-- Insert garages
INSERT INTO garages (name) VALUES
    ('Fields Parking'),
    ('Hutson Marsh Griffith Parking'),
    ('Highrise Parking')
ON CONFLICT (name) DO NOTHING;

-- Insert floors for Fields Parking (3 floors)
INSERT INTO floors (garage_id, floor_number)
SELECT g.garage_id, fnum
FROM garages g
CROSS JOIN (VALUES (1), (2), (3)) AS f(fnum)
WHERE g.name = 'Fields Parking'
ON CONFLICT DO NOTHING;

-- Insert floors for Hutson Marsh Griffith Parking (4 floors)
INSERT INTO floors (garage_id, floor_number)
SELECT g.garage_id, fnum
FROM garages g
CROSS JOIN (VALUES (1), (2), (3), (4)) AS f(fnum)
WHERE g.name = 'Hutson Marsh Griffith Parking'
ON CONFLICT DO NOTHING;

-- Insert named floors for Highrise Parking
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

-- Seed floor_status with base values (0 total, 0 free) for all floors
INSERT INTO floor_status (floor_id, vehicle_type, total_spots, free_spots)
SELECT f.floor_id, v.vehicle_type, 0, 0
FROM floors f
CROSS JOIN (VALUES ('car'), ('motorcycle')) AS v(vehicle_type)
ON CONFLICT DO NOTHING;
