import { Box, Typography } from '@mui/material';
import { useAuth } from '../../context/AuthContext';
import { formatDate } from '../../utils/format';
import { DashboardQuickActions } from './DashboardQuickActions';

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good Morning';
  if (hour < 17) return 'Good Afternoon';
  return 'Good Evening';
}

interface DashboardHeaderProps {
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

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: { xs: 'flex-start', md: 'center' },
        flexDirection: { xs: 'column', md: 'row' },
        gap: 2.5,
        mb: 4,
        p: 3,
        borderRadius: 3,
        bgcolor: 'background.paper',
        border: '1px solid',
        borderColor: 'divider',
        boxShadow: (theme) => theme.palette.prosohm.shadowCard,
      }}
    >
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 700, letterSpacing: '-0.03em', mb: 0.5 }}>
          {getGreeting()}, {displayName}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {formatDate(new Date().toISOString().slice(0, 10))}
        </Typography>
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
  );
}
