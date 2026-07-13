import { Suspense, lazy, type ReactNode } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './context/AuthContext';
import { AppThemeProvider } from './context/AppThemeProvider';
import { ToastProvider } from './context/ToastContext';
import { LoadingState } from './components/common/LoadingState';
import { queryClient } from './lib/queryClient';
import { MainLayout } from './layouts/MainLayout';
import { AdminLayout } from './layouts/AdminLayout';
import { DashboardPage } from './pages/DashboardPage';
import { ChangePasswordPage } from './pages/ChangePasswordPage';
import { LoginPage } from './pages/LoginPage';
import { ProjectWorkspacePage } from './components/projects/workspace/ProjectWorkspace';
import { ArchivedProjectsPage } from './pages/ArchivedProjectsPage';
import { ProjectsPage } from './pages/ProjectsPage';
import { ReportsPage } from './pages/ReportsPage';
import { TimesheetsPage } from './pages/TimesheetsPage';
import { ResourcePlanningPage } from './pages/ResourcePlanningPage';
import { WorkloadPage } from './pages/WorkloadPage';
import { ExecutiveWallPage } from './pages/ExecutiveWallPage';
import { KnowledgeBasePage } from './pages/KnowledgeBasePage';
import HelpCenterPage from './pages/HelpCenterPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { AdminRoute } from './routes/AdminRoute';
import { AdminPortalRoute } from './routes/AdminPortalRoute';
import { RoleRoute } from './routes/RoleRoute';
import { ProtectedRoute, PublicRoute, RequirePasswordChangedRoute, ChangePasswordGate } from './routes/ProtectedRoute';
import { DefaultHomeRedirect, PlanningBoardGate } from './routes/PlanningBoardGate';
import {
  accessContextFromUser,
  canImportHistoricalProjects,
  canImportHistoricalTimesheets,
  canViewReports,
  canViewResourcePlanning,
  canViewWorkload,
  ROLES,
} from './utils/permissions';
import { ModuleRoute } from './routes/ModuleRoute';
import {
  MODULE_ARCHIVED_PROJECTS,
  MODULE_FINANCIAL_PLANNING,
  MODULE_HUMAN_RESOURCES,
  MODULE_PLANNING_BOARD,
  MODULE_PROJECTS,
  MODULE_REPORTS_ANALYTICS,
  MODULE_TIMESHEETS,
} from './config/accessControl';
import { PlanningBoardLayout } from './layouts/PlanningBoardLayout';
import PlanningBoardPage from './pages/PlanningBoardPage';
const FinanceDashboardPage = lazy(() =>
  import('./pages/FinanceDashboardPage').then((module) => ({
    default: module.FinanceDashboardPage,
  })),
);
const HrDashboardPage = lazy(() =>
  import('./pages/HrDashboardPage').then((module) => ({
    default: module.HrDashboardPage,
  })),
);
const AnalyticsHubPage = lazy(() =>
  import('./pages/AnalyticsHubPage').then((module) => ({
    default: module.AnalyticsHubPage,
  })),
);

const AdminCreatePage = lazy(() => import('./pages/admin/AdminCreatePage'));
const AdminDashboardPage = lazy(() => import('./pages/admin/AdminDashboardPage'));
const AdminImportsPage = lazy(() => import('./pages/admin/AdminImportsPage'));
const AdminManageHubPage = lazy(() => import('./pages/admin/AdminManageHubPage'));
const AdminReportsPage = lazy(() => import('./pages/admin/AdminReportsPage'));
const AdminSettingsHubPage = lazy(() => import('./pages/admin/AdminSettingsHubPage'));
const CompanyProfilePage = lazy(() => import('./pages/admin/CompanyProfilePage'));
const HolidayCalendarPage = lazy(() => import('./pages/admin/HolidayCalendarPage'));
const DepartmentsPage = lazy(() => import('./pages/admin/DepartmentsPage'));
const FilePathSettingsPage = lazy(() => import('./pages/admin/FilePathSettingsPage'));
const NotificationSettingsPage = lazy(() => import('./pages/admin/NotificationSettingsPage'));
const EmailSettingsPage = lazy(() => import('./pages/admin/EmailSettingsPage'));
const EmailTemplatesPage = lazy(() => import('./pages/admin/EmailTemplatesPage'));
const EmailQueuePage = lazy(() => import('./pages/admin/EmailQueuePage'));
const AuditLogsPage = lazy(() => import('./pages/admin/AuditLogsPage'));
const BackupRestorePage = lazy(() => import('./pages/admin/BackupRestorePage'));
const SecuritySettingsPage = lazy(() => import('./pages/admin/SecuritySettingsPage'));
const EngineeringCalendarPage = lazy(() => import('./pages/EngineeringCalendarPage'));
const AdminAuditHubPage = lazy(() => import('./pages/admin/AdminAuditHubPage'));
const AdminSystemPage = lazy(() => import('./pages/admin/AdminSystemPage'));
const DeveloperDiagnosticsPage = lazy(() => import('./pages/admin/DeveloperDiagnosticsPage'));
const ContactsAdminPage = lazy(() => import('./pages/admin/ContactsPage'));
const CustomersAdminPage = lazy(() => import('./pages/admin/CustomersPage'));
const DeletedProjectsAdminPage = lazy(() => import('./pages/admin/DeletedProjectsPage'));
const DeletedUsersAdminPage = lazy(() => import('./pages/admin/DeletedUsersPage'));
const RebuildTimesheetStatsAdminPage = lazy(
  () => import('./pages/admin/RebuildTimesheetStatsPage'),
);
const DeletedTimesheetEntriesAdminPage = lazy(
  () => import('./pages/admin/DeletedTimesheetEntriesPage'),
);
const ProjectTemplatesAdminPage = lazy(() => import('./pages/admin/ProjectTemplatesPage'));
const ProjectTemplateEditorPage = lazy(() => import('./pages/admin/ProjectTemplateEditorPage'));
const ProjectTypesAdminPage = lazy(() => import('./pages/admin/ProjectTypesPage'));
const RolesAdminPage = lazy(() => import('./pages/admin/RolesPage'));
const StreamsAdminPage = lazy(() => import('./pages/admin/StreamsPage'));
const WorkingModelsAdminPage = lazy(() => import('./pages/admin/WorkingModelsPage'));
const TeamsAdminPage = lazy(() => import('./pages/admin/TeamsPage'));
const TaskTypesAdminPage = lazy(() => import('./pages/admin/TaskTypesPage'));
const NonProductiveCodesAdminPage = lazy(() => import('./pages/admin/NonProductiveCodesPage'));
const UsersAdminPage = lazy(() => import('./pages/admin/UsersPage'));
const BrandingPage = lazy(() => import('./pages/admin/BrandingPage'));
const UserProfilePage = lazy(() => import('./pages/UserProfilePage'));
const HistoricalImportPage = lazy(() =>
  import('./pages/HistoricalImportPage').then((module) => ({
    default: module.HistoricalImportPage,
  })),
);
const HistoricalTimesheetImportPage = lazy(() =>
  import('./pages/HistoricalTimesheetImportPage').then((module) => ({
    default: module.HistoricalTimesheetImportPage,
  })),
);

function LazyAdmin({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<LoadingState message="Loading administration…" variant="skeleton" />}>
      {children}
    </Suspense>
  );
}

function AdminHistoricalImportRoute() {
  const { user } = useAuth();
  const access = accessContextFromUser(user);
  if (!canImportHistoricalProjects(access)) {
    return <Navigate to="/admin/dashboard" replace />;
  }
  return (
    <LazyAdmin>
      <HistoricalImportPage />
    </LazyAdmin>
  );
}

function AdminHistoricalTimesheetImportRoute() {
  const { user } = useAuth();
  if (!canImportHistoricalTimesheets(accessContextFromUser(user))) {
    return <Navigate to="/dashboard" replace />;
  }
  return (
    <LazyAdmin>
      <HistoricalTimesheetImportPage />
    </LazyAdmin>
  );
}

function AdminSystemRoute() {
  const { user } = useAuth();
  const role = user?.role_name ?? '';
  if (role !== ROLES.ADMIN) {
    return <Navigate to="/admin/dashboard" replace />;
  }
  return (
    <LazyAdmin>
      <AdminSystemPage />
    </LazyAdmin>
  );
}

function AdminDiagnosticsRoute() {
  const { user } = useAuth();
  const role = user?.role_name ?? '';
  if (role !== ROLES.ADMIN) {
    return <Navigate to="/admin/dashboard" replace />;
  }
  return (
    <LazyAdmin>
      <DeveloperDiagnosticsPage />
    </LazyAdmin>
  );
}

function LazyAdminPage({ children }: { children: ReactNode }) {
  return (
    <LazyAdmin>
      <AdminPortalRoute>{children}</AdminPortalRoute>
    </LazyAdmin>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AppThemeProvider>
          <ToastProvider>
            <BrowserRouter>
              <Routes>
                <Route element={<PublicRoute />}>
                  <Route path="/login" element={<LoginPage />} />
                </Route>

                <Route element={<ProtectedRoute />}>
                  <Route element={<ChangePasswordGate />}>
                    <Route path="/change-password" element={<ChangePasswordPage />} />
                  </Route>
                  <Route element={<RequirePasswordChangedRoute />}>
                    <Route element={<PlanningBoardGate />}>
                    <Route element={<ModuleRoute module={MODULE_PLANNING_BOARD} />}>
                      <Route element={<PlanningBoardLayout />}>
                        <Route path="/planning-board" element={<PlanningBoardPage />} />
                      </Route>
                    </Route>
                    <Route element={<MainLayout />}>
                    <Route path="/dashboard" element={<DashboardPage />} />
                    <Route element={<ModuleRoute module={MODULE_ARCHIVED_PROJECTS} redirectTo="/projects" />}>
                      <Route path="/projects/archived" element={<ArchivedProjectsPage />} />
                    </Route>
                    <Route element={<ModuleRoute module={MODULE_PROJECTS} />}>
                      <Route path="/projects" element={<ProjectsPage />} />
                      <Route path="/projects/:id" element={<ProjectWorkspacePage />} />
                    </Route>
                    <Route element={<ModuleRoute module={MODULE_TIMESHEETS} />}>
                      <Route path="/timesheets" element={<TimesheetsPage />} />
                      <Route path="/timesheets/month" element={<Navigate to="/timesheets" replace />} />
                      <Route
                        path="/timesheets/:timesheetId/entries/new"
                        element={<Navigate to="/timesheets" replace />}
                      />
                      <Route
                        path="/timesheets/:timesheetId/entries/:entryId"
                        element={<Navigate to="/timesheets" replace />}
                      />
                    </Route>
                    <Route
                      path="/profile"
                      element={
                        <Suspense fallback={<LoadingState message="Loading profile…" />}>
                          <UserProfilePage />
                        </Suspense>
                      }
                    />
                    <Route path="/help" element={<HelpCenterPage />} />
                    <Route element={<RoleRoute allowed={canViewReports} />}>
                      <Route path="/reports" element={<ReportsPage />} />
                      <Route
                        path="/calendar"
                        element={
                          <Suspense fallback={<LoadingState message="Loading calendar…" />}>
                            <EngineeringCalendarPage />
                          </Suspense>
                        }
                      />
                      <Route path="/knowledge" element={<KnowledgeBasePage />} />
                      <Route path="/executive-wall" element={<ExecutiveWallPage />} />
                    </Route>
                    <Route element={<RoleRoute allowed={canViewWorkload} />}>
                      <Route path="/workload" element={<WorkloadPage />} />
                    </Route>
                    <Route element={<ModuleRoute module={MODULE_FINANCIAL_PLANNING} />}>
                      <Route
                        path="/finance"
                        element={
                          <Suspense fallback={<LoadingState message="Loading financial planning…" />}>
                            <FinanceDashboardPage />
                          </Suspense>
                        }
                      />
                      <Route
                        path="/finance/*"
                        element={
                          <Suspense fallback={<LoadingState message="Loading financial planning…" />}>
                            <FinanceDashboardPage />
                          </Suspense>
                        }
                      />
                    </Route>
                    <Route element={<ModuleRoute module={MODULE_HUMAN_RESOURCES} />}>
                      <Route
                        path="/hr"
                        element={
                          <Suspense fallback={<LoadingState message="Loading HR…" />}>
                            <HrDashboardPage />
                          </Suspense>
                        }
                      />
                    </Route>
                    <Route element={<ModuleRoute module={MODULE_REPORTS_ANALYTICS} />}>
                      <Route
                        path="/analytics"
                        element={
                          <Suspense fallback={<LoadingState message="Loading analytics…" />}>
                            <AnalyticsHubPage />
                          </Suspense>
                        }
                      />
                    </Route>
                    <Route element={<RoleRoute allowed={canViewResourcePlanning} />}>
                      <Route path="/resource-planning" element={<ResourcePlanningPage />} />
                    </Route>
                    </Route>

                    <Route element={<AdminRoute />}>
                      <Route element={<AdminLayout />}>
                      <Route path="/admin" element={<Navigate to="/admin/dashboard" replace />} />
                      <Route
                        path="/admin/dashboard"
                        element={
                          <LazyAdminPage>
                            <AdminDashboardPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/create"
                        element={
                          <LazyAdminPage>
                            <AdminCreatePage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/manage"
                        element={
                          <LazyAdminPage>
                            <AdminManageHubPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/imports"
                        element={
                          <LazyAdminPage>
                            <AdminImportsPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/audit"
                        element={
                          <LazyAdminPage>
                            <AdminAuditHubPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/reports"
                        element={
                          <LazyAdminPage>
                            <AdminReportsPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/settings"
                        element={
                          <LazyAdminPage>
                            <AdminSettingsHubPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/settings/company"
                        element={
                          <LazyAdminPage>
                            <CompanyProfilePage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/settings/branding"
                        element={
                          <LazyAdminPage>
                            <BrandingPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/settings/holidays"
                        element={
                          <LazyAdminPage>
                            <HolidayCalendarPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/settings/departments"
                        element={
                          <LazyAdminPage>
                            <DepartmentsPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/settings/paths"
                        element={
                          <LazyAdminPage>
                            <FilePathSettingsPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/settings/notifications"
                        element={
                          <LazyAdminPage>
                            <NotificationSettingsPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/settings/email"
                        element={
                          <LazyAdminPage>
                            <EmailSettingsPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/settings/email-templates"
                        element={
                          <LazyAdminPage>
                            <EmailTemplatesPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/settings/email-queue"
                        element={
                          <LazyAdminPage>
                            <EmailQueuePage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/settings/backup"
                        element={
                          <LazyAdminPage>
                            <BackupRestorePage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/settings/security"
                        element={
                          <LazyAdminPage>
                            <SecuritySettingsPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/audit/logs"
                        element={
                          <LazyAdminPage>
                            <AuditLogsPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route path="/admin/system" element={<AdminSystemRoute />} />
                      <Route path="/admin/system/diagnostics" element={<AdminDiagnosticsRoute />} />

                      <Route
                        path="/admin/users"
                        element={
                          <LazyAdminPage>
                            <UsersAdminPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/customers"
                        element={
                          <LazyAdminPage>
                            <CustomersAdminPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/contacts"
                        element={
                          <LazyAdminPage>
                            <ContactsAdminPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/teams"
                        element={
                          <LazyAdminPage>
                            <TeamsAdminPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/streams"
                        element={
                          <LazyAdminPage>
                            <StreamsAdminPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/task-types"
                        element={
                          <LazyAdminPage>
                            <TaskTypesAdminPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/non-productive-codes"
                        element={
                          <LazyAdminPage>
                            <NonProductiveCodesAdminPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/working-models"
                        element={
                          <LazyAdminPage>
                            <WorkingModelsAdminPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/project-types"
                        element={
                          <LazyAdminPage>
                            <ProjectTypesAdminPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/project-templates"
                        element={
                          <LazyAdminPage>
                            <ProjectTemplatesAdminPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/project-templates/:templateId"
                        element={
                          <LazyAdminPage>
                            <ProjectTemplateEditorPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/roles"
                        element={
                          <LazyAdminPage>
                            <RolesAdminPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/deleted-projects"
                        element={
                          <LazyAdminPage>
                            <DeletedProjectsAdminPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/deleted-users"
                        element={
                          <LazyAdminPage>
                            <DeletedUsersAdminPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/deleted-timesheet-entries"
                        element={
                          <LazyAdminPage>
                            <DeletedTimesheetEntriesAdminPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/rebuild-timesheet-stats"
                        element={
                          <LazyAdminPage>
                            <RebuildTimesheetStatsAdminPage />
                          </LazyAdminPage>
                        }
                      />

                      <Route
                        path="/admin/imports/historical-projects"
                        element={<AdminHistoricalImportRoute />}
                      />
                      <Route
                        path="/admin/imports/historical-timesheets"
                        element={<AdminHistoricalTimesheetImportRoute />}
                      />
                      <Route
                        path="/admin/import-historical-projects"
                        element={<AdminHistoricalImportRoute />}
                      />
                      <Route
                        path="/admin/import-historical-timesheets"
                        element={<AdminHistoricalTimesheetImportRoute />}
                      />
                      </Route>
                    </Route>
                    </Route>
                  </Route>
                </Route>

                <Route path="/" element={<DefaultHomeRedirect />} />
                <Route path="*" element={<NotFoundPage />} />
              </Routes>
            </BrowserRouter>
          </ToastProvider>
        </AppThemeProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
