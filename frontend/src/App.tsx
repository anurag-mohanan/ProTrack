import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { CssBaseline, ThemeProvider } from '@mui/material';
import AppLayout from './components/layout/AppLayout';
import DashboardPage from './pages/DashboardPage';
import ProjectsPage from './pages/ProjectsPage';
import MilestonesPage from './pages/MilestonesPage';
import TimesheetsPage from './pages/TimesheetsPage';
import ResourcePlanningPage from './pages/ResourcePlanningPage';
import CustomersPage from './pages/CustomersPage';
import StreamsPage from './pages/StreamsPage';
import UsersPage from './pages/UsersPage';
import ReportsPage from './pages/ReportsPage';
import { theme } from './theme/theme';

export default function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="projects" element={<ProjectsPage />} />
            <Route path="milestones" element={<MilestonesPage />} />
            <Route path="timesheets" element={<TimesheetsPage />} />
            <Route path="resource-planning" element={<ResourcePlanningPage />} />
            <Route path="customers" element={<CustomersPage />} />
            <Route path="streams" element={<StreamsPage />} />
            <Route path="users" element={<UsersPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}
