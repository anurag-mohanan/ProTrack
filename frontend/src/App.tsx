import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { CssBaseline, ThemeProvider } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { MainLayout } from './layouts/MainLayout';
import { DashboardPage } from './pages/DashboardPage';
import { LoginPage } from './pages/LoginPage';
import { ProjectDetailPage } from './pages/ProjectDetailPage';
import { ProjectsPage } from './pages/ProjectsPage';
import { ReportsPage } from './pages/ReportsPage';
import { TimesheetEntryPage } from './pages/TimesheetEntryPage';
import { TimesheetsPage } from './pages/TimesheetsPage';
import { WorkloadPage } from './pages/WorkloadPage';
import { ProtectedRoute, PublicRoute } from './routes/ProtectedRoute';
import { theme } from './theme/theme';

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
                  <Route path="/projects/:id" element={<ProjectDetailPage />} />
                  <Route path="/timesheets" element={<TimesheetsPage />} />
                  <Route
                    path="/timesheets/:timesheetId/entries/new"
                    element={<TimesheetEntryPage />}
                  />
                  <Route path="/workload" element={<WorkloadPage />} />
                  <Route path="/reports" element={<ReportsPage />} />
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
