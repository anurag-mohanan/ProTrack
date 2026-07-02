import { Suspense, lazy, type ReactNode } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './context/AuthContext';
import { AppThemeProvider } from './context/AppThemeProvider';
import { ToastProvider } from './context/ToastContext';
import { LoadingState } from './components/common/LoadingState';
import { queryClient } from './lib/queryClient';
import { MainLayout } from './layouts/MainLayout';
import { DashboardPage } from './pages/DashboardPage';
import { ChangePasswordPage } from './pages/ChangePasswordPage';
import { LoginPage } from './pages/LoginPage';
import { ProjectDetailPage } from './pages/ProjectDetailPage';
import { ArchivedProjectsPage } from './pages/ArchivedProjectsPage';
import { ProjectsPage } from './pages/ProjectsPage';
import { ReportsPage } from './pages/ReportsPage';
import { TimesheetEntryPage } from './pages/TimesheetEntryPage';
import { TimesheetsPage } from './pages/TimesheetsPage';
import { ResourcePlanningPage } from './pages/ResourcePlanningPage';
import { WorkloadPage } from './pages/WorkloadPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { AdminRoute } from './routes/AdminRoute';
import { RoleRoute } from './routes/RoleRoute';
import { ProtectedRoute, PublicRoute, RequirePasswordChangedRoute } from './routes/ProtectedRoute';
import {
  canImportHistoricalProjects,
  canImportHistoricalTimesheets,
  canViewReports,
  ROLES,
} from './utils/permissions';

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
const AdminSystemPage = lazy(() => import('./pages/admin/AdminSystemPage'));
const ContactsAdminPage = lazy(() => import('./pages/admin/ContactsPage'));
const CustomersAdminPage = lazy(() => import('./pages/admin/CustomersPage'));
const DeletedProjectsAdminPage = lazy(() => import('./pages/admin/DeletedProjectsPage'));
const DeletedUsersAdminPage = lazy(() => import('./pages/admin/DeletedUsersPage'));
const ProjectTemplatesAdminPage = lazy(() => import('./pages/admin/ProjectTemplatesPage'));
const ProjectTemplateEditorPage = lazy(() => import('./pages/admin/ProjectTemplateEditorPage'));
const ProjectTypesAdminPage = lazy(() => import('./pages/admin/ProjectTypesPage'));
const RolesAdminPage = lazy(() => import('./pages/admin/RolesPage'));
const StreamsAdminPage = lazy(() => import('./pages/admin/StreamsPage'));
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
  if (!canImportHistoricalProjects(user?.role_name ?? '')) {
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
  if (!canImportHistoricalTimesheets(user?.role_name ?? '')) {
    return <Navigate to="/admin/dashboard" replace />;
  }
  return (
    <LazyAdmin>
      <HistoricalTimesheetImportPage />
    </LazyAdmin>
  );
}

function AdminSystemRoute() {
  const { user } = useAuth();
  if (user?.role_name !== ROLES.ADMIN) {
    return <Navigate to="/admin/dashboard" replace />;
  }
  return (
    <LazyAdmin>
      <AdminSystemPage />
    </LazyAdmin>
  );
}

function LazyAdminPage({ children }: { children: ReactNode }) {
  return <LazyAdmin>{children}</LazyAdmin>;
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
                  <Route path="/change-password" element={<ChangePasswordPage />} />
                  <Route element={<RequirePasswordChangedRoute />}>
                    <Route element={<MainLayout />}>
                    <Route path="/dashboard" element={<DashboardPage />} />
                    <Route path="/projects" element={<ProjectsPage />} />
                    <Route path="/projects/archived" element={<ArchivedProjectsPage />} />
                    <Route path="/projects/:id" element={<ProjectDetailPage />} />
                    <Route path="/timesheets" element={<TimesheetsPage />} />
                    <Route
                      path="/profile"
                      element={
                        <Suspense fallback={<LoadingState message="Loading profile…" />}>
                          <UserProfilePage />
                        </Suspense>
                      }
                    />
                    <Route
                      path="/timesheets/:timesheetId/entries/new"
                      element={<TimesheetEntryPage />}
                    />
                    <Route element={<RoleRoute allowed={canViewReports} />}>
                      <Route path="/workload" element={<WorkloadPage />} />
                      <Route path="/resource-planning" element={<ResourcePlanningPage />} />
                      <Route path="/reports" element={<ReportsPage />} />
                    </Route>

                    <Route element={<AdminRoute />}>
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
                      <Route path="/admin/system" element={<AdminSystemRoute />} />

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
                        path="/admin/project-templates/new"
                        element={
                          <LazyAdminPage>
                            <ProjectTemplateEditorPage />
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

                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="*" element={<NotFoundPage />} />
              </Routes>
            </BrowserRouter>
          </ToastProvider>
        </AppThemeProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
