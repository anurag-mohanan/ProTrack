import {
  Collapse,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { NavLink, useLocation } from 'react-router-dom';
import type { AdminNavItem } from '../../config/adminNavigation';
import { useAdminNavExpanded } from '../../hooks/useAdminNavExpanded';

const leafSx = {
  color: 'prosohm.sidebarTextMuted',
  '&.active': {
    bgcolor: 'prosohm.sidebarActive',
    color: 'prosohm.sidebarText',
    borderLeft: '3px solid',
    borderColor: 'primary.main',
    '& .MuiListItemIcon-root': { color: 'primary.main' },
  },
};

function NavLeaf({ item, depth = 0 }: { item: AdminNavItem; depth?: number }) {
  if (item.comingSoon) {
    return (
      <ListItemButton disabled sx={{ pl: 2 + depth * 2, opacity: 0.6 }}>
        <ListItemIcon sx={{ minWidth: 32, color: 'inherit' }}>
          <item.icon fontSize="small" />
        </ListItemIcon>
        <ListItemText primary={`${item.label} (Soon)`} />
      </ListItemButton>
    );
  }

  if (!item.path) return null;

  return (
    <ListItemButton
      component={NavLink}
      to={item.path}
      end
      sx={{
        ...leafSx,
        pl: depth > 0 ? 4 : 2,
        '&.active': {
          ...leafSx['&.active'],
          pl: depth > 0 ? 'calc(32px - 3px)' : 'calc(16px - 3px)',
        },
      }}
    >
      <ListItemIcon sx={{ minWidth: 32, color: 'inherit' }}>
        <item.icon fontSize="small" />
      </ListItemIcon>
      <ListItemText primary={item.label} />
    </ListItemButton>
  );
}

function NavSection({ item }: { item: AdminNavItem }) {
  const location = useLocation();
  const hasChildren = Boolean(item.children?.length);
  const childActive = item.children?.some((child) => {
    if (!child.path) return false;
    const base = child.path.split('#')[0];
    return location.pathname === base || location.pathname.startsWith(`${base}/`);
  });
  const selfActive = item.path
    ? location.pathname === item.path.split('#')[0] ||
      location.pathname.startsWith(`${item.path.split('#')[0]}/`)
    : false;
  const { expanded, toggle } = useAdminNavExpanded(item.id, childActive || selfActive);

  if (!hasChildren) {
    return <NavLeaf item={item} />;
  }

  return (
    <>
      <ListItemButton
        onClick={toggle}
        sx={{
          color:
            childActive || selfActive ? 'prosohm.sidebarText' : 'prosohm.sidebarTextMuted',
          bgcolor: childActive || selfActive ? 'prosohm.sidebarActive' : undefined,
        }}
      >
        <ListItemIcon sx={{ minWidth: 40, color: 'inherit' }}>
          <item.icon fontSize="small" />
        </ListItemIcon>
        <ListItemText primary={item.label} />
        {expanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
      </ListItemButton>
      <Collapse in={expanded} timeout="auto" unmountOnExit>
        <List disablePadding>
          {item.path ? (
            <ListItemButton component={NavLink} to={item.path} end sx={leafSx}>
              <ListItemText primary="Overview" sx={{ pl: 2 }} />
            </ListItemButton>
          ) : null}
          {item.children?.map((child) => (
            <NavLeaf key={child.id} item={child} depth={1} />
          ))}
        </List>
      </Collapse>
    </>
  );
}

interface AdminNavigationProps {
  sections: AdminNavItem[];
}

export function AdminNavigation({ sections }: AdminNavigationProps) {
  return (
    <List disablePadding>
      {sections.map((section) => (
        <NavSection key={section.id} item={section} />
      ))}
    </List>
  );
}
