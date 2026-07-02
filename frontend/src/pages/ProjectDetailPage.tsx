import { useState } from 'react';
import {
  Box,
  Button,
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
import ArchiveIcon from '@mui/icons-material/Archive';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import EditIcon from '@mui/icons-material/Edit';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import AssessmentIcon from '@mui/icons-material/Assessment';
import ScheduleIcon from '@mui/icons-material/Schedule';
import FileCopyIcon from '@mui/icons-material/FileCopy';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  cloneProject,
  commandCenterQueryKeys,
  createEngineeringChange,
  createProjectDecision,
  deleteProjectDecision,
  fetchProjectCommandCenter,
  updateProjectDecision,
  updateProjectFolders,
} from '../api/commandCenter';
import { DecisionLogPanel } from '../components/command-center/DecisionLogPanel';
import { KpiPanel } from '../components/command-center/KpiPanel';
import { WorkflowTimeline } from '../components/command-center/WorkflowTimeline';
import { PageContainer } from '../components/common/PageContainer';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { PageHeader } from '../components/common/PageHeader';
import {
  HealthChip,
  ExecutionStatusChip,
  ProjectStageChip,
} from '../components/common/StatusChip';
import { MilestoneFormDialog } from '../components/projects/MilestoneFormDialog';
import { ProjectFormDialog } from '../components/projects/ProjectFormDialog';
import { AppCard, FormDrawer, FormField, PriorityBadge } from '../components/ui/design-system';
import { ProsohmButton } from '../components/ui/ProsohmButton';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { archiveProject, invalidateProjectCalculationQueries } from '../services/projectService';
import { formatDate, formatNumber } from '../utils/format';
import { canArchiveProject } from '../utils/permissions';

function InfoLine({ label, value }: { label: string; value: string }) {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.75, gap: 2 }}>
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="body2" sx={{ fontWeight: 600, textAlign: 'right' }}>
        {value}
      </Typography>
    </Box>
  );
}

function copyToClipboard(value: string, showSuccess: (msg: string) => void) {
  void navigator.clipboard.writeText(value);
  showSuccess('Path copied to clipboard');
}

export function ProjectDetailPage() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const { showSuccess, showError } = useToast();
  const [editOpen, setEditOpen] = useState(false);
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [milestoneOpen, setMilestoneOpen] = useState(false);
  const [folderOpen, setFolderOpen] = useState(false);
  const [ecOpen, setEcOpen] = useState(false);
  const [folderForm, setFolderForm] = useState({
    project_folder_path: '',
    cad_folder_path: '',
    released_folder_path: '',
  });
  const [ecForm, setEcForm] = useState({ ec_number: '', title: '', hours: 0 });

  const query = useQuery({
    queryKey: commandCenterQueryKeys.detail(id),
    queryFn: () => fetchProjectCommandCenter(id),
    enabled: Boolean(id),
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: commandCenterQueryKeys.detail(id) });
    invalidateProjectCalculationQueries(queryClient, id);
  };

  const archiveMutation = useMutation({
    mutationFn: () => archiveProject(id),
    onSuccess: () => {
      showSuccess('Project archived');
      setArchiveOpen(false);
      invalidate();
    },
    onError: (error: Error) => showError(error.message),
  });

  const cloneMutation = useMutation({
    mutationFn: () => cloneProject(id),
    onSuccess: (cloned: { id: string }) => {
      showSuccess('Project cloned');
      navigate(`/projects/${cloned.id}`);
    },
    onError: (error: Error) => showError(error.message),
  });

  const folderMutation = useMutation({
    mutationFn: () => updateProjectFolders(id, folderForm),
    onSuccess: () => {
      showSuccess('Folder paths saved');
      setFolderOpen(false);
      invalidate();
    },
    onError: (error: Error) => showError(error.message),
  });

  const ecMutation = useMutation({
    mutationFn: () =>
      createEngineeringChange(id, {
        ec_number: ecForm.ec_number,
        title: ecForm.title,
        hours: ecForm.hours,
      }),
    onSuccess: () => {
      showSuccess('Engineering change created');
      setEcOpen(false);
      setEcForm({ ec_number: '', title: '', hours: 0 });
      invalidate();
    },
    onError: (error: Error) => showError(error.message),
  });

  const decisionMutation = useMutation({
    mutationFn: (payload: Parameters<typeof createProjectDecision>[1]) =>
      createProjectDecision(id, payload),
    onSuccess: () => {
      showSuccess('Decision logged');
      invalidate();
    },
    onError: (error: Error) => showError(error.message),
  });

  if (query.isLoading) return <LoadingState message="Loading command center…" />;
  if (query.error) return <ErrorState error={query.error} />;
  if (!query.data) {
    return (
      <EmptyState
        title="Project unavailable"
        description="This project may have been removed or you may not have access to view it."
      />
    );
  }

  const data = query.data;
  const { header, project, folders } = data;
  const displayFolder =
    folders.project_folder_path || folders.suggested_project_folder || '';

  const openFolder = (path: string) => {
    if (!path) {
      showError('No folder path configured');
      return;
    }
    copyToClipboard(path, showSuccess);
  };

  const openFoldersEditor = () => {
    setFolderForm({
      project_folder_path: folders.project_folder_path ?? folders.suggested_project_folder ?? '',
      cad_folder_path: folders.cad_folder_path ?? folders.suggested_cad_folder ?? '',
      released_folder_path:
        folders.released_folder_path ?? folders.suggested_released_folder ?? '',
    });
    setFolderOpen(true);
  };

  return (
    <PageContainer>
      <PageHeader
        title={header.tool_number}
        subtitle={header.part_description}
        action={
          <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
            {!project.is_archived && !project.is_deleted ? (
              <>
                <Button variant="outlined" startIcon={<EditIcon />} onClick={() => setEditOpen(true)}>
                  Edit
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<FileCopyIcon />}
                  onClick={() => cloneMutation.mutate()}
                  disabled={cloneMutation.isPending}
                >
                  Clone
                </Button>
                {canArchiveProject(user?.role_name ?? '') ? (
                  <Button
                    variant="outlined"
                    color="secondary"
                    startIcon={<ArchiveIcon />}
                    onClick={() => setArchiveOpen(true)}
                  >
                    Archive
                  </Button>
                ) : null}
              </>
            ) : null}
            <Button
              component={Link}
              to="/timesheets"
              variant="outlined"
              startIcon={<ScheduleIcon />}
            >
              Timesheets
            </Button>
            <Button component={Link} to="/reports" variant="outlined" startIcon={<AssessmentIcon />}>
              Reports
            </Button>
            <Button variant="outlined" startIcon={<FolderOpenIcon />} onClick={openFoldersEditor}>
              Open Folder
            </Button>
          </Stack>
        }
      />

      <Grid container spacing={2} sx={{ mb: 3 }}>
        {[
          { label: 'Customer', value: header.customer_name },
          { label: 'Team', value: header.team_name ?? '—' },
          { label: 'Designer', value: header.designer_name ?? '—' },
          { label: 'Current Milestone', value: header.current_milestone ?? '—' },
          { label: 'Completion', value: `${formatNumber(header.completion_percent)}%` },
          { label: 'Days Remaining', value: String(header.days_remaining) },
        ].map((item) => (
          <Grid size={{ xs: 6, sm: 4, md: 2 }} key={item.label}>
            <AppCard title={item.label}>
              <Typography sx={{ fontWeight: 700 }}>{item.value}</Typography>
            </AppCard>
          </Grid>
        ))}
      </Grid>

      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 3 }}>
        <HealthChip health={header.health} />
        <ProjectStageChip stage={header.project_stage} />
        <ExecutionStatusChip status={header.execution_status} />
        <PriorityBadge priority={header.priority} />
      </Box>

      <Grid container spacing={2.5}>
        <Grid size={{ xs: 12, lg: 8 }}>
          <AppCard title="Project Timeline" subtitle="Engineering workflow milestones">
            <WorkflowTimeline steps={data.timeline} />
          </AppCard>
        </Grid>
        <Grid size={{ xs: 12, lg: 4 }}>
          <AppCard title="Project Risks" subtitle="Automatically detected">
            {!data.risks.length ? (
              <Typography variant="body2" color="text.secondary">
                No active risks detected.
              </Typography>
            ) : (
              data.risks.map((risk) => (
                <Box
                  key={`${risk.risk_type}-${risk.title}`}
                  sx={{ mb: 1.5, p: 1.5, borderRadius: 2, bgcolor: 'action.hover' }}
                >
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5 }}>
                    <Chip
                      size="small"
                      label={risk.severity}
                      color={
                        risk.severity === 'critical'
                          ? 'error'
                          : risk.severity === 'high'
                            ? 'warning'
                            : 'default'
                      }
                    />
                    <Typography sx={{ fontWeight: 600 }}>{risk.title}</Typography>
                  </Box>
                  {risk.detail ? (
                    <Typography variant="caption" color="text.secondary">
                      {risk.detail}
                    </Typography>
                  ) : null}
                </Box>
              ))
            )}
          </AppCard>
        </Grid>

        <Grid size={{ xs: 12 }}>
          <AppCard title="Project KPIs">
            <KpiPanel kpis={data.kpis} />
          </AppCard>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <AppCard title="Project Team" subtitle="Capacity and availability">
            <InfoLine label="Engineering Manager" value={data.team.engineering_manager_name ?? '—'} />
            <InfoLine label="Design Leader" value={data.team.design_leader_name ?? '—'} />
            <InfoLine label="Designer" value={data.team.designer_name ?? '—'} />
            <InfoLine label="Surfacer" value={data.team.surfacer_name ?? '—'} />
            <InfoLine label="Team" value={data.team.team_name ?? '—'} />
            {data.team.members.map((member) => (
              <Box key={member.user_id} sx={{ mt: 2, p: 1.5, borderRadius: 2, bgcolor: 'action.hover' }}>
                <Typography sx={{ fontWeight: 600 }}>
                  {member.name} · {member.role}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Capacity {formatNumber(member.capacity_hours)}h · Allocated{' '}
                  {formatNumber(member.allocated_hours)}h · Available{' '}
                  {formatNumber(member.available_hours)}h
                </Typography>
              </Box>
            ))}
          </AppCard>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <AppCard title="Customer Summary">
            <InfoLine label="Customer" value={data.customer_summary.customer_name} />
            <InfoLine
              label="Primary Contact"
              value={data.customer_summary.primary_contact_name ?? '—'}
            />
            <InfoLine label="Active Projects" value={String(data.customer_summary.active_projects)} />
            <InfoLine
              label="Completed Projects"
              value={String(data.customer_summary.completed_projects)}
            />
            <InfoLine
              label="Average Hours"
              value={formatNumber(data.customer_summary.average_hours)}
            />
          </AppCard>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <AppCard title="Engineering Changes">
            <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
              <Chip label={`Open: ${data.engineering_changes.open_count}`} color="warning" />
              <Chip label={`Closed: ${data.engineering_changes.closed_count}`} color="success" />
              <Chip label={`Hours: ${formatNumber(data.engineering_changes.total_hours)}`} />
            </Box>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>EC #</TableCell>
                  <TableCell>Title</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell align="right">Hours</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.engineering_changes.items.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>{row.ec_number}</TableCell>
                    <TableCell>{row.title}</TableCell>
                    <TableCell>{row.status}</TableCell>
                    <TableCell align="right">{formatNumber(row.hours)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </AppCard>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <AppCard title="Recent Timesheets">
            {!data.recent_timesheets.length ? (
              <EmptyState title="No timesheet entries" />
            ) : (
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Date</TableCell>
                    <TableCell>Hours</TableCell>
                    <TableCell>Billable</TableCell>
                    <TableCell>Notes</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.recent_timesheets.map((row) => (
                    <TableRow key={row.id}>
                      <TableCell>{formatDate(row.entry_date)}</TableCell>
                      <TableCell>{formatNumber(row.hours)}</TableCell>
                      <TableCell>{row.is_billable ? 'Yes' : 'No'}</TableCell>
                      <TableCell>{row.description ?? '—'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </AppCard>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <AppCard title="Project Folder" subtitle="Paths only — no file storage">
            <InfoLine label="Project Folder" value={displayFolder || '—'} />
            <InfoLine
              label="CAD Folder"
              value={folders.cad_folder_path ?? folders.suggested_cad_folder ?? '—'}
            />
            <InfoLine
              label="Released Folder"
              value={folders.released_folder_path ?? folders.suggested_released_folder ?? '—'}
            />
            <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
              <Button
                size="small"
                startIcon={<FolderOpenIcon />}
                onClick={() => openFolder(displayFolder)}
                disabled={!displayFolder}
              >
                Copy Project Path
              </Button>
              <Button size="small" startIcon={<ContentCopyIcon />} onClick={openFoldersEditor}>
                Edit Paths
              </Button>
            </Stack>
          </AppCard>
        </Grid>

        <Grid size={{ xs: 12 }}>
          <AppCard
            title="Quick Actions"
            action={
              <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
                <ProsohmButton size="small" onClick={() => setMilestoneOpen(true)}>
                  Add Milestone
                </ProsohmButton>
                <Button component={Link} to="/timesheets" size="small" variant="outlined">
                  Add Timesheet
                </Button>
                <ProsohmButton size="small" onClick={() => setEditOpen(true)}>
                  Assign Designer
                </ProsohmButton>
                <ProsohmButton size="small" onClick={() => setEcOpen(true)}>
                  Create EC
                </ProsohmButton>
                <ProsohmButton size="small" onClick={() => setArchiveOpen(true)}>
                  Archive
                </ProsohmButton>
              </Stack>
            }
          >
            <Typography variant="body2" color="text.secondary">
              Use the actions above to update milestones, assignments, engineering changes, and folder
              paths without leaving the command center.
            </Typography>
          </AppCard>
        </Grid>

        <Grid size={{ xs: 12 }}>
          <AppCard title="Engineering Decision Log">
            <DecisionLogPanel
              decisions={data.decisions}
              loading={decisionMutation.isPending}
              onCreate={(payload) => decisionMutation.mutate(payload)}
              onUpdate={(decisionId, payload) =>
                void updateProjectDecision(id, decisionId, payload).then(() => {
                  showSuccess('Decision updated');
                  invalidate();
                })
              }
              onDelete={(decisionId) =>
                void deleteProjectDecision(id, decisionId).then(() => {
                  showSuccess('Decision deleted');
                  invalidate();
                })
              }
            />
          </AppCard>
        </Grid>
      </Grid>

      <Box sx={{ mt: 3 }}>
        <Link to="/projects">← Back to projects</Link>
      </Box>

      <ProjectFormDialog
        open={editOpen}
        onClose={() => setEditOpen(false)}
        project={project}
        onUpdated={invalidate}
      />

      <MilestoneFormDialog
        open={milestoneOpen}
        onClose={() => setMilestoneOpen(false)}
        projectId={project.id}
        onSaved={invalidate}
      />

      <FormDrawer
        open={folderOpen}
        onClose={() => setFolderOpen(false)}
        title="Project Folder Paths"
        subtitle="Store paths only — no CAD uploads"
        formId="folder-form"
        submitLabel="Save Paths"
        loading={folderMutation.isPending}
        onSubmit={() => folderMutation.mutate()}
      >
        <Box id="folder-form" component="form" onSubmit={(e) => e.preventDefault()} sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <FormField
            label="Project Folder Path"
            value={folderForm.project_folder_path}
            onChange={(e) =>
              setFolderForm((c) => ({ ...c, project_folder_path: e.target.value }))
            }
          />
          <FormField
            label="CAD Folder"
            value={folderForm.cad_folder_path}
            onChange={(e) => setFolderForm((c) => ({ ...c, cad_folder_path: e.target.value }))}
          />
          <FormField
            label="Released Folder"
            value={folderForm.released_folder_path}
            onChange={(e) =>
              setFolderForm((c) => ({ ...c, released_folder_path: e.target.value }))
            }
          />
        </Box>
      </FormDrawer>

      <FormDrawer
        open={ecOpen}
        onClose={() => setEcOpen(false)}
        title="Create Engineering Change"
        formId="ec-form"
        submitLabel="Create EC"
        loading={ecMutation.isPending}
        onSubmit={() => ecMutation.mutate()}
      >
        <Box id="ec-form" component="form" onSubmit={(e) => e.preventDefault()} sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <FormField
            label="EC Number"
            value={ecForm.ec_number}
            onChange={(e) => setEcForm((c) => ({ ...c, ec_number: e.target.value }))}
          />
          <FormField
            label="Title"
            value={ecForm.title}
            onChange={(e) => setEcForm((c) => ({ ...c, title: e.target.value }))}
          />
          <FormField
            label="Hours"
            type="number"
            value={ecForm.hours}
            onChange={(e) => setEcForm((c) => ({ ...c, hours: Number(e.target.value) }))}
          />
        </Box>
      </FormDrawer>

      <ConfirmDialog
        open={archiveOpen}
        title="Archive project?"
        message="Archived projects are removed from the default list but remain in reports and history."
        confirmLabel="Archive"
        loading={archiveMutation.isPending}
        onClose={() => setArchiveOpen(false)}
        onConfirm={() => archiveMutation.mutate()}
      />
    </PageContainer>
  );
}
