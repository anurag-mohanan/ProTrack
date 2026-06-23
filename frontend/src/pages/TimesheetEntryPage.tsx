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
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { fetchMilestones } from '../api/milestones';
import { fetchTaskTypes } from '../api/lookups';
import { fetchProjects } from '../api/projects';
import { createTimesheetEntry } from '../api/timesheets';
import { timesheetQueryKeys } from '../services/timesheetService';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { projectLabel } from '../types';

export function TimesheetEntryPage() {
  const { timesheetId = '' } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [projectId, setProjectId] = useState('');
  const [taskTypeId, setTaskTypeId] = useState('');
  const [milestoneId, setMilestoneId] = useState('');
  const [entryDate, setEntryDate] = useState(new Date().toISOString().slice(0, 10));
  const [hours, setHours] = useState('8');
  const [description, setDescription] = useState('');

  const projectsQuery = useQuery({
    queryKey: ['projects'],
    queryFn: () => fetchProjects(),
  });

  const taskTypesQuery = useQuery({
    queryKey: ['task-types'],
    queryFn: fetchTaskTypes,
  });

  const milestonesQuery = useQuery({
    queryKey: ['milestones', projectId],
    queryFn: () => fetchMilestones({ project_id: projectId }),
    enabled: Boolean(projectId),
  });

  const activeTaskTypes = useMemo(
    () => (taskTypesQuery.data ?? []).filter((taskType) => taskType.is_active),
    [taskTypesQuery.data],
  );

  useEffect(() => {
    setMilestoneId('');
  }, [projectId]);

  const createMutation = useMutation({
    mutationFn: createTimesheetEntry,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: timesheetQueryKeys.all });
      void queryClient.invalidateQueries({
        queryKey: timesheetQueryKeys.entries(timesheetId),
      });
      navigate('/timesheets');
    },
  });

  if (projectsQuery.isLoading || taskTypesQuery.isLoading) {
    return <LoadingState />;
  }

  if (projectsQuery.error) return <ErrorState error={projectsQuery.error} />;
  if (taskTypesQuery.error) return <ErrorState error={taskTypesQuery.error} />;

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    createMutation.mutate({
      timesheet_id: timesheetId,
      project_id: projectId,
      task_type_id: taskTypeId || null,
      milestone_id: milestoneId || null,
      entry_date: entryDate,
      hours: Number(hours),
      description: description || null,
    });
  };

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700 }} gutterBottom>
        New Timesheet Entry
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Log hours against a project and milestone
      </Typography>

      <Paper sx={{ p: 3, maxWidth: 640 }}>
        <Stack
          component="form"
          spacing={2}
          onSubmit={handleSubmit}
        >
          <FormControl fullWidth required>
            <InputLabel>Project</InputLabel>
            <Select
              label="Project"
              value={projectId}
              onChange={(event) => setProjectId(event.target.value)}
            >
              {(projectsQuery.data ?? []).map((project) => (
                <MenuItem key={project.id} value={project.id}>
                  {projectLabel(project)}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl fullWidth>
            <InputLabel>Task Type</InputLabel>
            <Select
              label="Task Type"
              value={taskTypeId}
              onChange={(event) => setTaskTypeId(event.target.value)}
            >
              <MenuItem value="">None</MenuItem>
              {activeTaskTypes.map((taskType) => (
                <MenuItem key={taskType.id} value={taskType.id}>
                  {taskType.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl fullWidth disabled={!projectId}>
            <InputLabel>Milestone</InputLabel>
            <Select
              label="Milestone"
              value={milestoneId}
              onChange={(event) => setMilestoneId(event.target.value)}
            >
              <MenuItem value="">None</MenuItem>
              {(milestonesQuery.data ?? []).map((milestone) => (
                <MenuItem key={milestone.id} value={milestone.id}>
                  {milestone.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

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
            slotProps={{ htmlInput: { min: 0.25, max: 24, step: 0.25 } }}
            value={hours}
            onChange={(event) => setHours(event.target.value)}
          />

          <TextField
            label="Description"
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
            <Button
              type="submit"
              variant="contained"
              disabled={createMutation.isPending || !projectId}
            >
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
