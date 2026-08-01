import { Breadcrumbs, Link, Typography } from '@mui/material';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import { useQuery } from '@tanstack/react-query';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import { commandCenterQueryKeys, fetchProjectCommandCenter } from '../../api/commandCenter';

interface BreadcrumbItem {
  label: string;
  to?: string;
}

const ROUTE_LABELS: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/projects': 'Projects',
  '/projects/archived': 'Archived Projects',
  '/timesheets': 'Timesheets',
  '/timesheets/month': 'Timesheet Entry',
  '/workload': 'Workload',
  '/resource-planning': 'Resource Planning',
  '/hr': 'HR Dashboard',
  '/hr/onboarding': 'Onboarding',
  '/hr/training': 'Training',
  '/hr/exit-process': 'Exit process',
  '/hr/past-employees': 'Past employees',
  '/hr/process-audit': 'Process Audit',
  '/performance': 'Performance',
  '/help-desk': 'Help Desk',
  '/organization': 'Organization Chart',
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
  '/admin/role-hierarchy': 'Role Hierarchy',
  '/admin/org-departments': 'Org Departments',
  '/admin/settings': 'System Settings',
  '/admin/settings/company': 'Company Information',
  '/admin/settings/branding': 'Branding',
  '/admin/settings/commercial': 'Commercial / Tenancy',
  '/admin/settings/commercial-readiness': 'Commercial Readiness',
  '/admin/settings/holidays': 'Holiday Calendar',
  '/admin/settings/departments': 'Departments',
  '/admin/settings/paths': 'File Paths',
  '/admin/settings/notifications': 'Notifications',
  '/admin/deleted-projects': 'Deleted Projects',
  '/admin/import-historical-projects': 'Historical Import',
  '/admin/imports/historical-projects': 'Historical Projects',
  '/admin/imports/historical-timesheets': 'Historical Timesheets',
};

function projectIdFromPath(pathname: string): string | null {
  if (!pathname.startsWith('/projects/') || pathname === '/projects/archived') {
    return null;
  }
  const segment = pathname.split('/')[2] ?? '';
  return segment || null;
}

function formatProjectTitle(toolNumber?: string | null, partDescription?: string | null): string {
  const tool = toolNumber?.trim() ?? '';
  const part = partDescription?.trim() ?? '';
  if (tool && part) return `${tool} · ${part}`;
  return tool || part || 'Project';
}

function resolveBreadcrumbs(pathname: string, projectLabel?: string | null): BreadcrumbItem[] {
  if (ROUTE_LABELS[pathname]) {
    if (pathname.startsWith('/admin/')) {
      return [
        { label: 'System Administration', to: '/admin/dashboard' },
        { label: ROUTE_LABELS[pathname] },
      ];
    }
    if (pathname.startsWith('/hr/') && pathname !== '/hr') {
      return [
        { label: 'HR Dashboard', to: '/hr' },
        { label: ROUTE_LABELS[pathname] },
      ];
    }
    if (pathname === '/projects/archived') {
      return [
        { label: 'Projects', to: '/projects' },
        { label: ROUTE_LABELS[pathname] },
      ];
    }
    return [{ label: ROUTE_LABELS[pathname] }];
  }

  if (pathname.startsWith('/projects/') && pathname !== '/projects/archived') {
    return [
      { label: 'Projects', to: '/projects' },
      { label: projectLabel?.trim() || 'Project' },
    ];
  }

  if (pathname.startsWith('/admin/project-templates/')) {
    return [
      { label: 'System Administration', to: '/admin/dashboard' },
      { label: 'Project Templates', to: '/admin/project-templates' },
      { label: 'Template Editor' },
    ];
  }

  if (pathname.startsWith('/admin/settings/')) {
    return [
      { label: 'System Administration', to: '/admin/dashboard' },
      { label: 'System Settings', to: '/admin/settings' },
      { label: ROUTE_LABELS[pathname] ?? 'Settings' },
    ];
  }

  if (pathname.startsWith('/timesheets/month')) {
    return [{ label: 'Timesheet Entry' }];
  }

  if (pathname.startsWith('/timesheets/') && pathname.includes('/entries/new')) {
    return [
      { label: 'Timesheets', to: '/timesheets' },
      { label: 'New Entry' },
    ];
  }

  return [{ label: 'Dashboard', to: '/dashboard' }];
}

function useProjectBreadcrumbLabel(projectId: string | null): string | null {
  const query = useQuery({
    queryKey: commandCenterQueryKeys.detail(projectId ?? ''),
    queryFn: () => fetchProjectCommandCenter(projectId!),
    enabled: Boolean(projectId),
    staleTime: 60_000,
  });
  if (!query.data?.project) return null;
  return formatProjectTitle(query.data.project.tool_number, query.data.project.part_description);
}

export function useBreadcrumbTitle(): string {
  const { pathname } = useLocation();
  const projectId = projectIdFromPath(pathname);
  const projectLabel = useProjectBreadcrumbLabel(projectId);
  const items = resolveBreadcrumbs(pathname, projectLabel);
  return items[items.length - 1]?.label ?? 'ProTrack';
}

export function AppBreadcrumbs() {
  const { pathname } = useLocation();
  const projectId = projectIdFromPath(pathname);
  const projectLabel = useProjectBreadcrumbLabel(projectId);
  const items = resolveBreadcrumbs(pathname, projectLabel);

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
