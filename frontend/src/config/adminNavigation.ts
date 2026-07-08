import type { SvgIconComponent } from '@mui/icons-material';
import AddIcon from '@mui/icons-material/Add';
import AssessmentIcon from '@mui/icons-material/Assessment';
import BlockIcon from '@mui/icons-material/Block';
import BusinessIcon from '@mui/icons-material/Business';
import CategoryIcon from '@mui/icons-material/Category';
import ContactPhoneIcon from '@mui/icons-material/ContactPhone';
import DashboardIcon from '@mui/icons-material/Dashboard';
import DeleteIcon from '@mui/icons-material/Delete';
import DownloadIcon from '@mui/icons-material/Download';
import FolderSharedIcon from '@mui/icons-material/FolderShared';
import GroupsIcon from '@mui/icons-material/Groups';
import HistoryIcon from '@mui/icons-material/History';
import ManageAccountsIcon from '@mui/icons-material/ManageAccounts';
import PeopleIcon from '@mui/icons-material/People';
import SecurityIcon from '@mui/icons-material/Security';
import SettingsIcon from '@mui/icons-material/Settings';
import PaletteIcon from '@mui/icons-material/Palette';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import ScheduleIcon from '@mui/icons-material/Schedule';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import TypeSpecimenIcon from '@mui/icons-material/TypeSpecimen';
import ViewTimelineIcon from '@mui/icons-material/ViewTimeline';
import BuildIcon from '@mui/icons-material/Build';
import ArchiveIcon from '@mui/icons-material/Archive';
import EmailIcon from '@mui/icons-material/Email';
import BackupIcon from '@mui/icons-material/Backup';
import RestorePageIcon from '@mui/icons-material/RestorePage';
import LockIcon from '@mui/icons-material/Lock';
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import MonitorHeartIcon from '@mui/icons-material/MonitorHeart';
import WorkHistoryIcon from '@mui/icons-material/WorkHistory';
import RefreshIcon from '@mui/icons-material/Refresh';
import {
  canImportHistoricalProjects,
  canImportHistoricalTimesheets,
  ROLES,
} from '../utils/permissions';

export interface AdminNavItem {
  id: string;
  label: string;
  path?: string;
  icon: SvgIconComponent;
  children?: AdminNavItem[];
  comingSoon?: boolean;
}

export interface AdminCreateAction {
  id: string;
  title: string;
  description: string;
  icon: SvgIconComponent;
  path: string;
}

export interface AdminHubItem {
  id: string;
  title: string;
  description: string;
  icon: SvgIconComponent;
  path: string;
  comingSoon?: boolean;
}

export interface AdminWorkspaceNavItem {
  label: string;
  path: string;
  icon: SvgIconComponent;
}

export const ADMIN_WORKSPACE_NAV: AdminWorkspaceNavItem[] = [
  { label: 'Overview', path: '/admin/dashboard', icon: DashboardIcon },
  { label: 'Create', path: '/admin/create', icon: AddIcon },
  { label: 'Manage', path: '/admin/manage', icon: ManageAccountsIcon },
  { label: 'Import / Export', path: '/admin/imports', icon: UploadFileIcon },
  { label: 'System Settings', path: '/admin/settings', icon: SettingsIcon },
  { label: 'Audit & Maintenance', path: '/admin/audit', icon: HistoryIcon },
];

export const ADMIN_CREATE_ACTIONS: AdminCreateAction[] = [
  { id: 'user', title: 'User', description: 'Add a team member with role and access.', icon: PeopleIcon, path: '/admin/users?create=1' },
  { id: 'customer', title: 'Customer', description: 'Register a customer organisation.', icon: BusinessIcon, path: '/admin/customers?create=1' },
  { id: 'contact', title: 'Contact', description: 'Add a customer contact person.', icon: ContactPhoneIcon, path: '/admin/contacts?create=1' },
  { id: 'team', title: 'Team', description: 'Create an engineering team.', icon: GroupsIcon, path: '/admin/teams?create=1' },
  { id: 'role', title: 'Role', description: 'Define a security role.', icon: SecurityIcon, path: '/admin/roles?create=1' },
  { id: 'task-type', title: 'Task Type', description: 'Configure productive task categories.', icon: CategoryIcon, path: '/admin/task-types?create=1' },
  { id: 'stream', title: 'Stream', description: 'Add a design stream or discipline.', icon: AccountTreeIcon, path: '/admin/streams?create=1' },
  { id: 'project-template', title: 'Project Template', description: 'Define milestones for a project type.', icon: ViewTimelineIcon, path: '/admin/project-templates/new' },
  { id: 'np-code', title: 'NP Code', description: 'Add a non-productive code for timesheets.', icon: BlockIcon, path: '/admin/non-productive-codes?create=1' },
  { id: 'project-type', title: 'Project Type', description: 'Add a project classification.', icon: TypeSpecimenIcon, path: '/admin/project-types?create=1' },
];

export const ADMIN_MANAGE_ITEMS: AdminHubItem[] = [
  { id: 'users', title: 'Users', description: 'Accounts, roles, and access.', icon: PeopleIcon, path: '/admin/users' },
  { id: 'customers', title: 'Customers', description: 'Customer organisations.', icon: BusinessIcon, path: '/admin/customers' },
  { id: 'contacts', title: 'Contacts', description: 'Customer contact people.', icon: ContactPhoneIcon, path: '/admin/contacts' },
  { id: 'teams', title: 'Teams', description: 'Engineering teams and leads.', icon: GroupsIcon, path: '/admin/teams' },
  { id: 'roles', title: 'Roles', description: 'Security roles and permissions.', icon: SecurityIcon, path: '/admin/roles' },
  { id: 'task-types', title: 'Task Types', description: 'Productive task categories.', icon: CategoryIcon, path: '/admin/task-types' },
  { id: 'streams', title: 'Streams', description: 'Design streams and disciplines.', icon: AccountTreeIcon, path: '/admin/streams' },
  { id: 'project-templates', title: 'Project Templates', description: 'Milestone workflows by project type.', icon: ViewTimelineIcon, path: '/admin/project-templates' },
  { id: 'project-types', title: 'Project Types', description: 'Project classifications.', icon: TypeSpecimenIcon, path: '/admin/project-types' },
  { id: 'np-codes', title: 'NP Codes', description: 'Non-productive timesheet codes.', icon: BlockIcon, path: '/admin/non-productive-codes' },
];

function buildImportItems(roleName: string, includeComingSoon: boolean): AdminHubItem[] {
  const items: AdminHubItem[] = [
    { id: 'projects-import', title: 'Projects', description: 'Bulk project import.', icon: FolderSharedIcon, path: '/admin/imports', comingSoon: true },
  ];

  if (canImportHistoricalProjects(roleName)) {
    items.push({
      id: 'historical-projects',
      title: 'Historical Projects',
      description: 'Import legacy project workbooks.',
      icon: UploadFileIcon,
      path: '/admin/imports/historical-projects',
    });
  }

  items.push(
    { id: 'users-import', title: 'Users', description: 'Bulk user import.', icon: PeopleIcon, path: '/admin/imports', comingSoon: true },
    { id: 'customers-import', title: 'Customers', description: 'Bulk customer import.', icon: BusinessIcon, path: '/admin/imports', comingSoon: true },
    { id: 'timesheets-import', title: 'Timesheets', description: 'Bulk timesheet import.', icon: ScheduleIcon, path: '/admin/imports', comingSoon: true },
  );

  if (canImportHistoricalTimesheets(roleName)) {
    items.push({
      id: 'historical-timesheets',
      title: 'Historical Timesheets',
      description: 'Import designer timesheet files.',
      icon: UploadFileIcon,
      path: '/admin/imports/historical-timesheets',
    });
  }

  items.push(
    { id: 'templates-import', title: 'Project Templates', description: 'Template import.', icon: ViewTimelineIcon, path: '/admin/imports', comingSoon: true },
    { id: 'export-data', title: 'Export Data', description: 'Export master data and reports.', icon: DownloadIcon, path: '/admin/imports', comingSoon: true },
  );

  return includeComingSoon ? items : items.filter((item) => !item.comingSoon);
}

export const ADMIN_IMPORT_ITEMS = (roleName: string): AdminHubItem[] =>
  buildImportItems(roleName, false);

// Unfinished ("Coming Soon") items are hidden from navigation until implemented.
export const ADMIN_IMPORT_ALL_ITEMS = (roleName: string): AdminHubItem[] =>
  buildImportItems(roleName, false);

const ALL_SETTINGS_ITEMS: AdminHubItem[] = [
  { id: 'system-settings', title: 'System Settings', description: 'Core application configuration.', icon: SettingsIcon, path: '/admin/settings' },
  { id: 'company', title: 'Company Information', description: 'Name, logo, address, hours, and holidays.', icon: BusinessIcon, path: '/admin/settings/company' },
  { id: 'branding', title: 'Theme', description: 'Default application theme and colour palette.', icon: PaletteIcon, path: '/admin/settings/branding' },
  { id: 'logo', title: 'Logo Upload', description: 'Company logo used across ProTrack.', icon: BusinessIcon, path: '/admin/settings/company' },
  { id: 'email', title: 'Email Settings', description: 'Outbound email configuration.', icon: EmailIcon, path: '/admin/settings', comingSoon: true },
  { id: 'notifications', title: 'Notifications', description: 'System notification rules.', icon: AssessmentIcon, path: '/admin/settings/notifications' },
  { id: 'backup', title: 'Backup', description: 'Database and file backup.', icon: BackupIcon, path: '/admin/settings', comingSoon: true },
  { id: 'restore', title: 'Restore', description: 'Restore from backup.', icon: RestorePageIcon, path: '/admin/settings', comingSoon: true },
  { id: 'security', title: 'Security', description: 'Authentication and access controls.', icon: LockIcon, path: '/admin/settings/security', comingSoon: true },
  { id: 'authentication', title: 'Authentication', description: 'Sign-in methods and session policy.', icon: VpnKeyIcon, path: '/admin/settings/security', comingSoon: true },
  { id: 'password-policy', title: 'Password Policy', description: 'Password complexity and expiry rules.', icon: SecurityIcon, path: '/admin/settings/security', comingSoon: true },
];

export const ADMIN_SETTINGS_ITEMS: AdminHubItem[] = ALL_SETTINGS_ITEMS.filter(
  (item) => !item.comingSoon,
);

const ALL_AUDIT_ITEMS: AdminHubItem[] = [
  { id: 'audit-logs', title: 'Audit Logs', description: 'System activity and change history.', icon: HistoryIcon, path: '/admin/audit', comingSoon: true },
  { id: 'deleted-records', title: 'Deleted Records', description: 'Recover soft-deleted projects and users.', icon: DeleteIcon, path: '/admin/deleted-projects' },
  { id: 'deleted-timesheets', title: 'Deleted Timesheet Entries', description: 'Audit and restore soft-deleted timesheet rows.', icon: ScheduleIcon, path: '/admin/deleted-timesheet-entries' },
  { id: 'archived-records', title: 'Archived Records', description: 'Review archived engineering projects.', icon: ArchiveIcon, path: '/projects/archived' },
  { id: 'system-health', title: 'System Health', description: 'Version, services, and runtime status.', icon: MonitorHeartIcon, path: '/admin/system' },
  { id: 'rebuild-timesheet-stats', title: 'Rebuild Timesheet Statistics', description: 'Recalculate all timesheet summaries and repair data.', icon: RefreshIcon, path: '/admin/rebuild-timesheet-stats' },
  { id: 'import-history', title: 'Import History', description: 'Historical import audit trail.', icon: WorkHistoryIcon, path: '/admin/imports/historical-timesheets#history' },
  { id: 'background-jobs', title: 'Background Jobs', description: 'Scheduled tasks and queue status.', icon: BuildIcon, path: '/admin/audit', comingSoon: true },
];

export const ADMIN_AUDIT_ITEMS: AdminHubItem[] = ALL_AUDIT_ITEMS.filter(
  (item) => !item.comingSoon,
);

export const ADMIN_REPORT_ITEMS: AdminHubItem[] = [
  { id: 'import-history', title: 'Import History', description: 'Historical import audit.', icon: HistoryIcon, path: '/admin/imports/historical-timesheets#history' },
];

export const ADMIN_SYSTEM_ITEMS: AdminHubItem[] = [
  { id: 'version', title: 'Version Information', description: 'Build and release details.', icon: SettingsIcon, path: '/admin/system' },
];

/** @deprecated Use ADMIN_WORKSPACE_NAV in the dedicated administrator workspace sidebar. */
export function getAdminNavSections(_roleName: string): AdminNavItem[] {
  return ADMIN_WORKSPACE_NAV.map((item) => ({
    id: item.path.replace('/admin/', ''),
    label: item.label,
    path: item.path,
    icon: item.icon,
  }));
}

export function isAdminRole(roleName: string): boolean {
  return roleName === ROLES.ADMIN;
}
