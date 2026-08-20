import { Suspense, lazy, type ReactNode } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './context/AuthContext';
import { AppThemeProvider } from './context/AppThemeProvider';
import { ToastProvider } from './context/ToastContext';
import { LoadingState } from './components/common/LoadingState';
import { GlobalDragAutoScroll } from './components/common/GlobalDragAutoScroll';
import { queryClient } from './lib/queryClient';
import { MainLayout } from './layouts/MainLayout';
import { AdminLayout } from './layouts/AdminLayout';
import { DashboardPage } from './pages/DashboardPage';
import { ChangePasswordPage } from './pages/ChangePasswordPage';
import { LoginPage } from './pages/LoginPage';
import { SsoCallbackPage } from './pages/SsoCallbackPage';
import { ProjectWorkspacePage } from './components/projects/workspace/ProjectWorkspace';
import { ArchivedProjectsPage } from './pages/ArchivedProjectsPage';
import { ProjectsPage } from './pages/ProjectsPage';
import { ReportsPage } from './pages/ReportsPage';
import { TimesheetsPage } from './pages/TimesheetsPage';
import { ApprovalsInboxPage } from './pages/ApprovalsInboxPage';
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
  canViewOrganizationChart,
  ROLES,
} from './utils/permissions';
import { ModuleRoute } from './routes/ModuleRoute';
import {
  MODULE_ARCHIVED_PROJECTS,
  MODULE_FINANCIAL_PLANNING,
  MODULE_HUMAN_RESOURCES,
  MODULE_IT_OPERATIONS,
  MODULE_PERFORMANCE,
  MODULE_TICKETS,
  MODULE_PLANNING_BOARD,
  MODULE_CALENDAR,
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
const PerformancePage = lazy(() => import('./pages/PerformancePage'));
const HelpDeskPage = lazy(() => import('./pages/HelpDeskPage'));
const OnboardingPage = lazy(() => import('./pages/OnboardingPage'));
const TrainingPage = lazy(() => import('./pages/TrainingPage'));
const ExitProcessPage = lazy(() => import('./pages/ExitProcessPage'));
const PastEmployeesPage = lazy(() => import('./pages/PastEmployeesPage'));
const HrProcessAuditPage = lazy(() =>
  import('./pages/HrProcessAuditPage').then((module) => ({
    default: module.HrProcessAuditPage,
  })),
);
const OrganizationChartPage = lazy(() => import('./pages/OrganizationChartPage'));
const AnalyticsHubPage = lazy(() =>
  import('./pages/AnalyticsHubPage').then((module) => ({
    default: module.AnalyticsHubPage,
  })),
);
const ITDashboardPage = lazy(() =>
  import('./pages/it/ITDashboardPage').then((module) => ({
    default: module.ITDashboardPage,
  })),
);
const ITAssetsPage = lazy(() =>
  import('./pages/it/ITAssetsPage').then((module) => ({
    default: module.ITAssetsPage,
  })),
);
const ITComputersPage = lazy(() =>
  import('./pages/it/ITComputersPage').then((module) => ({
    default: module.ITComputersPage,
  })),
);
const ITNetworksPage = lazy(() =>
  import('./pages/it/ITNetworksPage').then((module) => ({
    default: module.ITNetworksPage,
  })),
);
const ITRequestsPage = lazy(() =>
  import('./pages/it/ITRequestsPage').then((module) => ({
    default: module.ITRequestsPage,
  })),
);
const ITSettingsPage = lazy(() =>
  import('./pages/it/ITSettingsPage').then((module) => ({
    default: module.ITSettingsPage,
  })),
);
const ITDataImportPage = lazy(() =>
  import('./pages/it/ITDataImportPage').then((module) => ({
    default: module.ITDataImportPage,
  })),
);
const ITReturnedAssetsPage = lazy(() =>
  import('./pages/it/ITReturnedAssetsPage').then((module) => ({
    default: module.ITReturnedAssetsPage,
  })),
);
const ITReportsPage = lazy(() =>
  import('./pages/it/ITReportsPage').then((module) => ({
    default: module.ITReportsPage,
  })),
);
const ITUsersPage = lazy(() =>
  import('./pages/it/ITUsersPage').then((module) => ({
    default: module.ITUsersPage,
  })),
);
const ITModulePlaceholderPage = lazy(() =>
  import('./pages/it/ITModulePlaceholderPage').then((module) => ({
    default: module.ITModulePlaceholderPage,
  })),
);

const AdminCreatePage = lazy(() => import('./pages/admin/AdminCreatePage'));
const AdminDashboardPage = lazy(() => import('./pages/admin/AdminDashboardPage'));
const AdminImportsPage = lazy(() => import('./pages/admin/AdminImportsPage'));
const HistoryDataImportPage = lazy(() => import('./pages/admin/HistoryDataImportPage'));
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
const SecurityCenterPage = lazy(() => import('./pages/admin/SecurityCenterPage'));
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
const RoleHierarchyAdminPage = lazy(() => import('./pages/admin/RoleHierarchyPage'));
const OrgDepartmentsAdminPage = lazy(() => import('./pages/admin/OrgDepartmentsPage'));
const TicketRoutingAdminPage = lazy(() => import('./pages/admin/TicketRoutingPage'));
const StreamsAdminPage = lazy(() => import('./pages/admin/StreamsPage'));
const WorkstreamsAdminPage = lazy(() => import('./pages/admin/WorkstreamsPage'));
const WorkingModelsAdminPage = lazy(() => import('./pages/admin/WorkingModelsPage'));
const TeamsAdminPage = lazy(() => import('./pages/admin/TeamsPage'));
const TaskTypesAdminPage = lazy(() => import('./pages/admin/TaskTypesPage'));
const NonProductiveCodesAdminPage = lazy(() => import('./pages/admin/NonProductiveCodesPage'));
const UsersAdminPage = lazy(() => import('./pages/admin/UsersPage'));
const BrandingPage = lazy(() => import('./pages/admin/BrandingPage'));
const CommercialSettingsPage = lazy(() => import('./pages/admin/CommercialSettingsPage'));
const CommercialReadinessPage = lazy(() => import('./pages/admin/CommercialReadinessPage'));
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
            <GlobalDragAutoScroll />
            <BrowserRouter>
              <Routes>
                <Route element={<PublicRoute />}>
                  <Route path="/login" element={<LoginPage />} />
                  <Route path="/login/sso" element={<SsoCallbackPage />} />
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
                    <Route path="/approvals" element={<ApprovalsInboxPage />} />
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
                      <Route path="/knowledge" element={<KnowledgeBasePage />} />
                      <Route path="/executive-wall" element={<ExecutiveWallPage />} />
                    </Route>
                    <Route element={<ModuleRoute module={MODULE_CALENDAR} />}>
                      <Route
                        path="/calendar"
                        element={
                          <Suspense fallback={<LoadingState message="Loading calendar…" />}>
                            <EngineeringCalendarPage />
                          </Suspense>
                        }
                      />
                    </Route>
                    <Route element={<RoleRoute allowed={canViewWorkload} />}>
                      <Route path="/workload" element={<WorkloadPage />} />
                    </Route>
                    <Route element={<ModuleRoute module={MODULE_PERFORMANCE} />}>
                      <Route
                        path="/performance"
                        element={
                          <Suspense fallback={<LoadingState message="Loading performance…" />}>
                            <PerformancePage />
                          </Suspense>
                        }
                      />
                    </Route>
                    <Route path="/performance-reviews" element={<Navigate to="/performance?section=annual" replace />} />
                    <Route element={<ModuleRoute module={MODULE_TICKETS} />}>
                      <Route
                        path="/help-desk"
                        element={
                          <Suspense fallback={<LoadingState message="Loading help desk…" />}>
                            <HelpDeskPage />
                          </Suspense>
                        }
                      />
                    </Route>
                    <Route element={<RoleRoute allowed={canViewOrganizationChart} />}>
                      <Route
                        path="/organization"
                        element={
                          <Suspense fallback={<LoadingState message="Loading organization chart…" />}>
                            <OrganizationChartPage />
                          </Suspense>
                        }
                      />
                    </Route>
                    <Route path="/admin/organization-chart" element={<Navigate to="/organization" replace />} />
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
                      <Route
                        path="/hr/onboarding"
                        element={
                          <Suspense fallback={<LoadingState message="Loading onboarding…" />}>
                            <OnboardingPage />
                          </Suspense>
                        }
                      />
                      <Route
                        path="/hr/training"
                        element={
                          <Suspense fallback={<LoadingState message="Loading training…" />}>
                            <TrainingPage />
                          </Suspense>
                        }
                      />
                      <Route
                        path="/hr/exit-process"
                        element={
                          <Suspense fallback={<LoadingState message="Loading exit process…" />}>
                            <ExitProcessPage />
                          </Suspense>
                        }
                      />
                      <Route
                        path="/hr/past-employees"
                        element={
                          <Suspense fallback={<LoadingState message="Loading past employees…" />}>
                            <PastEmployeesPage />
                          </Suspense>
                        }
                      />
                      <Route
                        path="/hr/process-audit"
                        element={
                          <Suspense fallback={<LoadingState message="Loading process audit…" />}>
                            <HrProcessAuditPage />
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
                    <Route element={<ModuleRoute module={MODULE_IT_OPERATIONS} />}>
                      <Route
                        path="/it"
                        element={
                          <Suspense fallback={<LoadingState message="Loading IT operations…" />}>
                            <ITDashboardPage />
                          </Suspense>
                        }
                      />
                      <Route
                        path="/it/assets"
                        element={
                          <Suspense fallback={<LoadingState message="Loading IT assets…" />}>
                            <ITAssetsPage />
                          </Suspense>
                        }
                      />
                      <Route
                        path="/it/returned-assets"
                        element={
                          <Suspense fallback={<LoadingState message="Loading returned assets…" />}>
                            <ITReturnedAssetsPage />
                          </Suspense>
                        }
                      />
                      <Route
                        path="/it/computers"
                        element={
                          <Suspense fallback={<LoadingState message="Loading computers…" />}>
                            <ITComputersPage />
                          </Suspense>
                        }
                      />
                      <Route
                        path="/it/networks"
                        element={
                          <Suspense fallback={<LoadingState message="Loading networks…" />}>
                            <ITNetworksPage />
                          </Suspense>
                        }
                      />
                      <Route
                        path="/it/accounts"
                        element={
                          <Suspense fallback={<LoadingState message="Loading IT users…" />}>
                            <ITUsersPage />
                          </Suspense>
                        }
                      />
                      <Route
                        path="/it/software"
                        element={
                          <Suspense fallback={<LoadingState message="Loading software…" />}>
                            <ITModulePlaceholderPage
                              title="Software & Licenses"
                              description="Software catalog, license pools, and assignments."
                            />
                          </Suspense>
                        }
                      />
                      <Route
                        path="/it/requests"
                        element={
                          <Suspense fallback={<LoadingState message="Loading IT requests…" />}>
                            <ITRequestsPage />
                          </Suspense>
                        }
                      />
                      <Route
                        path="/it/maintenance"
                        element={
                          <Suspense fallback={<LoadingState message="Loading maintenance…" />}>
                            <ITModulePlaceholderPage
                              title="Maintenance"
                              description="Maintenance schedules and warranty follow-up."
                            />
                          </Suspense>
                        }
                      />
                      <Route
                        path="/it/suppliers"
                        element={
                          <Suspense fallback={<LoadingState message="Loading suppliers…" />}>
                            <ITModulePlaceholderPage
                              title="Suppliers"
                              description="IT and inventory vendor master data."
                            />
                          </Suspense>
                        }
                      />
                      <Route
                        path="/it/reports"
                        element={
                          <Suspense fallback={<LoadingState message="Loading IT reports…" />}>
                            <ITReportsPage />
                          </Suspense>
                        }
                      />
                      <Route
                        path="/it/settings"
                        element={
                          <Suspense fallback={<LoadingState message="Loading IT settings…" />}>
                            <ITSettingsPage />
                          </Suspense>
                        }
                      />
                      <Route
                        path="/it/data-import"
                        element={
                          <Suspense fallback={<LoadingState message="Loading IT Data Import…" />}>
                            <ITDataImportPage />
                          </Suspense>
                        }
                      />
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
                        path="/admin/imports/history"
                        element={
                          <LazyAdminPage>
                            <HistoryDataImportPage />
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
                        path="/admin/settings/commercial"
                        element={
                          <LazyAdminPage>
                            <CommercialSettingsPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/settings/commercial-readiness"
                        element={
                          <LazyAdminPage>
                            <CommercialReadinessPage />
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
                      <Route
                        path="/admin/security"
                        element={
                          <LazyAdminPage>
                            <SecurityCenterPage />
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
                        path="/admin/workstreams"
                        element={
                          <LazyAdminPage>
                            <WorkstreamsAdminPage />
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
                        path="/admin/role-hierarchy"
                        element={
                          <LazyAdminPage>
                            <RoleHierarchyAdminPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/org-departments"
                        element={
                          <LazyAdminPage>
                            <OrgDepartmentsAdminPage />
                          </LazyAdminPage>
                        }
                      />
                      <Route
                        path="/admin/ticket-routing"
                        element={
                          <LazyAdminPage>
                            <TicketRoutingAdminPage />
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
