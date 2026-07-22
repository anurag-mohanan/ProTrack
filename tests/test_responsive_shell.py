"""Responsive shell — company-wide layout scaling checks."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def test_viewport_meta_present_in_index_html():
    text = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert 'name="viewport"' in text
    assert "width=device-width" in text
    assert "initial-scale=1" in text


def test_responsive_shell_hook_defines_compact_breakpoint():
    text = (FRONTEND / "src" / "hooks" / "useResponsiveShell.ts").read_text(encoding="utf-8")
    assert 'NAV_COMPACT_BREAKPOINT = \'md\'' in text or 'NAV_COMPACT_BREAKPOINT = "md"' in text
    assert "100dvh" in text
    assert "useMediaQuery" in text


def test_main_and_admin_layouts_use_responsive_shell():
    main = (FRONTEND / "src" / "layouts" / "MainLayout.tsx").read_text(encoding="utf-8")
    admin = (FRONTEND / "src" / "layouts" / "AdminLayout.tsx").read_text(encoding="utf-8")
    assert "useResponsiveShell" in main
    assert "useResponsiveShell" in admin
    assert "overflowX: 'clip'" in main
    assert "overflowX: 'clip'" in admin


def test_sidebars_support_temporary_drawer_on_compact():
    app = (FRONTEND / "src" / "components" / "layout" / "AppSidebar.tsx").read_text(encoding="utf-8")
    admin = (FRONTEND / "src" / "components" / "layout" / "AdminSidebar.tsx").read_text(
        encoding="utf-8"
    )
    assert 'variant="temporary"' in app
    assert 'variant="permanent"' in app
    assert 'variant="temporary"' in admin
    assert 'variant="permanent"' in admin
