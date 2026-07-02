import { useQuery } from '@tanstack/react-query';
import { Box, Grid, LinearProgress, Typography } from '@mui/material';
import FolderOutlinedIcon from '@mui/icons-material/FolderOutlined';
import type { ProjectTableRow } from './ProjectTable';
import {
  DrawerQuickActions,
  ExecutionStatusBadge,
  FormField,
  FormSection,
  PriorityBadge,
  ProjectStageBadge,
  RecordDetailDrawer,
  HealthBadge,
} from '../ui/design-system';
import { ProsohmButton } from '../ui/ProsohmButton';
import { LoadingState } from '../common/LoadingState';
import { getProjectDetail } from '../../services/projectService';
import { QUERY_STALE_TIMES } from '../../config/queryConfig';
import { formatCellValue, formatDate, formatNumber } from '../../utils/format';

interface ProjectRecordDrawerProps {
  project: ProjectTableRow | null;
  open: boolean;
  onClose: () => void;
  onEdit: (project: ProjectTableRow) => void;
  onArchive?: (projectId: string) => void;
  canArchive?: boolean;
}

export function ProjectRecordDrawer({
  project,
  open,
  onClose,
  onEdit,
  onArchive,
  canArchive = false,
}: ProjectRecordDrawerProps) {
  const detailQuery = useQuery({
    queryKey: ['projects', 'detail', project?.id],
    queryFn: () => getProjectDetail(project!.id),
    enabled: open && Boolean(project?.id),
    staleTime: QUERY_STALE_TIMES.projects,
  });

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
          </DrawerQuickActions>
        ) : null
      }
    >
      {!project ? null : detailQuery.isPending ? (
        <LoadingState message="Loading project details…" />
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <FormSection title="Overview" icon={FolderOutlinedIcon}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="Tool Number"
                value={project.tool_number}
                slotProps={{ input: { readOnly: true } }}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="Project Code"
                value={project.code}
                slotProps={{ input: { readOnly: true } }}
              />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <FormField
                label="Part Description"
                value={project.part_description}
                slotProps={{ input: { readOnly: true } }}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="Customer"
                value={formatCellValue(project.customerName) || '—'}
                slotProps={{ input: { readOnly: true } }}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="Due Date"
                value={formatDate(project.due_date)}
                slotProps={{ input: { readOnly: true } }}
              />
            </Grid>
          </FormSection>

          <FormSection title="Assignments" icon={FolderOutlinedIcon}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="Team"
                value={formatCellValue(project.teamName) || '—'}
                slotProps={{ input: { readOnly: true } }}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="Design Leader"
                value={formatCellValue(project.designLeaderName) || '—'}
                slotProps={{ input: { readOnly: true } }}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="Designer"
                value={formatCellValue(project.designerName) || '—'}
                slotProps={{ input: { readOnly: true } }}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="Stream"
                value={formatCellValue(project.streamName) || '—'}
                slotProps={{ input: { readOnly: true } }}
              />
            </Grid>
          </FormSection>

          {detailQuery.data ? (
            <FormSection title="Progress" icon={FolderOutlinedIcon}>
              <Grid size={{ xs: 12 }}>
                <Box sx={{ mb: 1, display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2" color="text.secondary">
                    Milestone completion
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {formatNumber(detailQuery.data.milestone_summary.progress_percent)}%
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={detailQuery.data.milestone_summary.progress_percent}
                  sx={{ height: 8, borderRadius: 4, mb: 2 }}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 4 }}>
                <FormField
                  label="Quoted Hours"
                  value={formatNumber(project.quoted_hours)}
                  slotProps={{ input: { readOnly: true } }}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 4 }}>
                <FormField
                  label="Actual Hours"
                  value={formatNumber(detailQuery.data.hours.actual)}
                  slotProps={{ input: { readOnly: true } }}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 4 }}>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                  <Typography variant="caption" color="text.secondary">
                    Health
                  </Typography>
                  <HealthBadge health={detailQuery.data.health} />
                </Box>
              </Grid>
            </FormSection>
          ) : null}

          <FormSection title="Notes" icon={FolderOutlinedIcon}>
            <FormField
              label="Notes"
              value={formatCellValue(project.notes) || '—'}
              multiline
              minRows={3}
              slotProps={{ input: { readOnly: true } }}
            />
          </FormSection>
        </Box>
      )}
    </RecordDetailDrawer>
  );
}
