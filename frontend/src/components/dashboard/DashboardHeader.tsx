import { Box, Button, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import BusinessIcon from '@mui/icons-material/Business';
import ScheduleIcon from '@mui/icons-material/Schedule';
import { useAuth } from '../../context/AuthContext';
import { canAccessAdministration, canEditProject } from '../../utils/permissions';
import { formatDate } from '../../utils/format';

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
}

export function DashboardHeader({
  onNewProject,
  onTimesheet,
  onCustomer,
  onUser,
}: DashboardHeaderProps) {
  const { user, displayName } = useAuth();
  const roleName = user?.role_name ?? '';
  const firstName = displayName.split(' ')[0] ?? displayName;
  const showAdminActions = canAccessAdministration(roleName);
  const showNewProject = canEditProject(roleName);

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: { xs: 'flex-start', md: 'center' },
        flexDirection: { xs: 'column', md: 'row' },
        gap: 2.5,
        mb: 3.5,
      }}
    >
      <Box>
        <Typography
          variant="h4"
          sx={{ fontWeight: 700, letterSpacing: '-0.03em', mb: 0.5 }}
        >
          {getGreeting()}, {firstName}
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ mb: 0.25 }}>
          {roleName || 'Team Member'}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {formatDate(new Date().toISOString().slice(0, 10))}
        </Typography>
      </Box>

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
        {showNewProject ? (
          <Button
            variant="outlined"
            size="small"
            startIcon={<AddIcon />}
            onClick={onNewProject}
            sx={{ borderRadius: 2, textTransform: 'none', fontWeight: 600 }}
          >
            New Project
          </Button>
        ) : null}
        <Button
          variant="outlined"
          size="small"
          startIcon={<ScheduleIcon />}
          onClick={onTimesheet}
          sx={{ borderRadius: 2, textTransform: 'none', fontWeight: 600 }}
        >
          Timesheet
        </Button>
        {showAdminActions ? (
          <>
            <Button
              variant="outlined"
              size="small"
              startIcon={<BusinessIcon />}
              onClick={onCustomer}
              sx={{ borderRadius: 2, textTransform: 'none', fontWeight: 600 }}
            >
              Customer
            </Button>
            <Button
              variant="outlined"
              size="small"
              startIcon={<PersonAddIcon />}
              onClick={onUser}
              sx={{ borderRadius: 2, textTransform: 'none', fontWeight: 600 }}
            >
              User
            </Button>
          </>
        ) : null}
      </Box>
    </Box>
  );
}
