"""R10 M1b — natural-key unique constraints that must include tenant_id.

Child uniqueness on UUID FKs (e.g. timesheets user_id+week_start) is omitted:
parent PKs are globally unique UUIDs, so those composites already isolate tenants.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TenantUniqueSpec:
    """Replace a global unique with a tenant-scoped unique index/constraint."""

    table: str
    columns: tuple[str, ...]  # includes tenant_id as first column
    name: str
    # Pre-M1b column set (without tenant_id) used to find/drop legacy uniques.
    legacy_columns: tuple[str, ...]


# Natural business keys + singleton settings (one row per tenant).
TENANT_UNIQUE_SPECS: tuple[TenantUniqueSpec, ...] = (
    # Identity / org / delivery
    TenantUniqueSpec("users", ("tenant_id", "email"), "uq_users_tenant_email", ("email",)),
    TenantUniqueSpec("roles", ("tenant_id", "name"), "uq_roles_tenant_name", ("name",)),
    TenantUniqueSpec(
        "operational_role_types",
        ("tenant_id", "code"),
        "uq_operational_role_types_tenant_code",
        ("code",),
    ),
    TenantUniqueSpec(
        "working_models", ("tenant_id", "code"), "uq_working_models_tenant_code", ("code",)
    ),
    TenantUniqueSpec("streams", ("tenant_id", "name"), "uq_streams_tenant_name", ("name",)),
    TenantUniqueSpec(
        "org_departments",
        ("tenant_id", "code"),
        "uq_org_departments_tenant_code",
        ("code",),
    ),
    TenantUniqueSpec(
        "org_departments",
        ("tenant_id", "name"),
        "uq_org_departments_tenant_name",
        ("name",),
    ),
    TenantUniqueSpec("teams", ("tenant_id", "name"), "uq_teams_tenant_name", ("name",)),
    TenantUniqueSpec(
        "customers", ("tenant_id", "code"), "uq_customers_tenant_code", ("code",)
    ),
    TenantUniqueSpec(
        "project_types", ("tenant_id", "name"), "uq_project_types_tenant_name", ("name",)
    ),
    TenantUniqueSpec(
        "projects",
        ("tenant_id", "tool_number"),
        "uq_projects_tenant_tool_number",
        ("tool_number",),
    ),
    TenantUniqueSpec(
        "projects", ("tenant_id", "code"), "uq_projects_tenant_code", ("code",)
    ),
    TenantUniqueSpec(
        "non_productive_codes",
        ("tenant_id", "code"),
        "uq_non_productive_codes_tenant_code",
        ("code",),
    ),
    TenantUniqueSpec(
        "tickets",
        ("tenant_id", "ticket_number"),
        "uq_tickets_tenant_ticket_number",
        ("ticket_number",),
    ),
    TenantUniqueSpec(
        "ticket_category_routes",
        ("tenant_id", "category"),
        "uq_ticket_category_routes_tenant_category",
        ("category",),
    ),
    TenantUniqueSpec(
        "onboarding_checklist_templates",
        ("tenant_id", "code"),
        "uq_onboarding_checklist_templates_tenant_code",
        ("code",),
    ),
    TenantUniqueSpec(
        "performance_review_templates",
        ("tenant_id", "code", "version"),
        "uq_review_template_tenant_code_version",
        ("code", "version"),
    ),
    # Foundation lookups / settings
    TenantUniqueSpec(
        "departments", ("tenant_id", "name"), "uq_departments_tenant_name", ("name",)
    ),
    TenantUniqueSpec(
        "departments", ("tenant_id", "code"), "uq_departments_tenant_code", ("code",)
    ),
    TenantUniqueSpec(
        "contact_types", ("tenant_id", "name"), "uq_contact_types_tenant_name", ("name",)
    ),
    TenantUniqueSpec(
        "engineering_disciplines",
        ("tenant_id", "name"),
        "uq_engineering_disciplines_tenant_name",
        ("name",),
    ),
    TenantUniqueSpec("skills", ("tenant_id", "name"), "uq_skills_tenant_name", ("name",)),
    TenantUniqueSpec(
        "email_templates",
        ("tenant_id", "slug"),
        "uq_email_templates_tenant_slug",
        ("slug",),
    ),
    TenantUniqueSpec(
        "company_settings", ("tenant_id",), "uq_company_settings_tenant", ("tenant_id",)
    ),
    TenantUniqueSpec(
        "branding_settings", ("tenant_id",), "uq_branding_settings_tenant", ("tenant_id",)
    ),
    TenantUniqueSpec(
        "file_path_settings",
        ("tenant_id",),
        "uq_file_path_settings_tenant",
        ("tenant_id",),
    ),
    TenantUniqueSpec(
        "notification_settings",
        ("tenant_id",),
        "uq_notification_settings_tenant",
        ("tenant_id",),
    ),
    TenantUniqueSpec(
        "email_settings", ("tenant_id",), "uq_email_settings_tenant", ("tenant_id",)
    ),
    TenantUniqueSpec(
        "security_policy_settings",
        ("tenant_id",),
        "uq_security_policy_settings_tenant",
        ("tenant_id",),
    ),
    # Finance / training / enterprise
    TenantUniqueSpec(
        "cost_centres", ("tenant_id", "code"), "uq_cost_centres_tenant_code", ("code",)
    ),
    TenantUniqueSpec(
        "company_finance_settings",
        ("tenant_id",),
        "uq_company_finance_settings_tenant",
        ("tenant_id",),
    ),
    TenantUniqueSpec(
        "fx_rates",
        ("tenant_id", "from_currency", "to_currency", "effective_date"),
        "uq_fx_rates_tenant_pair_date",
        ("from_currency", "to_currency", "effective_date"),
    ),
    TenantUniqueSpec(
        "training_courses",
        ("tenant_id", "code"),
        "uq_training_courses_tenant_code",
        ("code",),
    ),
    TenantUniqueSpec(
        "legal_entities",
        ("tenant_id", "code"),
        "uq_legal_entities_tenant_code",
        ("code",),
    ),
)
