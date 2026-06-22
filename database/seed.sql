-- ProTrack seed data (MVP)
-- Safe to re-run on an existing database (uses ON CONFLICT).

-- Roles
INSERT INTO roles (name, description) VALUES
    ('Admin',           'Full system administration'),
    ('Project Manager', 'Manage projects and approvals'),
    ('Design Leader',   'Lead design projects'),
    ('Designer',        'Design work and time logging'),
    ('Surfacer',        'Surface modeling work')
ON CONFLICT (name) DO UPDATE
    SET description = EXCLUDED.description,
        updated_at  = now();

-- Business streams
INSERT INTO streams (name, description) VALUES
    ('Mold Design', 'Mold design projects')
ON CONFLICT (name) DO UPDATE
    SET description = EXCLUDED.description,
        updated_at  = now();

-- Task types (Mold Design stream)
INSERT INTO task_types (stream_id, name, description)
SELECT s.id, t.name, t.description
FROM streams s
CROSS JOIN (
    VALUES
        ('Mold Design',        'Core mold design work'),
        ('Engineering Change', 'Engineering change orders'),
        ('Feasibility',        'Feasibility assessment'),
        ('Design Review',      'Design review activities'),
        ('BOM Creation',       'Bill of materials creation')
) AS t(name, description)
WHERE s.name = 'Mold Design'
ON CONFLICT (stream_id, name) DO UPDATE
    SET description = EXCLUDED.description,
        updated_at  = now();
