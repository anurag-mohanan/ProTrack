import { useState } from 'react';
import {
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchMilestones, updateMilestone } from '../../api/milestones';
import { EmptyState } from '../common/EmptyState';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import type { MilestoneStatus } from '../../types';
import { formatDate, formatDateTime } from '../../utils/format';

const statusOptions: MilestoneStatus[] = [
  'not_started',
  'in_progress',
  'completed',
  'not_applicable',
];

interface ProjectMilestonesTabProps {
  projectId: string;
}

export function ProjectMilestonesTab({ projectId }: ProjectMilestonesTabProps) {
  const queryClient = useQueryClient();
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ['milestones', projectId],
    queryFn: () => fetchMilestones({ project_id: projectId }),
  });

  const mutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: MilestoneStatus }) =>
      updateMilestone(id, { status }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['milestones', projectId] });
      void queryClient.invalidateQueries({ queryKey: ['dashboard', 'project', projectId] });
    },
    onSettled: () => setUpdatingId(null),
  });

  if (isLoading) return <LoadingState message="Loading milestones…" />;
  if (error) return <ErrorState error={error} />;

  if (!data?.length) {
    return (
      <EmptyState
        title="No milestones"
        description="Milestones for this project will appear here."
      />
    );
  }

  return (
    <TableContainer component={Paper}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Milestone</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Due Date</TableCell>
            <TableCell>Completed Date</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {data.map((milestone) => (
            <TableRow key={milestone.id} hover>
              <TableCell>{milestone.name}</TableCell>
              <TableCell>
                <FormControl size="small" sx={{ minWidth: 160 }}>
                  <InputLabel>Status</InputLabel>
                  <Select
                    label="Status"
                    value={milestone.status}
                    disabled={updatingId === milestone.id && mutation.isPending}
                    onChange={(event) => {
                      const status = event.target.value as MilestoneStatus;
                      setUpdatingId(milestone.id);
                      mutation.mutate({ id: milestone.id, status });
                    }}
                  >
                    {statusOptions.map((status) => (
                      <MenuItem key={status} value={status}>
                        {status.replace(/_/g, ' ')}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </TableCell>
              <TableCell>{formatDate(milestone.due_date)}</TableCell>
              <TableCell>{formatDateTime(milestone.completed_at)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
