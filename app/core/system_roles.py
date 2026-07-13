"""Roles seeded by the system that must not be deleted."""

SYSTEM_ROLE_NAMES = frozenset(
    {
        "Admin",
        "Engineering Manager",
        "Design Leader",
        "Senior Designer",
        "Designer",
        "Junior Designer",
        "Surfacer",
        "Read Only",
        "Planning Board",
        # Legacy name kept for existing databases; normalized to Engineering Manager.
        "Project Manager",
    }
)
