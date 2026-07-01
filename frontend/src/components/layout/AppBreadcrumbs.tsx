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
  '/reports': 'Reports',
  '/admin/users': 'Users',
  '/admin/customers': 'Customers',
  '/admin/contacts': 'Contacts',
  '/admin/streams': 'Streams',
  '/admin/task-types': 'Task Types',
  '/admin/non-productive-codes': 'NP Codes',
  '/admin/project-types': 'Project Types',
  '/admin/project-templates': 'Project Templates',
  '/admin/roles': 'Roles',
  '/admin/settings': 'System Settings',
  '/admin/deleted-projects': 'Deleted Projects',
  '/admin/import-historical-projects': 'Historical Import',
};

function resolveBreadcrumbs(pathname: string): BreadcrumbItem[] {
  if (ROUTE_LABELS[pathname]) {
    if (pathname.startsWith('/admin/')) {
      return [
        { label: 'Administration', to: '/admin/users' },
        { label: ROUTE_LABELS[pathname] },
      ];
    }
    return [{ label: ROUTE_LABELS[pathname] }];
  }

  if (pathname.startsWith('/projects/') && pathname !== '/projects/archived') {
    return [
      { label: 'Projects', to: '/projects' },
      { label: 'Project Details' },
    ];
  }

  if (pathname.startsWith('/admin/project-templates/')) {
    return [
      { label: 'Administration', to: '/admin/users' },
      { label: 'Project Templates', to: '/admin/project-templates' },
      { label: 'Template Editor' },
    ];
  }

  if (pathname.startsWith('/timesheets/') && pathname.includes('/entries/new')) {
    return [
      { label: 'Timesheets', to: '/timesheets' },
      { label: 'New Entry' },
    ];
  }

  return [{ label: 'ProTrack', to: '/dashboard' }];
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
