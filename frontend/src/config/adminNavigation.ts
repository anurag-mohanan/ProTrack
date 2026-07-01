import type { SvgIconComponent } from '@mui/icons-material';
import AddIcon from '@mui/icons-material/Add';
import AssessmentIcon from '@mui/icons-material/Assessment';
import BlockIcon from '@mui/icons-material/Block';
import BusinessIcon from '@mui/icons-material/Business';
import CategoryIcon from '@mui/icons-material/Category';
import ContactPhoneIcon from '@mui/icons-material/ContactPhone';
import DashboardIcon from '@mui/icons-material/Dashboard';
import DeleteIcon from '@mui/icons-material/Delete';
import FolderSharedIcon from '@mui/icons-material/FolderShared';
import GroupsIcon from '@mui/icons-material/Groups';
import HistoryIcon from '@mui/icons-material/History';
import ManageAccountsIcon from '@mui/icons-material/ManageAccounts';
import PeopleIcon from '@mui/icons-material/People';
import SecurityIcon from '@mui/icons-material/Security';
import SettingsIcon from '@mui/icons-material/Settings';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import TypeSpecimenIcon from '@mui/icons-material/TypeSpecimen';
import ViewTimelineIcon from '@mui/icons-material/ViewTimeline';
import BuildIcon from '@mui/icons-material/Build';
import {
  canImportHistoricalProjects,
  canImportHistoricalTimesheets,
  canViewDeletedProjects,
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

function canSeeImportProjects(roleName: string) {
  return canImportHistoricalProjects(roleName);
}

function canSeeImportTimesheets(roleName: string) {
  return canImportHistoricalTimesheets(roleName);
}

function isAdmin(roleName: string) {
  return roleName === ROLES.ADMIN;
}

export function getAdminNavSections(roleName: string): AdminNavItem[] {
  const manageChildren: AdminNavItem[] = [
    { id: 'users', label: 'Users', path: '/admin/users', icon: PeopleIcon },
    { id: 'customers', label: 'Customers', path: '/admin/customers', icon: BusinessIcon },
    { id: 'contacts', label: 'Contacts', path: '/admin/contacts', icon: ContactPhoneIcon },
    { id: 'teams', label: 'Teams', path: '/admin/teams', icon: GroupsIcon },
    { id: 'project-types', label: 'Project Types', path: '/admin/project-types', icon: TypeSpecimenIcon },
    {
      id: 'project-templates',
      label: 'Project Templates',
      path: '/admin/project-templates',
      icon: ViewTimelineIcon,
    },
    { id: 'streams', label: 'Streams', path: '/admin/streams', icon: AccountTreeIcon },
    { id: 'task-types', label: 'Task Types', path: '/admin/task-types', icon: CategoryIcon },
    { id: 'roles', label: 'Roles', path: '/admin/roles', icon: SecurityIcon },
    {
      id: 'np-codes',
      label: 'Non Productive Codes',
      path: '/admin/non-productive-codes',
      icon: BlockIcon,
    },
    {
      id: 'company-settings',
      label: 'Company Settings',
      path: '/admin/settings',
      icon: SettingsIcon,
    },
  ];

  if (canViewDeletedProjects(roleName)) {
    manageChildren.push({
      id: 'deleted-projects',
      label: 'Deleted Projects',
      path: '/admin/deleted-projects',
      icon: DeleteIcon,
    });
  }

  const importChildren: AdminNavItem[] = [];
  if (canSeeImportProjects(roleName)) {
    importChildren.push({
      id: 'historical-projects',
      label: 'Historical Projects',
      path: '/admin/imports/historical-projects',
      icon: UploadFileIcon,
    });
  }
  if (canSeeImportTimesheets(roleName)) {
    importChildren.push({
      id: 'historical-timesheets',
      label: 'Historical Timesheets',
      path: '/admin/imports/historical-timesheets',
      icon: UploadFileIcon,
    });
    importChildren.push({
      id: 'import-history',
      label: 'Import History',
      path: '/admin/imports/historical-timesheets#history',
      icon: HistoryIcon,
    });
  }
  importChildren.push(
    { id: 'import-customers', label: 'Customers', path: '/admin/imports', icon: BusinessIcon, comingSoon: true },
    { id: 'import-users', label: 'Users', path: '/admin/imports', icon: PeopleIcon, comingSoon: true },
    {
      id: 'import-templates',
      label: 'Project Templates',
      path: '/admin/imports',
      icon: ViewTimelineIcon,
      comingSoon: true,
    },
  );

  const visibleImportChildren = importChildren.filter((item) => !item.comingSoon);

  const sections: AdminNavItem[] = [
    { id: 'dashboard', label: 'Dashboard', path: '/admin/dashboard', icon: DashboardIcon },
    { id: 'create', label: 'Create', path: '/admin/create', icon: AddIcon },
    { id: 'manage', label: 'Manage', icon: ManageAccountsIcon, children: manageChildren },
    {
      id: 'imports',
      label: 'Imports',
      path: '/admin/imports',
      icon: UploadFileIcon,
      children: visibleImportChildren,
    },
    { id: 'reports', label: 'Reports', path: '/admin/reports', icon: AssessmentIcon },
    { id: 'settings', label: 'Settings', path: '/admin/settings', icon: SettingsIcon },
  ];

  if (isAdmin(roleName)) {
    sections.push({ id: 'system', label: 'System', path: '/admin/system', icon: BuildIcon });
  }

  return sections;
}

export const ADMIN_CREATE_ACTIONS: AdminCreateAction[] = [
  {
    id: 'user',
    title: 'New User',
    description: 'Add a team member with role and access.',
    icon: PeopleIcon,
    path: '/admin/users?create=1',
  },
  {
    id: 'customer',
    title: 'New Customer',
    description: 'Register a customer organisation.',
    icon: BusinessIcon,
    path: '/admin/customers?create=1',
  },
  {
    id: 'contact',
    title: 'New Contact',
    description: 'Add a customer contact person.',
    icon: ContactPhoneIcon,
    path: '/admin/contacts?create=1',
  },
  {
    id: 'team',
    title: 'New Team',
    description: 'Create an engineering team.',
    icon: GroupsIcon,
    path: '/admin/teams?create=1',
  },
  {
    id: 'project-template',
    title: 'New Project Template',
    description: 'Define milestones for a project type.',
    icon: ViewTimelineIcon,
    path: '/admin/project-templates/new',
  },
  {
    id: 'project-type',
    title: 'New Project Type',
    description: 'Add a project classification.',
    icon: TypeSpecimenIcon,
    path: '/admin/project-types?create=1',
  },
  {
    id: 'stream',
    title: 'New Stream',
    description: 'Add a design stream or discipline.',
    icon: AccountTreeIcon,
    path: '/admin/streams?create=1',
  },
  {
    id: 'task-type',
    title: 'New Task Type',
    description: 'Configure productive task categories.',
    icon: CategoryIcon,
    path: '/admin/task-types?create=1',
  },
  {
    id: 'np-code',
    title: 'New Non Productive Code',
    description: 'Add an NP code for timesheets.',
    icon: BlockIcon,
    path: '/admin/non-productive-codes?create=1',
  },
  {
    id: 'role',
    title: 'New Role',
    description: 'Define a security role.',
    icon: SecurityIcon,
    path: '/admin/roles?create=1',
  },
];

export const ADMIN_MANAGE_ITEMS: AdminHubItem[] = [
  { id: 'users', title: 'Users', description: 'Accounts, roles, and teams.', icon: PeopleIcon, path: '/admin/users' },
  { id: 'customers', title: 'Customers', description: 'Customer organisations.', icon: BusinessIcon, path: '/admin/customers' },
  { id: 'contacts', title: 'Contacts', description: 'Customer contact people.', icon: ContactPhoneIcon, path: '/admin/contacts' },
  { id: 'teams', title: 'Teams', description: 'Engineering teams and leads.', icon: GroupsIcon, path: '/admin/teams' },
  { id: 'project-types', title: 'Project Types', description: 'Project classifications.', icon: TypeSpecimenIcon, path: '/admin/project-types' },
  { id: 'project-templates', title: 'Project Templates', description: 'Milestone workflows.', icon: ViewTimelineIcon, path: '/admin/project-templates' },
  { id: 'streams', title: 'Streams', description: 'Design streams.', icon: AccountTreeIcon, path: '/admin/streams' },
  { id: 'task-types', title: 'Task Types', description: 'Productive task types.', icon: CategoryIcon, path: '/admin/task-types' },
  { id: 'roles', title: 'Roles', description: 'Security roles.', icon: SecurityIcon, path: '/admin/roles' },
  { id: 'np-codes', title: 'Non Productive Codes', description: 'NP codes for timesheets.', icon: BlockIcon, path: '/admin/non-productive-codes' },
  { id: 'departments', title: 'Departments', description: 'Organisation departments.', icon: GroupsIcon, path: '/admin/settings/departments' },
  { id: 'settings', title: 'Settings Hub', description: 'All configuration pages.', icon: SettingsIcon, path: '/admin/settings' },
];

export const ADMIN_IMPORT_ITEMS = (roleName: string): AdminHubItem[] => {
  const items: AdminHubItem[] = [];
  if (canSeeImportProjects(roleName)) {
    items.push({
      id: 'historical-projects',
      title: 'Historical Projects',
      description: 'Import legacy project workbooks.',
      icon: FolderSharedIcon,
      path: '/admin/imports/historical-projects',
    });
  }
  if (canSeeImportTimesheets(roleName)) {
    items.push({
      id: 'historical-timesheets',
      title: 'Historical Timesheets',
      description: 'Import designer timesheet files.',
      icon: UploadFileIcon,
      path: '/admin/imports/historical-timesheets',
    });
    items.push({
      id: 'import-logs',
      title: 'Import Logs',
      description: 'View timesheet import history.',
      icon: HistoryIcon,
      path: '/admin/imports/historical-timesheets#history',
    });
  }
  items.push(
    { id: 'customers-import', title: 'Customers', description: 'Bulk customer import.', icon: BusinessIcon, path: '/admin/imports', comingSoon: true },
    { id: 'users-import', title: 'Users', description: 'Bulk user import.', icon: PeopleIcon, path: '/admin/imports', comingSoon: true },
    { id: 'templates-import', title: 'Project Templates', description: 'Template import.', icon: ViewTimelineIcon, path: '/admin/imports', comingSoon: true },
  );
  return items.filter((item) => !item.comingSoon);
};

export const ADMIN_REPORT_ITEMS: AdminHubItem[] = [
  { id: 'import-history', title: 'Import History', description: 'Historical import audit.', icon: HistoryIcon, path: '/admin/imports/historical-timesheets#history' },
];

export const ADMIN_SETTINGS_ITEMS: AdminHubItem[] = [
  { id: 'general', title: 'General Settings', description: 'Core application options.', icon: SettingsIcon, path: '/admin/settings' },
  { id: 'company', title: 'Company Profile', description: 'Organisation profile.', icon: BusinessIcon, path: '/admin/settings/company' },
  { id: 'working-hours', title: 'Working Hours', description: 'Standard working hours.', icon: SettingsIcon, path: '/admin/settings/company' },
  { id: 'holidays', title: 'Holiday Calendar', description: 'Non-working days.', icon: SettingsIcon, path: '/admin/settings/holidays' },
  { id: 'departments', title: 'Departments', description: 'Organisation departments.', icon: GroupsIcon, path: '/admin/settings/departments' },
  { id: 'paths', title: 'File Paths', description: 'Project folder templates.', icon: FolderSharedIcon, path: '/admin/settings/paths' },
  { id: 'notifications', title: 'Notifications', description: 'System notification rules.', icon: AssessmentIcon, path: '/admin/settings/notifications' },
];

export const ADMIN_SYSTEM_ITEMS: AdminHubItem[] = [
  { id: 'version', title: 'Version Information', description: 'Build and release details.', icon: SettingsIcon, path: '/admin/system' },
];
