-- ProTrack PostgreSQL Schema (MVP)
-- Aligned with app/models and docs/08_MVP_Scope.md

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------------
-- Enumerations
-- ---------------------------------------------------------------------------

CREATE TYPE project_health AS ENUM (
    'green',
    'yellow',
    'red'
);

CREATE TYPE project_status AS ENUM (
    'not_started',
    'in_progress',
    'waiting_for_customer',
    'completed'
);

CREATE TYPE milestone_status AS ENUM (
    'not_started',
    'in_progress',
    'completed',
    'not_applicable'
);

CREATE TYPE timesheet_status AS ENUM (
    'draft',
    'submitted',
    'approved',
    'rejected'
);

-- ---------------------------------------------------------------------------
-- Roles & Users
-- ---------------------------------------------------------------------------

CREATE TABLE roles (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(50)  NOT NULL UNIQUE,
    description TEXT,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id       UUID         NOT NULL REFERENCES roles (id),
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    first_name    VARCHAR(100) NOT NULL,
    last_name     VARCHAR(100) NOT NULL,
    is_active     BOOLEAN      NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Business Streams
-- ---------------------------------------------------------------------------

CREATE TABLE streams (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    is_active   BOOLEAN      NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Customers & Contacts
-- ---------------------------------------------------------------------------

CREATE TABLE customers (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(200) NOT NULL,
    code        VARCHAR(20)  UNIQUE,
    address     TEXT,
    is_active   BOOLEAN      NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE contacts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID         NOT NULL REFERENCES customers (id) ON DELETE CASCADE,
    first_name  VARCHAR(100) NOT NULL,
    last_name   VARCHAR(100) NOT NULL,
    email       VARCHAR(255),
    phone       VARCHAR(50),
    job_title   VARCHAR(100),
    is_primary  BOOLEAN      NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Task Types (per business stream)
-- ---------------------------------------------------------------------------

CREATE TABLE task_types (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stream_id   UUID         NOT NULL REFERENCES streams (id),
    name        VARCHAR(100) NOT NULL,
    description TEXT,
    is_billable BOOLEAN      NOT NULL DEFAULT true,
    is_active   BOOLEAN      NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (stream_id, name)
);

-- ---------------------------------------------------------------------------
-- Projects
-- ---------------------------------------------------------------------------

CREATE TABLE projects (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_number         VARCHAR(50)     NOT NULL,
    part_description    VARCHAR(255)    NOT NULL,
    customer_id         UUID            NOT NULL REFERENCES customers (id),
    customer_contact_id UUID            NOT NULL REFERENCES contacts (id),
    design_leader_id    UUID            NOT NULL REFERENCES users (id),
    designer_id         UUID            REFERENCES users (id),
    surfacer_id         UUID            REFERENCES users (id),
    stream_id           UUID            NOT NULL REFERENCES streams (id),
    code                VARCHAR(50)     NOT NULL UNIQUE,
    quoted_hours        NUMERIC(8, 2)   NOT NULL CHECK (quoted_hours > 0),
    actual_hours        NUMERIC(8, 2)   NOT NULL DEFAULT 0,
    due_date            DATE            NOT NULL,
    status              project_status  NOT NULL DEFAULT 'not_started',
    health              project_health  NOT NULL DEFAULT 'green',
    notes               TEXT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Milestones
-- ---------------------------------------------------------------------------

CREATE TABLE milestones (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id   UUID              NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    name         VARCHAR(200)      NOT NULL,
    description  TEXT,
    status       milestone_status  NOT NULL DEFAULT 'not_started',
    due_date     DATE,
    completed_at TIMESTAMPTZ,
    sort_order   INTEGER           NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ       NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ       NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Timesheets
-- ---------------------------------------------------------------------------

CREATE TABLE timesheets (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID              NOT NULL REFERENCES users (id),
    week_start   DATE              NOT NULL,
    status       timesheet_status  NOT NULL DEFAULT 'draft',
    submitted_at TIMESTAMPTZ,
    approved_by  UUID              REFERENCES users (id),
    approved_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ       NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ       NOT NULL DEFAULT now(),
    UNIQUE (user_id, week_start)
);

CREATE TABLE timesheet_entries (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timesheet_id  UUID           NOT NULL REFERENCES timesheets (id) ON DELETE CASCADE,
    project_id    UUID           NOT NULL REFERENCES projects (id),
    task_type_id  UUID           REFERENCES task_types (id),
    milestone_id  UUID           REFERENCES milestones (id),
    entry_date    DATE           NOT NULL,
    hours         NUMERIC(5, 2)  NOT NULL CHECK (hours > 0 AND hours <= 24),
    description   TEXT,
    created_at    TIMESTAMPTZ    NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ    NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

CREATE INDEX idx_users_role_id              ON users (role_id);
CREATE INDEX idx_contacts_customer_id       ON contacts (customer_id);
CREATE INDEX idx_task_types_stream_id       ON task_types (stream_id);
CREATE INDEX idx_projects_customer_id       ON projects (customer_id);
CREATE INDEX idx_projects_customer_contact_id ON projects (customer_contact_id);
CREATE INDEX idx_projects_stream_id         ON projects (stream_id);
CREATE INDEX idx_projects_design_leader_id  ON projects (design_leader_id);
CREATE INDEX idx_projects_designer_id       ON projects (designer_id);
CREATE INDEX idx_projects_surfacer_id       ON projects (surfacer_id);
CREATE INDEX idx_projects_status            ON projects (status);
CREATE INDEX idx_projects_due_date          ON projects (due_date);
CREATE INDEX idx_milestones_project_id      ON milestones (project_id);
CREATE INDEX idx_milestones_due_date        ON milestones (due_date);
CREATE INDEX idx_timesheets_user_id         ON timesheets (user_id);
CREATE INDEX idx_timesheet_entries_sheet    ON timesheet_entries (timesheet_id);
CREATE INDEX idx_timesheet_entries_project  ON timesheet_entries (project_id);
CREATE INDEX idx_timesheet_entries_date     ON timesheet_entries (entry_date);

-- ---------------------------------------------------------------------------
-- updated_at trigger
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_roles_updated_at
    BEFORE UPDATE ON roles FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_streams_updated_at
    BEFORE UPDATE ON streams FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_customers_updated_at
    BEFORE UPDATE ON customers FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_contacts_updated_at
    BEFORE UPDATE ON contacts FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_task_types_updated_at
    BEFORE UPDATE ON task_types FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_projects_updated_at
    BEFORE UPDATE ON projects FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_milestones_updated_at
    BEFORE UPDATE ON milestones FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_timesheets_updated_at
    BEFORE UPDATE ON timesheets FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_timesheet_entries_updated_at
    BEFORE UPDATE ON timesheet_entries FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- Seed data
-- ---------------------------------------------------------------------------

INSERT INTO roles (name, description) VALUES
    ('Admin',            'Full system administration'),
    ('Project Manager',  'Manage projects and approvals'),
    ('Design Leader',    'Lead design projects'),
    ('Senior Designer',  'Senior design work with project edit on assignments'),
    ('Designer',         'Design work and time logging'),
    ('Junior Designer',  'Entry-level design work and time logging'),
    ('Surfacer',         'Surface modeling work');

INSERT INTO streams (name, description) VALUES
    ('Mold Design', 'Mold design projects');

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
WHERE s.name = 'Mold Design';

-- Default password for all seed users: Password@123 (bcrypt via pgcrypto)
INSERT INTO users (role_id, email, password_hash, first_name, last_name)
SELECT r.id, u.email, crypt('Password@123', gen_salt('bf')), u.first_name, u.last_name
FROM roles r
JOIN (
    VALUES
        ('Admin',           'admin@prosohm.com',   'System', 'Admin'),
        ('Project Manager', 'pm@prosohm.com',      'Project', 'Manager'),
        ('Design Leader',   'anurag@prosohm.com',  'Anurag', 'Mohanan'),
        ('Senior Designer', 'senior@prosohm.com',  'Priya', 'Nair'),
        ('Designer',        'binil@prosohm.com',   'Binil', 'JR'),
        ('Junior Designer', 'junior@prosohm.com',  'Alex', 'Thomas'),
        ('Surfacer',        'ranjith@prosohm.com', 'Ranjith', 'K')
) AS u(role_name, email, first_name, last_name)
    ON r.name = u.role_name;
