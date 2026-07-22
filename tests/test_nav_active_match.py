"""Nav active-match helper parity (frontend/src/utils/navActive.ts)."""


def nav_item_needs_exact_match(path: str, sibling_paths: list[str]) -> bool:
    normalized = path.rstrip("/") or "/"
    return any(
        (candidate := (other.rstrip("/") or "/")) != normalized
        and candidate.startswith(f"{normalized}/")
        for other in sibling_paths
    )


def test_hr_dashboard_exact_when_onboarding_sibling_exists():
    paths = ["/hr", "/hr/onboarding", "/performance", "/help-desk"]
    assert nav_item_needs_exact_match("/hr", paths) is True
    assert nav_item_needs_exact_match("/hr/onboarding", paths) is False
    assert nav_item_needs_exact_match("/performance", paths) is False


def test_projects_not_forced_exact_without_sibling_nav_item():
    # /projects/archived is a route, but not a sibling nav item — keep prefix match.
    paths = ["/dashboard", "/projects", "/timesheets"]
    assert nav_item_needs_exact_match("/projects", paths) is False
    assert nav_item_needs_exact_match("/timesheets", paths) is False
