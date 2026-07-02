import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Grid,
  LinearProgress,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import FolderOutlinedIcon from '@mui/icons-material/FolderOutlined';
import AssignmentOutlinedIcon from '@mui/icons-material/AssignmentOutlined';
import TimelineOutlinedIcon from '@mui/icons-material/TimelineOutlined';
import ModeCommentOutlinedIcon from '@mui/icons-material/ModeCommentOutlined';
import FolderCopyOutlinedIcon from '@mui/icons-material/FolderCopyOutlined';
import type { ProjectTableRow } from './ProjectTable';
import {
  DrawerQuickActions,
  ExecutionStatusBadge,
  FormField,
  FormSection,
  HealthBadge,
  PriorityBadge,
  ProjectStageBadge,
  RecordDetailDrawer,
} from '../ui/design-system';
import { ProsohmButton } from '../ui/ProsohmButton';
import { LoadingState } from '../common/LoadingState';
import { cloneProject, commandCenterQueryKeys, fetchProjectCommandCenter } from '../../api/commandCenter';
import { getProjectDetail } from '../../services/projectService';
import { QUERY_STALE_TIMES } from '../../config/queryConfig';
import { useToast } from '../../context/ToastContext';
import { formatCellValue, formatDate, formatDateTime, formatDisplayValue, formatNumber, formatStatus } from '../../utils/format';
import { formatProjectStageDisplay } from '../../utils/projectCommandCenter';
import { projectQueryKeys } from '../../services/projectService';

interface ProjectRecordDrawerProps {
  project: ProjectTableRow | null;
  open: boolean;
  onClose: () => void;
  onEdit: (project: ProjectTableRow) => void;
  onArchive?: (projectId: string) => void;
  canArchive?: boolean;
}

function displayValue(value: string | null | undefined): string {
  return formatCellValue(value) || '—';
}

export function ProjectRecordDrawer({
  project,
  open,
  onClose,
  onEdit,
  onArchive,
  canArchive = false,
}: ProjectRecordDrawerProps) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [historyExpanded, setHistoryExpanded] = useState(false);

  const detailQuery = useQuery({
    queryKey: projectQueryKeys.detail(project?.id ?? ''),
    queryFn: () => getProjectDetail(project!.id),
    enabled: open && Boolean(project?.id),
    staleTime: QUERY_STALE_TIMES.projects,
  });

  const commandCenterQuery = useQuery({
    queryKey: commandCenterQueryKeys.detail(project?.id ?? ''),
    queryFn: () => fetchProjectCommandCenter(project!.id),
    enabled: open && Boolean(project?.id),
    staleTime: QUERY_STALE_TIMES.projects,
  });

  const cloneMutation = useMutation({
    mutationFn: () => cloneProject(project!.id),
    onSuccess: () => {
      showSuccess('Project duplicated.');
      void queryClient.invalidateQueries({ queryKey: projectQueryKeys.all });
    },
    onError: (error: Error) => showError(error.message),
  });

  const cc = commandCenterQuery.data;
  const detail = detailQuery.data;
  const health = detail?.health ?? project?.health;

  const recentActivity = useMemo(() => {
    const items: Array<{ id: string; title: string; detail: string; when: string }> = [];
    cc?.decisions.slice(0, 5).forEach((decision) => {
      items.push({
        id: decision.id,
        title: formatStatus(decision.category),
        detail: decision.comment,
        when: decision.created_at,
      });
    });
    cc?.recent_timesheets.slice(0, 3).forEach((entry) => {
      items.push({
        id: entry.id,
        title: 'Timesheet entry',
        detail: `${formatNumber(entry.hours)} hrs · ${formatStatus(entry.work_category)}`,
        when: entry.entry_date,
      });
    });
    return items.sort((a, b) => new Date(b.when).getTime() - new Date(a.when).getTime()).slice(0, 8);
  }, [cc?.decisions, cc?.recent_timesheets]);

  return (
    <RecordDetailDrawer
      open={open}
      onClose={onClose}
      title={project?.tool_number ?? 'Project'}
      subtitle={project?.part_description}
      icon={FolderOutlinedIcon}
      status={
        project ? (
          <>
            <ProjectStageBadge stage={project.project_stage} />
            <ExecutionStatusBadge status={project.execution_status} />
            <PriorityBadge priority={project.priority ?? 'medium'} />
            {health ? <HealthBadge health={health} /> : null}
          </>
        ) : null
      }
      quickActions={
        project ? (
          <DrawerQuickActions>
            <ProsohmButton buttonVariant="outlined" size="small" onClick={() => onEdit(project)}>
              Edit
            </ProsohmButton>
            {canArchive && onArchive ? (
              <ProsohmButton
                buttonVariant="outlined"
                size="small"
                onClick={() => onArchive(project.id)}
              >
                Archive
              </ProsohmButton>
            ) : null}
            <ProsohmButton
              buttonVariant="outlined"
              size="small"
              loading={cloneMutation.isPending}
              onClick={() => cloneMutation.mutate()}
            >
              Duplicate
            </ProsohmButton>
            <ProsohmButton
              buttonVariant="outlined"
              size="small"
              onClick={() => showSuccess('Export will be available in a future release.')}
            >
              Export
            </ProsohmButton>
          </DrawerQuickActions>
        ) : null
      }
    >
      {!project ? null : detailQuery.isPending && commandCenterQuery.isPending ? (
        <LoadingState message="Loading project details…" />
      ) : (
        <Stack spacing={3}>
          <FormSection title="Overview" icon={FolderOutlinedIcon}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField label="Tool Number" value={project.tool_number} slotProps={{ input: { readOnly: true } }} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField label="Project Code" value={project.code} slotProps={{ input: { readOnly: true } }} />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <FormField label="Part Description" value={project.part_description} slotProps={{ input: { readOnly: true } }} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField label="Customer" value={displayValue(project.customerName)} slotProps={{ input: { readOnly: true } }} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField label="Due Date" value={formatDate(project.due_date) || '—'} slotProps={{ input: { readOnly: true } }} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField label="Project Stage" value={formatProjectStageDisplay(project)} slotProps={{ input: { readOnly: true } }} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="Current Milestone"
                value={displayValue(project.current_milestone ?? cc?.header.current_milestone)}
                slotProps={{ input: { readOnly: true } }}
              />
            </Grid>
          </FormSection>

          <FormSection title="Assignments" icon={AssignmentOutlinedIcon}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField label="Team" value={displayValue(project.teamName)} slotProps={{ input: { readOnly: true } }} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField label="Design Leader" value={displayValue(project.designLeaderName)} slotProps={{ input: { readOnly: true } }} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField label="Designer" value={displayValue(project.designerName)} slotProps={{ input: { readOnly: true } }} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField label="Surfacer" value={displayValue(project.surfacerName)} slotProps={{ input: { readOnly: true } }} />
            </Grid>
          </FormSection>

          <FormSection title="Milestones" icon={TimelineOutlinedIcon}>
            {commandCenterQuery.isPending ? (
              <Typography variant="body2" color="text.secondary">Loading milestones…</Typography>
            ) : !cc?.timeline.length ? (
              <Typography variant="body2" color="text.secondary">No milestones defined.</Typography>
            ) : (
              <>
                {detail ? (
                  <Box sx={{ mb: 2 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography variant="body2" color="text.secondary">Progress</Typography>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {formatNumber(detail.milestone_summary.progress_percent)}%
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={detail.milestone_summary.progress_percent}
                      sx={{ height: 8, borderRadius: 4 }}
                    />
                  </Box>
                ) : null}
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Milestone</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell>Due</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {cc.timeline.slice(0, 8).map((step) => (
                      <TableRow key={step.milestone_id ?? step.name}>
                        <TableCell>{formatDisplayValue(step.name)}</TableCell>
                        <TableCell>{formatStatus(step.status)}</TableCell>
                        <TableCell>{formatDate(step.due_date) || '—'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </>
            )}
          </FormSection>

          <FormSection title="Hours" icon={TimelineOutlinedIcon}>
            <Grid size={{ xs: 12, sm: 3 }}>
              <FormField label="Quoted Hours" value={formatNumber(project.quoted_hours)} slotProps={{ input: { readOnly: true } }} />
            </Grid>
            <Grid size={{ xs: 12, sm: 3 }}>
              <FormField
                label="Actual Hours"
                value={formatNumber(detail?.hours.actual ?? project.actual_hours)}
                slotProps={{ input: { readOnly: true } }}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 3 }}>
              <FormField
                label="Remaining"
                value={formatNumber(detail?.hours.remaining ?? cc?.kpis.remaining_hours ?? 0)}
                slotProps={{ input: { readOnly: true } }}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 3 }}>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                <Typography variant="caption" color="text.secondary">Health</Typography>
                {health ? <HealthBadge health={health} /> : '—'}
              </Box>
            </Grid>
          </FormSection>

          <FormSection title="Comments" icon={ModeCommentOutlinedIcon}>
            <FormField
              label="Project Notes"
              value={displayValue(project.notes)}
              multiline
              minRows={2}
              slotProps={{ input: { readOnly: true } }}
            />
            {!cc?.decisions.length ? (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                No decision log entries yet.
              </Typography>
            ) : (
              <Stack spacing={1.5} sx={{ mt: 2 }}>
                {cc.decisions.slice(0, 5).map((decision) => (
                  <Box key={decision.id}>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {formatStatus(decision.category)}
                      {decision.user_name ? ` · ${decision.user_name}` : ''}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">{decision.comment}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {formatDateTime(decision.created_at)}
                    </Typography>
                  </Box>
                ))}
              </Stack>
            )}
          </FormSection>

          <FormSection title="Activity Timeline" icon={TimelineOutlinedIcon}>
            {!recentActivity.length ? (
              <Typography variant="body2" color="text.secondary">No recent activity.</Typography>
            ) : (
              <Stack spacing={1.5}>
                {recentActivity.map((item) => (
                  <Box key={item.id}>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>{item.title}</Typography>
                    <Typography variant="body2" color="text.secondary">{item.detail}</Typography>
                    <Typography variant="caption" color="text.secondary">{formatDateTime(item.when)}</Typography>
                  </Box>
                ))}
              </Stack>
            )}
          </FormSection>

          <FormSection title="Files" icon={FolderCopyOutlinedIcon}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              File management will be available in a future release.
            </Typography>
            {cc?.folders.project_folder_path ? (
              <FormField
                label="Project Folder"
                value={cc.folders.project_folder_path}
                slotProps={{ input: { readOnly: true } }}
              />
            ) : (
              <Typography variant="body2" color="text.secondary">No folder paths configured.</Typography>
            )}
          </FormSection>

          <Accordion
            expanded={historyExpanded}
            onChange={(_, expanded) => setHistoryExpanded(expanded)}
            disableGutters
            elevation={0}
            sx={{ border: 1, borderColor: 'divider', borderRadius: 2, '&:before': { display: 'none' } }}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle2">History</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <FormField label="Created" value={formatDateTime(project.created_at) || '—'} slotProps={{ input: { readOnly: true } }} />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <FormField label="Updated" value={formatDateTime(project.updated_at) || '—'} slotProps={{ input: { readOnly: true } }} />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <FormField label="Completed" value={formatDateTime(project.completed_at) || '—'} slotProps={{ input: { readOnly: true } }} />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <FormField label="Archived" value={formatDateTime(project.archived_at) || '—'} slotProps={{ input: { readOnly: true } }} />
                </Grid>
              </Grid>
            </AccordionDetails>
          </Accordion>
        </Stack>
      )}
    </RecordDetailDrawer>
  );
}
