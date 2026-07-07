import { Box, Typography } from '@mui/material';
import { useAuth } from '../../context/AuthContext';
import { designTokens } from '../../theme/designTokens';
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
        gap: 1.5,
        mb: 1.5,
        p: 2,
        borderRadius: `${designTokens.radius.lg}px`,
        bgcolor: designTokens.semantic.card,
        border: '1px solid',
        borderColor: 'divider',
        boxShadow: designTokens.elevation.card,
        backgroundImage: `linear-gradient(135deg, ${designTokens.semantic.primarySoft} 0%, ${designTokens.semantic.card} 55%)`,
      }}
    >
      <Box>
        <Typography variant="overline" sx={{ color: 'text.secondary', letterSpacing: '0.08em' }}>
          Engineering Command Center
        </Typography>
        <Typography variant="h5" sx={{ fontWeight: 800, letterSpacing: '-0.03em', mb: 0.25 }}>
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
