import { Breadcrumbs, Link, Typography } from '@mui/material';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import { Link as RouterLink, useLocation } from 'react-router-dom';

interface BreadcrumbItem {
  label: string;
  to?: string;
}

const ROUTE_LABELS: Record<string, string> = {
  '/admin/dashboard': 'Overview',
  '/admin/create': 'Create',
  '/admin/manage': 'Manage',
  '/admin/imports': 'Import',
  '/admin/settings': 'Settings',
  '/admin/audit': 'Audit',
  '/admin/reports': 'Reports',
  '/admin/system': 'System Health',
  '/admin/users': 'Users',
  '/admin/deleted-users': 'Deleted Records',
  '/admin/customers': 'Customers',
  '/admin/contacts': 'Contacts',
  '/admin/teams': 'Teams',
  '/organization': 'Organization Chart',
  '/admin/streams': 'Streams',
  '/admin/task-types': 'Task Types',
  '/admin/non-productive-codes': 'NP Codes',
  '/admin/project-types': 'Project Types',
  '/admin/project-templates': 'Project Templates',
  '/admin/roles': 'Roles',
  '/admin/role-hierarchy': 'Role Hierarchy',
  '/admin/org-departments': 'Org Departments',
  '/admin/settings/company': 'Company Information',
  '/admin/settings/branding': 'Theme & Colours',
  '/admin/settings/holidays': 'Holiday Calendar',
  '/admin/settings/departments': 'Departments',
  '/admin/settings/paths': 'File Paths',
  '/admin/settings/notifications': 'Notifications',
  '/admin/settings/security': 'Security',
  '/admin/deleted-projects': 'Deleted Records',
  '/admin/imports/historical-projects': 'Historical Projects',
  '/admin/imports/historical-timesheets': 'Historical Timesheets',
};

function resolveAdminBreadcrumbs(pathname: string): BreadcrumbItem[] {
  const root = { label: 'System Administration', to: '/admin/dashboard' };

  if (pathname === '/admin/dashboard') {
    return [root];
  }

  if (ROUTE_LABELS[pathname]) {
    return [root, { label: ROUTE_LABELS[pathname] }];
  }

  if (pathname.startsWith('/admin/project-templates/')) {
    return [
      root,
      { label: 'Project Templates', to: '/admin/project-templates' },
      { label: 'Template Editor' },
    ];
  }

  if (pathname.startsWith('/admin/settings/')) {
    return [
      root,
      { label: 'Settings', to: '/admin/settings' },
      { label: ROUTE_LABELS[pathname] ?? 'Settings' },
    ];
  }

  if (pathname.startsWith('/admin/imports/')) {
    return [
      root,
      { label: 'Import', to: '/admin/imports' },
      { label: ROUTE_LABELS[pathname] ?? 'Import' },
    ];
  }

  return [root, { label: 'Administration' }];
}

export function useAdminBreadcrumbTitle(): string {
  const { pathname } = useLocation();
  const crumbs = resolveAdminBreadcrumbs(pathname);
  return crumbs[crumbs.length - 1]?.label ?? 'System Administration';
}

export function AdminBreadcrumbs() {
  const { pathname } = useLocation();
  const items = resolveAdminBreadcrumbs(pathname);

  return (
    <Breadcrumbs
      separator={<NavigateNextIcon fontSize="small" sx={{ color: 'grey.500' }} />}
      sx={{ '& .MuiTypography-root': { color: 'grey.400', fontSize: '0.8125rem' } }}
    >
      {items.map((item, index) => {
        const isLast = index === items.length - 1;
        if (isLast || !item.to) {
          return (
            <Typography key={`${item.label}-${index}`} color={isLast ? 'grey.200' : 'grey.400'}>
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
            sx={{ color: 'grey.400' }}
          >
            {item.label}
          </Link>
        );
      })}
    </Breadcrumbs>
  );
}
