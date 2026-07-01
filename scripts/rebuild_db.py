"""Drop, recreate, and seed the local SQLite database for MVP development."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.models  # noqa: F401 — register models
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.db.design_team import DESIGN_TEAM, build_design_team_users
from app.models.models import Contact, Customer, Role, Stream, TaskType, User

IDS = {
    "role_admin": uuid.UUID("11111111-1111-1111-1111-111111111111"),
    "role_pm": uuid.UUID("22222222-2222-2222-2222-222222222222"),
    "role_design_leader": uuid.UUID("d7a67e79-dffa-42f8-bea4-f646f73fd3fd"),
    "role_designer": uuid.UUID("85e2fc34-f0f3-468f-9390-9d8efb1c2a4f"),
    "role_senior_designer": uuid.UUID("e5e5e5e5-e5e5-4e5e-8e5e-e5e5e5e5e5e1"),
    "role_junior_designer": uuid.UUID("f6f6f6f6-f6f6-4f6f-8f6f-f6f6f6f6f6f1"),
    "role_surfacer": uuid.UUID("04582a31-25bf-4709-ac44-e6e05aae8406"),
    "user_admin": uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
    "user_pm": uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
    "user_anurag": uuid.UUID("7cf429ba-ca31-4752-9a03-afa3ba4700a3"),
    "user_binil": uuid.UUID("1bb6229f-dcff-419a-a8fa-2b8a7fd15043"),
    "user_ranjith": uuid.UUID("731ddf9e-d2d9-450b-a675-cb2ca8a021e3"),
    "stream_mold_design": uuid.UUID("a4b9ba7c-4ff4-4a2c-8dc7-823a7cfacb55"),
    "customer_ti": uuid.UUID("3946c135-d515-4bbd-affb-00b5c1893832"),
    "contact_steve": uuid.UUID("b5301223-164f-4035-8017-252ff0452fa6"),
}

TASK_TYPES = (
    ("Mold Design", "Core mold design work"),
    ("Engineering Change", "Engineering change orders"),
    ("Feasibility", "Feasibility assessment"),
    ("Design Review", "Design review activities"),
    ("BOM Creation", "Bill of materials creation"),
)

DEFAULT_PASSWORD = "Password@123"


def rebuild() -> None:
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)

    print("Creating tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        roles = [
            Role(id=IDS["role_admin"], name="Admin", description="Full system administration"),
            Role(
                id=IDS["role_pm"],
                name="Engineering Manager",
                description="Manage projects and engineering operations",
            ),
            Role(
                id=IDS["role_design_leader"],
                name="Design Leader",
                description="Lead design projects",
            ),
            Role(
                id=IDS["role_designer"],
                name="Designer",
                description="Design work and time logging",
            ),
            Role(
                id=IDS["role_senior_designer"],
                name="Senior Designer",
                description="Senior design work with project edit on assignments",
            ),
            Role(
                id=IDS["role_junior_designer"],
                name="Junior Designer",
                description="Entry-level design work and time logging",
            ),
            Role(
                id=IDS["role_surfacer"],
                name="Surfacer",
                description="Surface modeling work",
            ),
            Role(
                name="Read Only",
                description="View-only access to projects, reports, and planning",
            ),
        ]
        db.add_all(roles)

        stream = Stream(
            id=IDS["stream_mold_design"],
            name="Mold Design",
            description="Mold design projects",
            is_active=True,
        )
        db.add(stream)

        for name, description in TASK_TYPES:
            db.add(
                TaskType(
                    stream_id=stream.id,
                    name=name,
                    description=description,
                    is_billable=True,
                    is_active=True,
                )
            )

        customer = Customer(
            id=IDS["customer_ti"],
            name="TI Automotive",
            code="TI",
            address=None,
            is_active=True,
        )
        db.add(customer)

        db.add(
            Contact(
                id=IDS["contact_steve"],
                customer_id=customer.id,
                first_name="Steve",
                last_name="Johnson",
                email="steve.johnson@ti.com",
                phone=None,
                job_title="Engineering Manager",
                is_primary=True,
            )
        )

        password_hash = hash_password(DEFAULT_PASSWORD)
        role_by_name = {role.name: role.id for role in roles}
        db.add_all(
            [
                User(
                    id=IDS["user_admin"],
                    role_id=IDS["role_admin"],
                    email="admin@prosohm.com",
                    password_hash=password_hash,
                    first_name="System",
                    last_name="Admin",
                    is_active=True,
                ),
                User(
                    id=IDS["user_pm"],
                    role_id=IDS["role_pm"],
                    email="pm@prosohm.com",
                    password_hash=password_hash,
                    first_name="Project",
                    last_name="Manager",
                    is_active=True,
                ),
                User(
                    id=IDS["user_anurag"],
                    role_id=IDS["role_design_leader"],
                    email="anurag@prosohm.com",
                    password_hash=password_hash,
                    first_name="Anurag",
                    last_name="Mohanan",
                    is_active=True,
                ),
                User(
                    id=IDS["user_binil"],
                    role_id=IDS["role_designer"],
                    email="binil@prosohm.com",
                    password_hash=password_hash,
                    first_name="Binil",
                    last_name="JR",
                    is_active=True,
                ),
                *build_design_team_users(password_hash, role_by_name),
                User(
                    id=IDS["user_ranjith"],
                    role_id=IDS["role_surfacer"],
                    email="ranjith@prosohm.com",
                    password_hash=password_hash,
                    first_name="Ranjith",
                    last_name="K",
                    is_active=True,
                ),
            ]
        )

        db.commit()
        print("Seed complete.")
        print(f"  Default password: {DEFAULT_PASSWORD}")
        print("  Accounts:")
        print("    admin@prosohm.com (Admin)")
        print("    pm@prosohm.com (Project Manager)")
        print("    anurag@prosohm.com (Design Leader)")
        print("    binil@prosohm.com (Designer)")
        for member in DESIGN_TEAM:
            print(f"    {member.email} ({member.role_name})")
        print("    ranjith@prosohm.com (Surfacer)")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    rebuild()
