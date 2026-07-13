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
  canApproveTimesheet,
  canCreateCustomer,
  canCreateProject,
  canImportHistoricalTimesheets,
  canManageUsers,
  canViewReports,
  canEnterOwnTimesheet,
  getDashboardRoleGroup,
  isDesignLeaderRole,
  isReadOnlyRole,
  userHasModule,
  accessContextFromUser,
} from '../../utils/permissions';
import { MODULE_TIMESHEETS } from '../../config/accessControl';

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
  const access = accessContextFromUser(user);
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
        {canViewReports(access) ? (
          <Button variant="outlined" size="small" startIcon={<AssessmentIcon />} onClick={onReports} sx={buttonSx}>
            Reports
          </Button>
        ) : null}
      </Box>
    );
  }

  if (group === 'staff') {
    return (
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
        {userHasModule(access, MODULE_TIMESHEETS) && canEnterOwnTimesheet(access) ? (
          <>
            <Button variant="contained" size="small" startIcon={<ScheduleIcon />} onClick={onTimesheet} sx={buttonSx}>
              Submit Timesheet
            </Button>
            <Button variant="outlined" size="small" startIcon={<TaskAltIcon />} onClick={onTimesheet} sx={buttonSx}>
              Update Milestone
            </Button>
          </>
        ) : null}
        <Button variant="outlined" size="small" startIcon={<FolderOpenIcon />} onClick={onOpenCurrentProject} sx={buttonSx}>
          Open Current Project
        </Button>
      </Box>
    );
  }

  if (isDesignLeaderRole(roleName)) {
    return (
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
        {canCreateProject(access) ? (
          <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={onNewProject} sx={buttonSx}>
            Create Project
          </Button>
        ) : null}
        {canApproveTimesheet('submitted', access) ? (
          <Button variant="outlined" size="small" startIcon={<ScheduleIcon />} onClick={onApproveTimesheets} sx={buttonSx}>
            Approve Team Timesheets
          </Button>
        ) : null}
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
      {canCreateProject(access) ? (
        <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={onNewProject} sx={buttonSx}>
          Create Project
        </Button>
      ) : null}
      {canManageUsers(access) ? (
        <Button variant="outlined" size="small" startIcon={<PersonAddIcon />} onClick={onUser} sx={buttonSx}>
          Create User
        </Button>
      ) : null}
      {canCreateCustomer(access) ? (
        <Button variant="outlined" size="small" startIcon={<BusinessIcon />} onClick={onCustomer} sx={buttonSx}>
          Create Customer
        </Button>
      ) : null}
      {canImportHistoricalTimesheets(access) ? (
        <Button variant="outlined" size="small" startIcon={<UploadFileIcon />} onClick={onImportTimesheets} sx={buttonSx}>
          Import Timesheets
        </Button>
      ) : null}
      {canViewReports(access) ? (
        <Button variant="outlined" size="small" startIcon={<AssessmentIcon />} onClick={onReports} sx={buttonSx}>
          Reports
        </Button>
      ) : null}
      {canAccessAdministration(access) ? (
        <Button variant="outlined" size="small" startIcon={<AdminPanelSettingsIcon />} onClick={onAdministration} sx={buttonSx}>
          System Administration
        </Button>
      ) : null}
    </Box>
  );
}
