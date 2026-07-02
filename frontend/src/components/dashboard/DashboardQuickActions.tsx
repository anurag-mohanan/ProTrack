import { Box, Button } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import BusinessIcon from '@mui/icons-material/Business';
import ScheduleIcon from '@mui/icons-material/Schedule';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import AssessmentIcon from '@mui/icons-material/Assessment';
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings';
import GroupsIcon from '@mui/icons-material/Groups';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import { useAuth } from '../../context/AuthContext';
import {
  canAccessAdministration,
  canCreateCustomer,
  canCreateProject,
  canImportHistoricalTimesheets,
  canManageUsers,
  getDashboardRoleGroup,
  isDesignLeaderRole,
  isReadOnlyRole,
} from '../../utils/permissions';

interface DashboardQuickActionsProps {
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

export function DashboardQuickActions({
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
}: DashboardQuickActionsProps) {
  const { user } = useAuth();
  const roleName = user?.role_name ?? '';
  const group = getDashboardRoleGroup(roleName);

  const buttonSx = {
    borderRadius: 2,
    textTransform: 'none',
    fontWeight: 600,
  } as const;

  if (isReadOnlyRole(roleName)) {
    return (
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
        <Button variant="outlined" size="small" startIcon={<AssessmentIcon />} onClick={onReports} sx={buttonSx}>
          Reports
        </Button>
      </Box>
    );
  }

  if (group === 'staff') {
    return (
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
        <Button variant="contained" size="small" startIcon={<ScheduleIcon />} onClick={onTimesheet} sx={buttonSx}>
          Submit Timesheet
        </Button>
        <Button variant="outlined" size="small" startIcon={<TaskAltIcon />} onClick={onTimesheet} sx={buttonSx}>
          Update Milestone
        </Button>
        <Button variant="outlined" size="small" startIcon={<FolderOpenIcon />} onClick={onOpenCurrentProject} sx={buttonSx}>
          Open Current Project
        </Button>
      </Box>
    );
  }

  if (isDesignLeaderRole(roleName)) {
    return (
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
        {canCreateProject(roleName) ? (
          <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={onNewProject} sx={buttonSx}>
            Create Project
          </Button>
        ) : null}
        <Button variant="outlined" size="small" startIcon={<ScheduleIcon />} onClick={onApproveTimesheets} sx={buttonSx}>
          Approve Team Timesheets
        </Button>
        <Button variant="outlined" size="small" startIcon={<GroupsIcon />} onClick={onAssignDesigners} sx={buttonSx}>
          Assign Designers
        </Button>
        <Button variant="outlined" size="small" startIcon={<TaskAltIcon />} onClick={onNewProject} sx={buttonSx}>
          Update Milestones
        </Button>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
      {canCreateProject(roleName) ? (
        <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={onNewProject} sx={buttonSx}>
          Create Project
        </Button>
      ) : null}
      {canManageUsers(roleName) ? (
        <Button variant="outlined" size="small" startIcon={<PersonAddIcon />} onClick={onUser} sx={buttonSx}>
          Create User
        </Button>
      ) : null}
      {canCreateCustomer(roleName) ? (
        <Button variant="outlined" size="small" startIcon={<BusinessIcon />} onClick={onCustomer} sx={buttonSx}>
          Create Customer
        </Button>
      ) : null}
      {canImportHistoricalTimesheets(roleName) ? (
        <Button variant="outlined" size="small" startIcon={<UploadFileIcon />} onClick={onImportTimesheets} sx={buttonSx}>
          Import Timesheets
        </Button>
      ) : null}
      <Button variant="outlined" size="small" startIcon={<AssessmentIcon />} onClick={onReports} sx={buttonSx}>
        Reports
      </Button>
      {canAccessAdministration(roleName) ? (
        <Button variant="outlined" size="small" startIcon={<AdminPanelSettingsIcon />} onClick={onAdministration} sx={buttonSx}>
          System Administration
        </Button>
      ) : null}
    </Box>
  );
}
