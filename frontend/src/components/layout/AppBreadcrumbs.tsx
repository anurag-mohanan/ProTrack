import { Breadcrumbs, Link, Typography } from '@mui/material';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import { Link as RouterLink, useLocation } from 'react-router-dom';

interface BreadcrumbItem {
  label: string;
  to?: string;
}

const ROUTE_LABELS: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/projects': 'Projects',
  '/projects/archived': 'Archived Projects',
  '/timesheets': 'Timesheets',
  '/workload': 'Workload',
  '/resource-planning': 'Resource Planning',
  '/reports': 'Reports',
  '/profile': 'My Profile',
  '/admin/dashboard': 'Admin Dashboard',
  '/admin/create': 'Create',
  '/admin/manage': 'Manage',
  '/admin/imports': 'Imports',
  '/admin/reports': 'Reports',
  '/admin/system': 'System',
  '/admin/users': 'Users',
  '/admin/deleted-users': 'Deleted Users',
  '/admin/customers': 'Customers',
  '/admin/contacts': 'Contacts',
  '/admin/teams': 'Teams',
  '/admin/streams': 'Streams',
  '/admin/task-types': 'Task Types',
  '/admin/non-productive-codes': 'NP Codes',
  '/admin/project-types': 'Project Types',
  '/admin/project-templates': 'Project Templates',
  '/admin/roles': 'Roles',
  '/admin/settings': 'Company Settings',
  '/admin/settings/company': 'Company Information',
  '/admin/settings/branding': 'Branding',
  '/admin/settings/holidays': 'Holiday Calendar',
  '/admin/settings/departments': 'Departments',
  '/admin/settings/paths': 'File Paths',
  '/admin/settings/notifications': 'Notifications',
  '/admin/deleted-projects': 'Deleted Projects',
  '/admin/import-historical-projects': 'Historical Import',
  '/admin/imports/historical-projects': 'Historical Projects',
  '/admin/imports/historical-timesheets': 'Historical Timesheets',
};

function resolveBreadcrumbs(pathname: string): BreadcrumbItem[] {
  if (ROUTE_LABELS[pathname]) {
    if (pathname.startsWith('/admin/')) {
      return [
        { label: 'Administration', to: '/admin/dashboard' },
        { label: ROUTE_LABELS[pathname] },
      ];
    }
    return [{ label: ROUTE_LABELS[pathname] }];
  }

  if (pathname.startsWith('/projects/') && pathname !== '/projects/archived') {
    const projectId = pathname.split('/')[2] ?? '';
    return [
      { label: 'Projects', to: '/projects' },
      { label: projectId ? `Project ${projectId.slice(0, 8)}…` : 'Project Detail' },
    ];
  }

  if (pathname.startsWith('/admin/project-templates/')) {
    return [
      { label: 'Administration', to: '/admin/dashboard' },
      { label: 'Project Templates', to: '/admin/project-templates' },
      { label: 'Template Editor' },
    ];
  }

  if (pathname.startsWith('/admin/settings/')) {
    return [
      { label: 'Administration', to: '/admin/dashboard' },
      { label: 'Company Settings', to: '/admin/settings' },
      { label: ROUTE_LABELS[pathname] ?? 'Settings' },
    ];
  }

  if (pathname.startsWith('/timesheets/') && pathname.includes('/entries/new')) {
    return [
      { label: 'Timesheets', to: '/timesheets' },
      { label: 'New Entry' },
    ];
  }

  return [{ label: 'Dashboard', to: '/dashboard' }];
}

export function useBreadcrumbTitle(): string {
  const { pathname } = useLocation();
  const items = resolveBreadcrumbs(pathname);
  return items[items.length - 1]?.label ?? 'ProTrack';
}

export function AppBreadcrumbs() {
  const { pathname } = useLocation();
  const items = resolveBreadcrumbs(pathname);

  return (
    <Breadcrumbs
      separator={<NavigateNextIcon sx={{ fontSize: 16 }} />}
      aria-label="breadcrumb"
      sx={{
        '& .MuiBreadcrumbs-li': { display: 'flex', alignItems: 'center' },
        '& .MuiBreadcrumbs-separator': { mx: 0.5 },
      }}
    >
      {items.map((item, index) => {
        const isLast = index === items.length - 1;
        if (isLast || !item.to) {
          return (
            <Typography
              key={`${item.label}-${index}`}
              variant="body2"
              sx={{ fontWeight: isLast ? 600 : 500, color: isLast ? 'text.primary' : 'text.secondary' }}
            >
              {item.label}
            </Typography>
          );
        }
        return (
          <Link
            key={`${item.label}-${index}`}
            component={RouterLink}
            to={item.to}
            underline="hover"
            color="text.secondary"
            variant="body2"
            sx={{ fontWeight: 500 }}
          >
            {item.label}
          </Link>
        );
      })}
    </Breadcrumbs>
  );
}
