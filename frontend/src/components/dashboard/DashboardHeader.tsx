import { Box, Typography } from '@mui/material';
import { useAuth } from '../../context/AuthContext';
import { formatDate } from '../../utils/format';
import { buildDashboardSummaryLine } from '../../utils/buildDashboardSummaryLine';
import type { DashboardSummary } from '../../types';
import { DashboardQuickActions } from './DashboardQuickActions';

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good Morning';
  if (hour < 17) return 'Good Afternoon';
  return 'Good Evening';
}

interface DashboardHeaderProps {
  summary?: DashboardSummary;
  onNewProject: () => void;
  onTimesheet: () => void;
  onCustomer: () => void;
  onUser: () => void;
  onReports: () => void;
  onAdministration: () => void;
  onImportTimesheets: () => void;
  onApproveTimesheets: () => void;
  onAssignDesigners: () => void;
  onOpenCurrentProject: () => void;
}

export function DashboardHeader({
  summary,
  onNewProject,
  onTimesheet,
  onCustomer,
  onUser,
  onReports,
  onAdministration,
  onImportTimesheets,
  onApproveTimesheets,
  onAssignDesigners,
  onOpenCurrentProject,
}: DashboardHeaderProps) {
  const { displayName } = useAuth();
  const summaryLine = buildDashboardSummaryLine(summary);

  return (
    <Box sx={{ mb: 1.25 }}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexDirection: { xs: 'column', md: 'row' },
          gap: 1,
          minHeight: 72,
        }}
      >
        <Box sx={{ minWidth: 0 }}>
          <Typography
            variant="subtitle1"
            sx={{ fontWeight: 800, letterSpacing: '-0.02em', lineHeight: 1.2 }}
          >
            {getGreeting()}, {displayName}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
            {formatDate(new Date().toISOString().slice(0, 10))}
          </Typography>
          <Typography
            variant="caption"
            sx={{ fontWeight: 700, color: 'text.secondary', letterSpacing: '0.06em', mt: 0.25 }}
          >
            Engineering Overview
          </Typography>
          {summaryLine ? (
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ display: 'block', mt: 0.5, lineHeight: 1.4 }}
            >
              {summaryLine}
            </Typography>
          ) : null}
        </Box>

        <DashboardQuickActions
          onNewProject={onNewProject}
          onTimesheet={onTimesheet}
          onCustomer={onCustomer}
          onUser={onUser}
          onReports={onReports}
          onAdministration={onAdministration}
          onImportTimesheets={onImportTimesheets}
          onApproveTimesheets={onApproveTimesheets}
          onAssignDesigners={onAssignDesigners}
          onOpenCurrentProject={onOpenCurrentProject}
        />
      </Box>
    </Box>
  );
}
