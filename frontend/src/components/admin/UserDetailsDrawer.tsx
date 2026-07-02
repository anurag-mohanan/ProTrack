import { useMemo, useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Avatar,
  Box,
  Chip,
  Grid,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import PersonIcon from '@mui/icons-material/Person';
import BadgeOutlinedIcon from '@mui/icons-material/BadgeOutlined';
import TimelineOutlinedIcon from '@mui/icons-material/TimelineOutlined';
import StickyNote2OutlinedIcon from '@mui/icons-material/StickyNote2Outlined';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { fetchUserProfileDetail } from '../../api/resources';
import { getProjects } from '../../services/projectService';
import type { User } from '../../types';
import type { Activity } from '../../types/Workflow';
import type { Timesheet } from '../../types/Timesheet';
import {
  DrawerQuickActions,
  FormField,
  FormSection,
  RecordDetailDrawer,
} from '../ui/design-system';
import { ProsohmButton } from '../ui/ProsohmButton';
import { LoadingState } from '../common/LoadingState';
import {
  formatCellValue,
  formatDate,
  formatDateTime,
  formatEmploymentType,
  formatNumber,
  formatStatus,
  formatUserWorkload,
  userDisplayName,
  userInitials,
} from '../../utils/format';

interface UserDetailsDrawerProps {
  user: User | null;
  open: boolean;
  onClose: () => void;
  roleLabel: string;
  isAdmin: boolean;
  onEdit: (user: User) => void;
  onDelete: (user: User) => void;
  onResetPassword: (user: User) => void;
  onSetTemporaryPassword: (user: User) => void;
  onForcePasswordChange: (user: User) => void;
  onUnlockUser: (user: User) => void;
  onToggleActive: (user: User) => void;
  onArchive: (user: User) => void;
  onImpersonate: (user: User) => void;
  canImpersonate: boolean;
}

function displayValue(value: string | null | undefined): string {
  const formatted = formatCellValue(value);
  return formatted || '—';
}

export function UserDetailsDrawer({
  user,
  open,
  onClose,
  roleLabel,
  isAdmin,
  onEdit,
  onDelete,
  onResetPassword,
  onSetTemporaryPassword,
  onForcePasswordChange,
  onUnlockUser,
  onToggleActive,
  onArchive,
  onImpersonate,
  canImpersonate,
}: UserDetailsDrawerProps) {
  const [auditExpanded, setAuditExpanded] = useState(false);

  const profileQuery = useQuery({
    queryKey: ['users', user?.id, 'profile'],
    queryFn: () => fetchUserProfileDetail(user!.id),
    enabled: open && Boolean(user?.id),
  });

  const projectsQuery = useQuery({
    queryKey: ['users', user?.id, 'assigned-projects'],
    queryFn: async () => {
      const [asDesigner, asLeader] = await Promise.all([
        getProjects({ designer_id: user!.id, limit: 50, lifecycle: 'active' }),
        getProjects({ design_leader_id: user!.id, limit: 50, lifecycle: 'active' }),
      ]);
      const merged = new Map([...asDesigner, ...asLeader].map((project) => [project.id, project]));
      return [...merged.values()];
    },
    enabled: open && Boolean(user?.id),
  });

  const timesheetsQuery = useQuery({
    queryKey: ['users', user?.id, 'timesheets'],
    queryFn: async () => {
      const { data } = await apiClient.get<Timesheet[]>(
        `/timesheets?user_id=${user!.id}&limit=5`,
      );
      return data;
    },
    enabled: open && Boolean(user?.id),
  });

  const activityQuery = useQuery({
    queryKey: ['users', user?.id, 'activity'],
    queryFn: async () => {
      const { data } = await apiClient.get<Activity[]>(
        `/activities?user_id=${user!.id}&limit=8`,
      );
      return data;
    },
    enabled: open && Boolean(user?.id),
  });

  const profile = profileQuery.data;
  const fullName = user ? userDisplayName(user) : '';
  const workloadLabel = useMemo(
    () => formatUserWorkload(user?.active_projects_count ?? profile?.summary.active_projects),
    [profile?.summary.active_projects, user?.active_projects_count],
  );

  return (
    <RecordDetailDrawer
      open={open}
      onClose={onClose}
      title={fullName || 'User'}
      subtitle={displayValue(user?.designation) !== '—' ? user?.designation ?? undefined : roleLabel}
      icon={PersonIcon}
      status={
        user ? (
          <>
            <Chip
              label={user.is_active ? 'Active' : 'Inactive'}
              size="small"
              color={user.is_active ? 'success' : 'default'}
            />
            <Chip label={roleLabel} size="small" color="primary" variant="outlined" />
          </>
        ) : null
      }
      quickActions={
        user ? (
          <DrawerQuickActions>
            <ProsohmButton
              buttonVariant="outlined"
              size="small"
              onClick={() => onEdit(user)}
            >
              Edit
            </ProsohmButton>
            {isAdmin ? (
              <ProsohmButton
                buttonVariant="danger"
                size="small"
                onClick={() => onDelete(user)}
              >
                Delete
              </ProsohmButton>
            ) : null}
          </DrawerQuickActions>
        ) : null
      }
    >
      {!user ? null : profileQuery.isPending ? (
        <LoadingState message="Loading user details…" />
      ) : (
        <Stack spacing={3}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Avatar sx={{ width: 72, height: 72, bgcolor: 'primary.main', fontSize: '1.5rem' }}>
              {userInitials(user)}
            </Avatar>
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 700 }}>
                {fullName}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {user.email}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                {workloadLabel}
              </Typography>
            </Box>
          </Box>

          <FormSection title="Overview" icon={PersonIcon}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField label="Designation" value={displayValue(user.designation)} slotProps={{ input: { readOnly: true } }} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField label="Role" value={roleLabel} slotProps={{ input: { readOnly: true } }} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField label="Department" value={displayValue(user.department_name)} slotProps={{ input: { readOnly: true } }} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField label="Team" value={displayValue(user.team_name)} slotProps={{ input: { readOnly: true } }} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField label="Email" value={user.email} slotProps={{ input: { readOnly: true } }} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField label="Phone" value={displayValue(user.phone)} slotProps={{ input: { readOnly: true } }} />
            </Grid>
          </FormSection>

          <FormSection title="Employment" icon={BadgeOutlinedIcon}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="Employment Type"
                value={displayValue(formatEmploymentType(user.employment_type ?? profile?.employment_type))}
                slotProps={{ input: { readOnly: true } }}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="Working Hours"
                value={
                  profile
                    ? `${formatNumber(profile.working_hours_per_day)} hrs/day · ${profile.working_days}`
                    : displayValue(String(user.working_hours_per_day ?? ''))
                }
                slotProps={{ input: { readOnly: true } }}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField label="Manager" value={displayValue(user.manager_name ?? profile?.manager_name)} slotProps={{ input: { readOnly: true } }} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="Skills"
                value={
                  profile?.skills?.length
                    ? profile.skills
                        .map((skill) =>
                          skill.skill_name
                            ? `${skill.skill_name} (${formatStatus(skill.proficiency)})`
                            : formatStatus(skill.proficiency),
                        )
                        .join(', ')
                    : displayValue(user.skill_level ? formatStatus(user.skill_level) : null)
                }
                slotProps={{ input: { readOnly: true } }}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="Capacity"
                value={displayValue(
                  user.max_allocation_percent != null
                    ? `${user.max_allocation_percent}%`
                    : null,
                )}
                slotProps={{ input: { readOnly: true } }}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="Current Utilization"
                value={
                  profile
                    ? `${formatNumber(Number(profile.summary.utilization_percent))}%`
                    : '—'
                }
                slotProps={{ input: { readOnly: true } }}
              />
            </Grid>
          </FormSection>

          <FormSection title="Assigned Projects" icon={BadgeOutlinedIcon}>
            {projectsQuery.isPending ? (
              <Typography variant="body2" color="text.secondary">
                Loading projects…
              </Typography>
            ) : !projectsQuery.data?.length ? (
              <Typography variant="body2" color="text.secondary">
                No active project assignments.
              </Typography>
            ) : (
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Tool #</TableCell>
                    <TableCell>Description</TableCell>
                    <TableCell>Due</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {projectsQuery.data.slice(0, 8).map((project) => (
                    <TableRow key={project.id}>
                      <TableCell>{project.tool_number}</TableCell>
                      <TableCell>{formatCellValue(project.part_description) || '—'}</TableCell>
                      <TableCell>{formatDate(project.due_date) || '—'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </FormSection>

          <FormSection title="Recent Timesheets" icon={TimelineOutlinedIcon}>
            {timesheetsQuery.isPending ? (
              <Typography variant="body2" color="text.secondary">
                Loading timesheets…
              </Typography>
            ) : !timesheetsQuery.data?.length ? (
              <Typography variant="body2" color="text.secondary">
                No timesheets recorded.
              </Typography>
            ) : (
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Week Starting</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Submitted</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {timesheetsQuery.data.map((sheet) => (
                    <TableRow key={sheet.id}>
                      <TableCell>{formatDate(sheet.week_start) || '—'}</TableCell>
                      <TableCell>{formatStatus(sheet.status)}</TableCell>
                      <TableCell>{formatDateTime(sheet.submitted_at) || '—'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </FormSection>

          <FormSection title="Recent Activity" icon={TimelineOutlinedIcon}>
            {activityQuery.isPending ? (
              <Typography variant="body2" color="text.secondary">
                Loading activity…
              </Typography>
            ) : !activityQuery.data?.length ? (
              <Typography variant="body2" color="text.secondary">
                No recent activity.
              </Typography>
            ) : (
              <Stack spacing={1.5}>
                {activityQuery.data.map((item) => (
                  <Box key={item.id}>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {formatStatus(item.action)}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {formatDateTime(item.created_at)}
                      {item.new_value ? ` · ${formatCellValue(item.new_value)}` : ''}
                    </Typography>
                  </Box>
                ))}
              </Stack>
            )}
          </FormSection>

          <FormSection title="Notes" icon={StickyNote2OutlinedIcon}>
            <Typography variant="body2" color="text.secondary">
              No notes recorded.
            </Typography>
          </FormSection>

          <FormSection title="Account Management" icon={PersonIcon}>
            <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1 }}>
              <ProsohmButton buttonVariant="outlined" size="small" onClick={() => onResetPassword(user)}>
                Reset Password
              </ProsohmButton>
              <ProsohmButton
                buttonVariant="outlined"
                size="small"
                onClick={() => onSetTemporaryPassword(user)}
              >
                Set Temporary Password
              </ProsohmButton>
              <ProsohmButton buttonVariant="outlined" size="small" onClick={() => onForcePasswordChange(user)}>
                Force Password Change
              </ProsohmButton>
              {user.is_locked ? (
                <ProsohmButton buttonVariant="outlined" size="small" onClick={() => onUnlockUser(user)}>
                  Unlock User
                </ProsohmButton>
              ) : null}
              <ProsohmButton buttonVariant="outlined" size="small" onClick={() => onToggleActive(user)}>
                {user.is_active ? 'Deactivate' : 'Activate'}
              </ProsohmButton>
              <ProsohmButton buttonVariant="outlined" size="small" disabled title="Coming soon">
                Generate Password Reset Link
              </ProsohmButton>
              {isAdmin ? (
                <ProsohmButton buttonVariant="outlined" size="small" onClick={() => onArchive(user)}>
                  Archive
                </ProsohmButton>
              ) : null}
              {canImpersonate ? (
                <ProsohmButton buttonVariant="outlined" size="small" onClick={() => onImpersonate(user)}>
                  Login As User
                </ProsohmButton>
              ) : null}
            </Stack>
          </FormSection>

          <Accordion
            expanded={auditExpanded}
            onChange={(_, expanded) => setAuditExpanded(expanded)}
            disableGutters
            elevation={0}
            sx={{ border: 1, borderColor: 'divider', borderRadius: 2, '&:before': { display: 'none' } }}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle2">Audit Information</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <FormField label="Last Login" value={formatDateTime(user.last_login) || '—'} slotProps={{ input: { readOnly: true } }} />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <FormField
                    label="Password Changed"
                    value={user.must_change_password ? 'Required on next login' : 'Yes'}
                    slotProps={{ input: { readOnly: true } }}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <FormField
                    label="Account Status"
                    value={
                      user.is_locked
                        ? `Locked (${user.failed_login_count ?? 0} failed attempts)`
                        : user.is_active
                          ? 'Active'
                          : 'Inactive'
                    }
                    slotProps={{ input: { readOnly: true } }}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <FormField label="Created" value={formatDateTime(user.created_at) || '—'} slotProps={{ input: { readOnly: true } }} />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <FormField label="Updated" value={formatDateTime(user.updated_at) || '—'} slotProps={{ input: { readOnly: true } }} />
                </Grid>
              </Grid>
            </AccordionDetails>
          </Accordion>
        </Stack>
      )}
    </RecordDetailDrawer>
  );
}
