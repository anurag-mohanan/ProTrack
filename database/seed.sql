-- ProTrack seed data
-- Safe to re-run on an existing database (uses ON CONFLICT).

-- Roles
INSERT INTO roles (name, description) VALUES
    ('Admin',           'Full system administration'),
    ('Project Manager', 'Manage projects, resources, and approvals'),
    ('Designer',        'Design work and time logging')
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

-- Milestone template
INSERT INTO milestone_templates (stream_id, name, description)
SELECT s.id, 'Mold Design', 'Standard milestone template for mold design projects'
FROM streams s
WHERE s.name = 'Mold Design'
ON CONFLICT (stream_id, name) DO UPDATE
    SET description = EXCLUDED.description,
        updated_at  = now();

-- Milestone template items
INSERT INTO milestone_template_items (template_id, name, description, sort_order)
SELECT mt.id, i.name, i.description, i.sort_order
FROM milestone_templates mt
CROSS JOIN (
    VALUES
        ('Feasibility',        'Assess design feasibility',        1),
        ('Mold Design',        'Detailed mold design',             2),
        ('Design Review',      'Review design with stakeholders',  3),
        ('BOM Creation',       'Create bill of materials',         4),
        ('Engineering Change', 'Implement engineering changes',    5)
) AS i(name, description, sort_order)
WHERE mt.name = 'Mold Design'
ON CONFLICT (template_id, name) DO UPDATE
    SET description = EXCLUDED.description,
        sort_order  = EXCLUDED.sort_order,
        updated_at  = now();
