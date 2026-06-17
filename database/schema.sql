-- ProTrack PostgreSQL Schema
-- Generated from docs/01_Project_Vision.md, docs/02_Requirements.md, docs/03_Database_Design.md

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------------
-- Enumerations
-- ---------------------------------------------------------------------------

CREATE TYPE project_status AS ENUM (
    'draft',
    'active',
    'on_hold',
    'completed',
    'cancelled'
);

CREATE TYPE milestone_status AS ENUM (
    'pending',
    'in_progress',
    'completed',
    'delayed'
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
-- Projects & Resource Planning
-- ---------------------------------------------------------------------------

CREATE TABLE projects (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id       UUID            NOT NULL REFERENCES customers (id),
    stream_id         UUID            NOT NULL REFERENCES streams (id),
    created_by        UUID            NOT NULL REFERENCES users (id),
    name              VARCHAR(200)    NOT NULL,
    code              VARCHAR(50)     NOT NULL UNIQUE,
    description       TEXT,
    status            project_status  NOT NULL DEFAULT 'draft',
    planned_start     DATE,
    planned_end       DATE,
    actual_start      DATE,
    actual_end        DATE,
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE TABLE project_members (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id         UUID         NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    user_id            UUID         NOT NULL REFERENCES users (id),
    role_on_project    VARCHAR(50)  NOT NULL DEFAULT 'member',
    allocation_percent SMALLINT     NOT NULL DEFAULT 100
        CHECK (allocation_percent BETWEEN 0 AND 100),
    start_date         DATE,
    end_date           DATE,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (project_id, user_id)
);

-- ---------------------------------------------------------------------------
-- Milestones
-- ---------------------------------------------------------------------------

CREATE TABLE milestones (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id   UUID              NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    name         VARCHAR(200)      NOT NULL,
    description  TEXT,
    status       milestone_status  NOT NULL DEFAULT 'pending',
    due_date     DATE,
    completed_at TIMESTAMPTZ,
    sort_order   INTEGER           NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ       NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ       NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Milestone Templates
-- ---------------------------------------------------------------------------

CREATE TABLE milestone_templates (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stream_id   UUID         NOT NULL REFERENCES streams (id),
    name        VARCHAR(200) NOT NULL,
    description TEXT,
    is_active   BOOLEAN      NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (stream_id, name)
);

CREATE TABLE milestone_template_items (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID         NOT NULL REFERENCES milestone_templates (id) ON DELETE CASCADE,
    name        VARCHAR(200) NOT NULL,
    description TEXT,
    sort_order  INTEGER      NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (template_id, name)
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

CREATE INDEX idx_users_role_id            ON users (role_id);
CREATE INDEX idx_contacts_customer_id     ON contacts (customer_id);
CREATE INDEX idx_task_types_stream_id     ON task_types (stream_id);
CREATE INDEX idx_projects_customer_id     ON projects (customer_id);
CREATE INDEX idx_projects_stream_id       ON projects (stream_id);
CREATE INDEX idx_projects_status          ON projects (status);
CREATE INDEX idx_project_members_user_id  ON project_members (user_id);
CREATE INDEX idx_milestones_project_id           ON milestones (project_id);
CREATE INDEX idx_milestones_due_date             ON milestones (due_date);
CREATE INDEX idx_milestone_templates_stream_id   ON milestone_templates (stream_id);
CREATE INDEX idx_milestone_template_items_tpl_id ON milestone_template_items (template_id);
CREATE INDEX idx_timesheets_user_id       ON timesheets (user_id);
CREATE INDEX idx_timesheet_entries_sheet  ON timesheet_entries (timesheet_id);
CREATE INDEX idx_timesheet_entries_project ON timesheet_entries (project_id);
CREATE INDEX idx_timesheet_entries_date   ON timesheet_entries (entry_date);

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
    BEFORE UPDATE ON roles FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

CREATE TRIGGER trg_streams_updated_at
    BEFORE UPDATE ON streams FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

CREATE TRIGGER trg_customers_updated_at
    BEFORE UPDATE ON customers FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

CREATE TRIGGER trg_contacts_updated_at
    BEFORE UPDATE ON contacts FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

CREATE TRIGGER trg_task_types_updated_at
    BEFORE UPDATE ON task_types FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

CREATE TRIGGER trg_projects_updated_at
    BEFORE UPDATE ON projects FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

CREATE TRIGGER trg_project_members_updated_at
    BEFORE UPDATE ON project_members FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

CREATE TRIGGER trg_milestones_updated_at
    BEFORE UPDATE ON milestones FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

CREATE TRIGGER trg_milestone_templates_updated_at
    BEFORE UPDATE ON milestone_templates FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

CREATE TRIGGER trg_milestone_template_items_updated_at
    BEFORE UPDATE ON milestone_template_items FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

CREATE TRIGGER trg_timesheets_updated_at
    BEFORE UPDATE ON timesheets FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

CREATE TRIGGER trg_timesheet_entries_updated_at
    BEFORE UPDATE ON timesheet_entries FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

-- ---------------------------------------------------------------------------
-- Seed data
-- ---------------------------------------------------------------------------

INSERT INTO roles (name, description) VALUES
    ('Admin',            'Full system administration'),
    ('Project Manager',  'Manage projects, resources, and approvals'),
    ('Designer',         'Design work and time logging');

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

INSERT INTO milestone_templates (stream_id, name, description)
SELECT s.id, 'Mold Design', 'Standard milestone template for mold design projects'
FROM streams s
WHERE s.name = 'Mold Design';

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
WHERE mt.name = 'Mold Design';
