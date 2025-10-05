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
INSERT INTO floors (garage_id, floor_number)
SELECT g.garage_id, fnum
FROM garages g
JOIN (VALUES
    (1, 'Green'),
    (2, 'Purple'),
    (3, 'Blue'),
    (4, 'Gold')
) AS f(fnum, fname) ON TRUE
WHERE g.name = 'Highrise Parking'
ON CONFLICT DO NOTHING;

-- Optional: add a column for named floors if you want both number + name
ALTER TABLE floors ADD COLUMN IF NOT EXISTS floor_name VARCHAR(50);

-- Update Highrise floors with names
UPDATE floors f
SET floor_name = fname
FROM garages g
JOIN (VALUES
    (1, 'Green'),
    (2, 'Purple'),
    (3, 'Blue'),
    (4, 'Gold')
) AS mapping(fnum, fname)
  ON f.floor_number = mapping.fnum
WHERE f.garage_id = g.garage_id
  AND g.name = 'Highrise Parking';
