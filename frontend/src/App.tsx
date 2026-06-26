import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { CssBaseline, ThemeProvider } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { MainLayout } from './layouts/MainLayout';
import ContactsAdminPage from './pages/admin/ContactsPage';
import CustomersAdminPage from './pages/admin/CustomersPage';
import DeletedProjectsAdminPage from './pages/admin/DeletedProjectsPage';
import ProjectTemplatesAdminPage from './pages/admin/ProjectTemplatesPage';
import ProjectTemplateEditorPage from './pages/admin/ProjectTemplateEditorPage';
import ProjectTypesAdminPage from './pages/admin/ProjectTypesPage';
import RolesAdminPage from './pages/admin/RolesPage';
import StreamsAdminPage from './pages/admin/StreamsPage';
import SystemSettingsPage from './pages/admin/SystemSettingsPage';
import TaskTypesAdminPage from './pages/admin/TaskTypesPage';
import UsersAdminPage from './pages/admin/UsersPage';
import { DashboardPage } from './pages/DashboardPage';
import { HistoricalImportPage } from './pages/HistoricalImportPage';
import { LoginPage } from './pages/LoginPage';
import { ProjectDetailPage } from './pages/ProjectDetailPage';
import { ArchivedProjectsPage } from './pages/ArchivedProjectsPage';
import { ProjectsPage } from './pages/ProjectsPage';
import { ReportsPage } from './pages/ReportsPage';
import { TimesheetEntryPage } from './pages/TimesheetEntryPage';
import { TimesheetsPage } from './pages/TimesheetsPage';
import { WorkloadPage } from './pages/WorkloadPage';
import { AdminRoute } from './routes/AdminRoute';
import { ProtectedRoute, PublicRoute } from './routes/ProtectedRoute';
import { theme } from './theme/theme';
import { useAuth } from './context/AuthContext';
import { canImportHistoricalProjects } from './utils/permissions';

function AdminHistoricalImportRoute() {
  const { user } = useAuth();
  if (!canImportHistoricalProjects(user?.role_name ?? '')) {
    return <Navigate to="/dashboard" replace />;
  }
  return <HistoricalImportPage />;
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <AuthProvider>
          <ToastProvider>
            <BrowserRouter>
              <Routes>
                <Route element={<PublicRoute />}>
                  <Route path="/login" element={<LoginPage />} />
                </Route>

                <Route element={<ProtectedRoute />}>
                  <Route element={<MainLayout />}>
                    <Route path="/dashboard" element={<DashboardPage />} />
                    <Route path="/projects" element={<ProjectsPage />} />
                    <Route path="/projects/archived" element={<ArchivedProjectsPage />} />
                    <Route path="/projects/:id" element={<ProjectDetailPage />} />
                    <Route path="/timesheets" element={<TimesheetsPage />} />
                    <Route
                      path="/timesheets/:timesheetId/entries/new"
                      element={<TimesheetEntryPage />}
                    />
                    <Route path="/workload" element={<WorkloadPage />} />
                    <Route path="/reports" element={<ReportsPage />} />

                    <Route element={<AdminRoute />}>
                      <Route path="/admin/users" element={<UsersAdminPage />} />
                      <Route path="/admin/customers" element={<CustomersAdminPage />} />
                      <Route path="/admin/contacts" element={<ContactsAdminPage />} />
                      <Route path="/admin/streams" element={<StreamsAdminPage />} />
                      <Route path="/admin/task-types" element={<TaskTypesAdminPage />} />
                      <Route path="/admin/project-types" element={<ProjectTypesAdminPage />} />
                      <Route
                        path="/admin/project-templates"
                        element={<ProjectTemplatesAdminPage />}
                      />
                      <Route
                        path="/admin/project-templates/:templateId"
                        element={<ProjectTemplateEditorPage />}
                      />
                      <Route path="/admin/roles" element={<RolesAdminPage />} />
                      <Route path="/admin/settings" element={<SystemSettingsPage />} />
                      <Route
                        path="/admin/deleted-projects"
                        element={<DeletedProjectsAdminPage />}
                      />
                      <Route
                        path="/admin/import-historical-projects"
                        element={<AdminHistoricalImportRoute />}
                      />
                    </Route>
                  </Route>
                </Route>

                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Routes>
            </BrowserRouter>
          </ToastProvider>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
