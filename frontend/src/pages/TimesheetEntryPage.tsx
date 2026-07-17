import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { fetchCustomers, fetchNonProductiveCodes, fetchTaskTypes, fetchTimesheetProjects } from '../api/lookups';
import { fetchMilestones } from '../api/milestones';
import { createTimesheetEntry } from '../api/timesheets';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { PageHeader } from '../components/common/PageHeader';
import { FilterSelect } from '../components/ui/design-system/FilterSelect';
import { useAuth } from '../context/AuthContext';
import type { WorkCategory } from '../types';
import { projectLabel } from '../types/Project';
import { canOverrideBillable } from '../utils/permissions';
import { invalidateTimesheetRelatedQueries } from '../utils/queryInvalidation';

const RECENT_PROJECTS_KEY = 'protrack.recentProjects';
const RECENT_NP_CODES_KEY = 'protrack.recentNpCodes';
const MAX_RECENT = 5;

function readRecentIds(key: string): string[] {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((value) => typeof value === 'string') : [];
  } catch {
    return [];
  }
}

function pushRecentId(key: string, id: string) {
  const next = [id, ...readRecentIds(key).filter((value) => value !== id)].slice(0, MAX_RECENT);
  localStorage.setItem(key, JSON.stringify(next));
}


export function TimesheetEntryPage() {
  const { timesheetId = '' } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const roleName = user?.role_name ?? '';
  const canEditBillable = canOverrideBillable(roleName);

  const [workCategory, setWorkCategory] = useState<WorkCategory>('productive');
  const [projectId, setProjectId] = useState('');
  const [taskTypeId, setTaskTypeId] = useState('');
  const [milestoneId, setMilestoneId] = useState('');
  const [npCodeId, setNpCodeId] = useState('');
  const [customerId, setCustomerId] = useState('');
  const [isBillable, setIsBillable] = useState<'yes' | 'no'>('yes');
  const [entryDate, setEntryDate] = useState(new Date().toISOString().slice(0, 10));
  const [hours, setHours] = useState('8');
  const [description, setDescription] = useState('');

  const projectsQuery = useQuery({
    queryKey: ['timesheet-projects'],
    queryFn: () => fetchTimesheetProjects(),
  });

  const customersQuery = useQuery({
    queryKey: ['customers'],
    queryFn: fetchCustomers,
  });

  const npCodesQuery = useQuery({
    queryKey: ['non-productive-codes'],
    queryFn: fetchNonProductiveCodes,
    enabled: workCategory === 'non_productive',
  });

  const selectedProject = useMemo(
    () => (projectsQuery.data ?? []).find((project) => project.id === projectId),
    [projectsQuery.data, projectId],
  );

  const taskTypesQuery = useQuery({
    queryKey: ['task-types', selectedProject?.stream_id],
    queryFn: () => fetchTaskTypes(selectedProject?.stream_id ?? undefined),
    enabled: workCategory === 'productive' && Boolean(selectedProject?.stream_id),
  });

  const milestonesQuery = useQuery({
    queryKey: ['milestones', projectId],
    queryFn: () => fetchMilestones({ project_id: projectId }),
    enabled: workCategory === 'productive' && Boolean(projectId),
  });

  const activeProjects = useMemo(
    () => projectsQuery.data ?? [],
    [projectsQuery.data],
  );

  const recentProjectIds = useMemo(() => readRecentIds(RECENT_PROJECTS_KEY), []);
  const recentNpCodeIds = useMemo(() => readRecentIds(RECENT_NP_CODES_KEY), []);

  const sortedProjects = useMemo(() => {
    const recent = new Set(recentProjectIds);
    return [...activeProjects].sort((a, b) => {
      const aRecent = recent.has(a.id) ? 0 : 1;
      const bRecent = recent.has(b.id) ? 0 : 1;
      if (aRecent !== bRecent) return aRecent - bRecent;
      return projectLabel(a).localeCompare(projectLabel(b));
    });
  }, [activeProjects, recentProjectIds]);

  const activeTaskTypes = useMemo(
    () => (taskTypesQuery.data ?? []).filter((taskType) => taskType.is_active),
    [taskTypesQuery.data],
  );

  const activeNpCodes = useMemo(
    () => (npCodesQuery.data ?? []).filter((code) => code.is_active),
    [npCodesQuery.data],
  );

  const sortedNpCodes = useMemo(() => {
    const recent = new Set(recentNpCodeIds);
    return [...activeNpCodes].sort((a, b) => {
      const aRecent = recent.has(a.id) ? 0 : 1;
      const bRecent = recent.has(b.id) ? 0 : 1;
      if (aRecent !== bRecent) return aRecent - bRecent;
      return a.sort_order - b.sort_order || a.code.localeCompare(b.code);
    });
  }, [activeNpCodes, recentNpCodeIds]);

  const resolvedCustomerName = useMemo(() => {
    if (workCategory !== 'productive' || !selectedProject) return '';
    return selectedProject.customer_name ?? '';
  }, [workCategory, selectedProject]);

  useEffect(() => {
    setMilestoneId('');
    setTaskTypeId('');
  }, [projectId]);

  useEffect(() => {
    if (workCategory === 'non_productive') {
      setIsBillable('no');
      setProjectId('');
      setMilestoneId('');
      setTaskTypeId('');
    } else {
      setIsBillable('yes');
      setNpCodeId('');
      setCustomerId('');
    }
  }, [workCategory]);

  const createMutation = useMutation({
    mutationFn: createTimesheetEntry,
    onSuccess: (_entry, variables) => {
      if (variables.project_id) pushRecentId(RECENT_PROJECTS_KEY, variables.project_id);
      if (variables.non_productive_code_id) {
        pushRecentId(RECENT_NP_CODES_KEY, variables.non_productive_code_id);
      }
      invalidateTimesheetRelatedQueries(queryClient, variables.project_id ?? undefined);
      navigate('/timesheets');
    },
  });

  const isLoading =
    projectsQuery.isLoading ||
    customersQuery.isLoading ||
    (workCategory === 'non_productive' && npCodesQuery.isLoading);

  if (isLoading) return <LoadingState />;

  if (projectsQuery.error) return <ErrorState error={projectsQuery.error} />;
  if (npCodesQuery.error) return <ErrorState error={npCodesQuery.error} />;
  if (customersQuery.error) return <ErrorState error={customersQuery.error} />;
  if (taskTypesQuery.error) return <ErrorState error={taskTypesQuery.error} />;

  const hoursValue = Number(hours);
  const validHoursForProductive = Number.isFinite(hoursValue) && hoursValue > 0 && hoursValue <= 24;
  const validHoursForNonProductive =
    Number.isFinite(hoursValue) && hoursValue >= 0 && hoursValue <= 24;
  const productiveValid = Boolean(projectId && taskTypeId && validHoursForProductive);
  const nonProductiveValid = Boolean(npCodeId && validHoursForNonProductive);
  const canSubmit = workCategory === 'productive' ? productiveValid : nonProductiveValid;

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    const payload = {
      timesheet_id: timesheetId,
      work_category: workCategory,
      entry_date: entryDate,
      hours: Number(hours),
      description: description || null,
    } as Parameters<typeof createTimesheetEntry>[0];

    if (workCategory === 'productive') {
      payload.project_id = projectId;
      payload.task_type_id = taskTypeId;
      payload.milestone_id = milestoneId || null;
      if (canEditBillable) {
        payload.is_billable = isBillable === 'yes';
      }
    } else {
      payload.non_productive_code_id = npCodeId;
      payload.customer_id = customerId || null;
      if (canEditBillable && isBillable === 'yes') {
        payload.is_billable = true;
      }
    }

    createMutation.mutate(payload);
  };

  return (
    <Box>
      <PageHeader
        title="New Timesheet Entry"
        subtitle="Log productive project work or non-productive time"
      />

      <Paper sx={{ p: 3, maxWidth: 640 }}>
        <Stack component="form" spacing={2} onSubmit={handleSubmit}>
          <FormControl fullWidth required>
            <InputLabel>Work Category</InputLabel>
            <Select
              label="Work Category"
              value={workCategory}
              onChange={(event) => setWorkCategory(event.target.value as WorkCategory)}
            >
              <MenuItem value="productive">Productive</MenuItem>
              <MenuItem value="non_productive">Non-Productive</MenuItem>
            </Select>
          </FormControl>

          {workCategory === 'productive' ? (
            <>
              <FormControl fullWidth required>
                <InputLabel>Project</InputLabel>
                <Select
                  label="Project"
                  value={projectId}
                  onChange={(event) => setProjectId(event.target.value)}
                >
                  {sortedProjects.map((project) => (
                    <MenuItem key={project.id} value={project.id}>
                      {projectLabel(project)}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <TextField
                label="Customer"
                fullWidth
                value={resolvedCustomerName}
                slotProps={{ input: { readOnly: true } }}
                helperText="Filled automatically from the selected project"
              />

              <FormControl fullWidth required>
                <InputLabel>Task</InputLabel>
                <Select
                  label="Task"
                  value={taskTypeId}
                  disabled={!projectId}
                  onChange={(event) => setTaskTypeId(event.target.value)}
                >
                  {activeTaskTypes.map((taskType) => (
                    <MenuItem key={taskType.id} value={taskType.id}>
                      {taskType.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <FilterSelect
                label="Milestone"
                size="medium"
                value={milestoneId}
                disabled={!projectId}
                onChange={(event) => setMilestoneId(String(event.target.value))}
              >
                <MenuItem value="">None</MenuItem>
                {(milestonesQuery.data ?? []).map((milestone) => (
                  <MenuItem key={milestone.id} value={milestone.id}>
                    {milestone.name}
                  </MenuItem>
                ))}
              </FilterSelect>

              <FormControl fullWidth>
                <InputLabel>Billable</InputLabel>
                <Select
                  label="Billable"
                  value={isBillable}
                  disabled={!canEditBillable}
                  onChange={(event) => setIsBillable(event.target.value as 'yes' | 'no')}
                >
                  <MenuItem value="yes">YES</MenuItem>
                  <MenuItem value="no">NO</MenuItem>
                </Select>
              </FormControl>
            </>
          ) : (
            <>
              <FormControl fullWidth required>
                <InputLabel>NP Code</InputLabel>
                <Select
                  label="NP Code"
                  value={npCodeId}
                  onChange={(event) => setNpCodeId(event.target.value)}
                >
                  {sortedNpCodes.map((code) => (
                    <MenuItem key={code.id} value={code.id}>
                      {code.code} — {code.description}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <FilterSelect
                label="Customer (optional)"
                size="medium"
                value={customerId}
                onChange={(event) => setCustomerId(String(event.target.value))}
              >
                <MenuItem value="">None</MenuItem>
                {(customersQuery.data ?? []).map((customer) => (
                  <MenuItem key={customer.id} value={customer.id}>
                    {customer.name}
                  </MenuItem>
                ))}
              </FilterSelect>

              <FormControl fullWidth>
                <InputLabel>Billable</InputLabel>
                <Select
                  label="Billable"
                  value={canEditBillable ? isBillable : 'no'}
                  disabled={!canEditBillable}
                  onChange={(event) => setIsBillable(event.target.value as 'yes' | 'no')}
                >
                  <MenuItem value="no">NO</MenuItem>
                  {canEditBillable ? <MenuItem value="yes">YES</MenuItem> : null}
                </Select>
              </FormControl>
            </>
          )}

          <TextField
            label="Date"
            type="date"
            required
            fullWidth
            slotProps={{ inputLabel: { shrink: true } }}
            value={entryDate}
            onChange={(event) => setEntryDate(event.target.value)}
          />

          <TextField
            label="Hours"
            type="number"
            required
            fullWidth
            slotProps={{
              htmlInput: {
                min: workCategory === 'non_productive' ? 0 : 0.5,
                max: 24,
                step: 0.5,
              },
            }}
            value={hours}
            onChange={(event) => setHours(event.target.value)}
          />

          <TextField
            label="Notes"
            fullWidth
            multiline
            rows={3}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />

          {createMutation.error ? (
            <ErrorState error={createMutation.error} title="Save failed" />
          ) : null}

          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button type="submit" variant="contained" disabled={createMutation.isPending || !canSubmit}>
              {createMutation.isPending ? 'Saving…' : 'Save Entry'}
            </Button>
            <Button component={Link} to="/timesheets">
              Cancel
            </Button>
          </Box>
        </Stack>
      </Paper>
    </Box>
  );
}
