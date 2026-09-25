import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Collapse,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Tooltip,
  Typography,
} from '@mui/material';
import AdminPanelSettingsRoundedIcon from '@mui/icons-material/AdminPanelSettingsRounded';
import ExpandLessRoundedIcon from '@mui/icons-material/ExpandLessRounded';
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import { LogoHomeLink } from '../branding/LogoHomeLink';
import type { CurrentUser } from '../../types';
import { designTokens } from '../../theme/designTokens';
import {
  FUTURE_MODULE_PLACEHOLDERS,
  accessContextFromUser,
  canAccessAdministration,
  getHrSectionNavItems,
  getItSectionNavItems,
  getMainNavItems,
  getOperationsSectionNavItems,
  type MainNavItem,
} from '../../utils/permissions';
import { navItemNeedsExactMatch } from '../../utils/navActive';
import { isNavItemActive, matchItNavPath, splitNavPath } from '../../utils/itNav';
import { NAV_COMPACT_BREAKPOINT } from '../../hooks/useResponsiveShell';
import { usePreferences } from '../../context/PreferencesContext';

export const DRAWER_WIDTH = 272;

/** Reserved for future compact (icon-rail) mode — same sidebar component. */
export type SidebarDisplayMode = 'expanded' | 'compact';

export type NavSectionId =
  | 'engineering'
  | 'operations'
  | 'hr'
  | 'it'
  | 'future'
  | 'admin';

const DEFAULT_SECTION_STATE: Record<NavSectionId, boolean> = {
  engineering: true,
  operations: true,
  hr: true,
  it: true,
  future: false,
  admin: true,
};

function parseSectionState(raw: string | null | undefined): Record<NavSectionId, boolean> {
  if (!raw) return { ...DEFAULT_SECTION_STATE };
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const next = { ...DEFAULT_SECTION_STATE };
    (Object.keys(DEFAULT_SECTION_STATE) as NavSectionId[]).forEach((key) => {
      if (typeof parsed[key] === 'boolean') {
        next[key] = parsed[key] as boolean;
      }
    });
    return next;
  } catch {
    return { ...DEFAULT_SECTION_STATE };
  }
}

function NavButton({
  path,
  label,
  icon: Icon,
  accent = false,
  disabled = false,
  end = false,
  nested = false,
  trailingPad = false,
  forceActive = false,
  onNavigate,
}: {
  path: string;
  label: string;
  icon?: React.ComponentType<{ fontSize?: 'small' | 'inherit' | 'large' | 'medium' }>;
  accent?: boolean;
  disabled?: boolean;
  end?: boolean;
  nested?: boolean;
  trailingPad?: boolean;
  forceActive?: boolean;
  onNavigate?: () => void;
}) {
  const location = useLocation();
  const active = isNavItemActive(path, location.pathname, location.search, {
    end,
    forceActive,
  });

  return (
    <ListItemButton
      component={disabled ? 'div' : RouterLink}
      to={disabled ? undefined : path}
      disabled={disabled}
      onClick={disabled ? undefined : onNavigate}
      className={active ? 'active' : undefined}
      sx={{
        mx: 1,
        mb: 0.25,
        pl: nested ? 4 : undefined,
        pr: trailingPad ? 5 : undefined,
        borderRadius: `${designTokens.radius.md}px`,
        color: accent ? 'rgba(255,255,255,0.92)' : 'rgba(255,255,255,0.68)',
        transition: `all ${designTokens.motion.fast}`,
        opacity: disabled ? 0.45 : 1,
        '&:hover': {
          bgcolor: disabled ? 'transparent' : designTokens.semantic.sidebarHover,
          color: disabled ? undefined : '#fff',
        },
        '&.active': {
          bgcolor: designTokens.semantic.sidebarActive,
          color: '#fff',
          boxShadow: 'inset 3px 0 0 #60a5fa',
          '& .MuiListItemIcon-root': {
            color: '#93c5fd',
          },
        },
      }}
    >
      {Icon ? (
        <ListItemIcon sx={{ minWidth: nested ? 28 : 40, color: 'inherit' }}>
          <Icon fontSize="small" />
        </ListItemIcon>
      ) : null}
      <ListItemText
        primary={label}
        secondary={disabled ? 'Coming soon' : undefined}
        slotProps={{
          primary: { sx: { fontWeight: 600, fontSize: '0.875rem' } },
          secondary: { sx: { color: 'rgba(255,255,255,0.35)', fontSize: '0.7rem' } },
        }}
      />
    </ListItemButton>
  );
}

function ITNavGroup({
  item,
  allNavPaths,
  onNavigate,
}: {
  item: MainNavItem;
  allNavPaths: string[];
  onNavigate?: () => void;
}) {
  const location = useLocation();
  const children = item.children ?? [];
  const childActive = children.some((child) =>
    matchItNavPath(child.path, location.pathname, location.search),
  );
  const selfActive =
    !childActive && matchItNavPath(item.path, location.pathname, location.search);
  const [open, setOpen] = useState(childActive || selfActive);
  const areaActive = (item.activePaths ?? []).some(
    (base) => location.pathname === base || location.pathname.startsWith(`${base}/`),
  );

  useEffect(() => {
    if (childActive || selfActive) setOpen(true);
  }, [childActive, selfActive]);

  if (!children.length) {
    return (
      <NavButton
        path={item.path}
        label={item.label}
        icon={item.icon}
        forceActive={areaActive}
        end={navItemNeedsExactMatch(splitNavPath(item.path).pathname, allNavPaths)}
        onNavigate={onNavigate}
      />
    );
  }

  return (
    <>
      <Box sx={{ position: 'relative' }}>
        <NavButton
          path={item.path}
          label={item.label}
          icon={item.icon}
          trailingPad
          forceActive={childActive}
          end={navItemNeedsExactMatch(splitNavPath(item.path).pathname, allNavPaths)}
          onNavigate={() => {
            setOpen(true);
            onNavigate?.();
          }}
        />
        <IconButton
          size="small"
          aria-label={open ? `Collapse ${item.label}` : `Expand ${item.label}`}
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            setOpen((value) => !value);
          }}
          sx={{
            position: 'absolute',
            right: 12,
            top: '50%',
            transform: 'translateY(-50%)',
            color: 'rgba(255,255,255,0.55)',
          }}
        >
          {open ? <ExpandLessRoundedIcon fontSize="small" /> : <ExpandMoreRoundedIcon fontSize="small" />}
        </IconButton>
      </Box>
      <Collapse in={open} timeout="auto" unmountOnExit>
        <List disablePadding>
          {children.map((child) => (
            <NavButton
              key={child.path}
              path={child.path}
              label={child.label}
              nested
              end={navItemNeedsExactMatch(splitNavPath(child.path).pathname, allNavPaths)}
              onNavigate={onNavigate}
            />
          ))}
        </List>
      </Collapse>
    </>
  );
}

function CollapsibleNavSection({
  sectionId,
  title,
  open,
  onToggle,
  children,
  leadingIcon,
}: {
  sectionId: NavSectionId;
  title: string;
  open: boolean;
  onToggle: (id: NavSectionId) => void;
  children: React.ReactNode;
  leadingIcon?: React.ReactNode;
}) {
  const panelId = `nav-section-${sectionId}`;
  const labelId = `${panelId}-label`;
  return (
    <>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 1.5,
          py: 0.25,
        }}
      >
        <Box
          component="button"
          type="button"
          id={labelId}
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => onToggle(sectionId)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              onToggle(sectionId);
            }
          }}
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            flex: 1,
            border: 0,
            background: 'transparent',
            cursor: 'pointer',
            color: 'inherit',
            textAlign: 'left',
            px: 1,
            py: 0.75,
            borderRadius: `${designTokens.radius.sm}px`,
            '&:hover': { bgcolor: 'rgba(255,255,255,0.06)' },
            '&:focus-visible': {
              outline: '2px solid #93c5fd',
              outlineOffset: 2,
            },
          }}
        >
          {leadingIcon}
          <Typography
            variant="overline"
            sx={{ color: 'rgba(255,255,255,0.45)', letterSpacing: '0.08em', lineHeight: 1.2 }}
          >
            {title}
          </Typography>
        </Box>
        <Tooltip title={open ? `Collapse ${title}` : `Expand ${title}`}>
          <IconButton
            size="small"
            aria-label={open ? `Collapse ${title}` : `Expand ${title}`}
            aria-expanded={open}
            aria-controls={panelId}
            onClick={() => onToggle(sectionId)}
            sx={{ color: 'rgba(255,255,255,0.6)' }}
          >
            {open ? (
              <ExpandLessRoundedIcon fontSize="small" />
            ) : (
              <ExpandMoreRoundedIcon fontSize="small" />
            )}
          </IconButton>
        </Tooltip>
      </Box>
      <Collapse in={open} id={panelId} role="region" aria-labelledby={labelId}>
        {children}
      </Collapse>
    </>
  );
}

interface AppSidebarProps {
  user: CurrentUser | null;
  mobileOpen?: boolean;
  onMobileClose?: () => void;
  /** Future compact rail — architecture hook only; always expanded for now. */
  displayMode?: SidebarDisplayMode;
}

export function AppSidebar({
  user,
  mobileOpen = false,
  onMobileClose,
  displayMode = 'expanded',
}: AppSidebarProps) {
  void displayMode;
  const { preferences, updatePreferences } = usePreferences();
  const [sectionState, setSectionState] = useState<Record<NavSectionId, boolean>>(
    DEFAULT_SECTION_STATE,
  );

  useEffect(() => {
    setSectionState(parseSectionState(preferences?.sidebar_section_state));
  }, [preferences?.sidebar_section_state]);

  const toggleSection = useCallback(
    (id: NavSectionId) => {
      setSectionState((prev) => {
        const next = { ...prev, [id]: !prev[id] };
        void updatePreferences({ sidebar_section_state: JSON.stringify(next) });
        return next;
      });
    },
    [updatePreferences],
  );

  const ctx = accessContextFromUser(user);
  const visibleNavItems = getMainNavItems(ctx);
  const operationsItems = getOperationsSectionNavItems(ctx);
  const hrItems = getHrSectionNavItems(ctx);
  const itItems = getItSectionNavItems(ctx);
  const showAdministratorEntry = canAccessAdministration(ctx);
  const allNavPaths = useMemo(
    () => [
      ...visibleNavItems.map((item) => item.path),
      ...operationsItems.map((item) => item.path),
      ...hrItems.map((item) => item.path),
      ...itItems.flatMap((item) => [
        splitNavPath(item.path).pathname,
        ...(item.children ?? []).map((child) => splitNavPath(child.path).pathname),
      ]),
    ],
    [visibleNavItems, operationsItems, hrItems, itItems],
  );

  const drawerPaperSx = {
    width: DRAWER_WIDTH,
    boxSizing: 'border-box' as const,
    bgcolor: designTokens.semantic.sidebar,
    color: '#fff',
    borderRight: 'none',
    boxShadow: designTokens.elevation.nav,
  };

  const nav = (
    <>
      <Toolbar sx={{ px: 2.5, minHeight: '72px !important' }}>
        <LogoHomeLink light size="md" />
      </Toolbar>

      <Box sx={{ px: 0.5, pb: 2, overflow: 'auto', maxHeight: 'calc(100dvh - 72px)' }}>
        <CollapsibleNavSection
          sectionId="engineering"
          title="Engineering Operations"
          open={sectionState.engineering}
          onToggle={toggleSection}
        >
          <List disablePadding>
            {visibleNavItems.map((item) => (
              <NavButton
                key={item.path}
                path={item.path}
                label={item.label}
                icon={item.icon}
                end={navItemNeedsExactMatch(item.path, allNavPaths)}
                onNavigate={onMobileClose}
              />
            ))}
          </List>
        </CollapsibleNavSection>

        {operationsItems.length > 0 ? (
          <>
            <Divider sx={{ my: 1.5, mx: 2, borderColor: 'rgba(255,255,255,0.08)' }} />
            <CollapsibleNavSection
              sectionId="operations"
              title="Operations"
              open={sectionState.operations}
              onToggle={toggleSection}
            >
              <List disablePadding>
                {operationsItems.map((item) => (
                  <NavButton
                    key={item.path}
                    path={item.path}
                    label={item.label}
                    icon={item.icon}
                    end={navItemNeedsExactMatch(item.path, allNavPaths)}
                    onNavigate={onMobileClose}
                  />
                ))}
              </List>
            </CollapsibleNavSection>
          </>
        ) : null}

        {hrItems.length > 0 ? (
          <>
            <Divider sx={{ my: 1.5, mx: 2, borderColor: 'rgba(255,255,255,0.08)' }} />
            <CollapsibleNavSection
              sectionId="hr"
              title="Human Resources"
              open={sectionState.hr}
              onToggle={toggleSection}
            >
              <List disablePadding>
                {hrItems.map((item) => (
                  <NavButton
                    key={item.path}
                    path={item.path}
                    label={item.label}
                    icon={item.icon}
                    end={navItemNeedsExactMatch(item.path, allNavPaths)}
                    onNavigate={onMobileClose}
                  />
                ))}
              </List>
            </CollapsibleNavSection>
          </>
        ) : null}

        {itItems.length > 0 ? (
          <>
            <Divider sx={{ my: 1.5, mx: 2, borderColor: 'rgba(255,255,255,0.08)' }} />
            <CollapsibleNavSection
              sectionId="it"
              title="IT Operations"
              open={sectionState.it}
              onToggle={toggleSection}
            >
              <List disablePadding>
                {itItems.map((item) => (
                  <ITNavGroup
                    key={item.path}
                    item={item}
                    allNavPaths={allNavPaths}
                    onNavigate={onMobileClose}
                  />
                ))}
              </List>
            </CollapsibleNavSection>
          </>
        ) : null}

        <Divider sx={{ my: 1.5, mx: 2, borderColor: 'rgba(255,255,255,0.08)' }} />
        <CollapsibleNavSection
          sectionId="future"
          title="Future Modules"
          open={sectionState.future}
          onToggle={toggleSection}
        >
          <List disablePadding>
            {FUTURE_MODULE_PLACEHOLDERS.map((item) => (
              <NavButton key={item.path} path={item.path} label={item.label} disabled />
            ))}
          </List>
        </CollapsibleNavSection>

        {showAdministratorEntry ? (
          <>
            <Divider sx={{ my: 1.5, mx: 2, borderColor: 'rgba(255,255,255,0.08)' }} />
            <CollapsibleNavSection
              sectionId="admin"
              title="System Administration"
              open={sectionState.admin}
              onToggle={toggleSection}
              leadingIcon={
                <AdminPanelSettingsRoundedIcon sx={{ fontSize: 16, color: '#93c5fd' }} />
              }
            >
              <List disablePadding>
                <NavButton
                  path="/admin/dashboard"
                  label="System Administration"
                  icon={AdminPanelSettingsRoundedIcon}
                  accent
                  onNavigate={onMobileClose}
                />
              </List>
            </CollapsibleNavSection>
          </>
        ) : null}
      </Box>
    </>
  );

  return (
    <>
      <Drawer
        variant="temporary"
        open={mobileOpen}
        onClose={onMobileClose}
        ModalProps={{ keepMounted: true }}
        sx={{
          display: { xs: 'block', [NAV_COMPACT_BREAKPOINT]: 'none' },
          [`& .MuiDrawer-paper`]: drawerPaperSx,
        }}
      >
        {nav}
      </Drawer>
      <Drawer
        variant="permanent"
        open
        sx={{
          display: { xs: 'none', [NAV_COMPACT_BREAKPOINT]: 'block' },
          width: DRAWER_WIDTH,
          flexShrink: 0,
          [`& .MuiDrawer-paper`]: drawerPaperSx,
        }}
      >
        {nav}
      </Drawer>
    </>
  );
}
