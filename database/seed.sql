-- ProTrack seed data (MVP)
-- Safe to re-run on an existing database (uses ON CONFLICT).

-- Roles
INSERT INTO roles (name, description) VALUES
    ('Admin',           'Full system administration'),
    ('Project Manager', 'Manage projects and approvals'),
    ('Design Leader',   'Lead design projects'),
    ('Senior Designer', 'Senior design work with project edit on assignments'),
    ('Designer',        'Design work and time logging'),
    ('Junior Designer', 'Entry-level design work and time logging'),
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

-- Design team users (default password: Password@123)
INSERT INTO users (role_id, email, password_hash, first_name, last_name)
SELECT r.id, u.email, crypt('Password@123', gen_salt('bf')), u.first_name, u.last_name
FROM roles r
JOIN (
    VALUES
        ('Senior Designer', 'sandrarag@prosohm.com', 'Sandrarag', 'Sandrarag'),
        ('Designer',        'logesh@prosohm.com',    'Logesh', 'Logesh'),
        ('Junior Designer', 'akhil@prosohm.com',     'Akhil', 'Akhil'),
        ('Senior Designer', 'umesh@prosohm.com',     'Umesh', 'Umesh'),
        ('Junior Designer', 'abhay@prosohm.com',     'Abhay', 'Abhay'),
        ('Designer',        'sarath@prosohm.com',    'Sarath', 'Sarath'),
        ('Senior Designer', 'ramkumar@prosohm.com',  'Ramkumar', 'Ramkumar')
) AS u(role_name, email, first_name, last_name)
    ON r.name = u.role_name
ON CONFLICT (email) DO UPDATE
    SET role_id = EXCLUDED.role_id,
        first_name = EXCLUDED.first_name,
        last_name = EXCLUDED.last_name,
        updated_at = now();
