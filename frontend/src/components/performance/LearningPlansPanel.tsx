import { useState } from 'react';
import {
  Box,
  Button,
  Chip,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getErrorMessage } from '../../api/client';
import {
  createLearningPlanFromGaps,
  fetchLearningPlans,
  updateLearningPlanItemStatus,
  type LearningPlan,
} from '../../api/learningPlans';
import { fetchUsers } from '../../api/lookups';
import { useToast } from '../../context/ToastContext';
import { FilterSelect } from '../ui/design-system/FilterSelect';
import { LoadingState } from '../common/LoadingState';
import { userDisplayName } from '../../utils/format';

type LearningPlansPanelProps = {
  canManage: boolean;
};

export function LearningPlansPanel({ canManage }: LearningPlansPanelProps) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [userId, setUserId] = useState('');

  const usersQuery = useQuery({
    queryKey: ['lookups', 'users'],
    queryFn: () => fetchUsers(),
  });

  const plansQuery = useQuery({
    queryKey: ['performance', 'learning-plans', userId],
    queryFn: () => fetchLearningPlans(userId),
    enabled: Boolean(userId),
  });

  const createMutation = useMutation({
    mutationFn: () => createLearningPlanFromGaps({ user_id: userId }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ['performance', 'learning-plans', userId],
      });
      showSuccess('Learning plan created from skill gaps');
    },
    onError: (err) => showError(getErrorMessage(err)),
  });

  const statusMutation = useMutation({
    mutationFn: ({ itemId, status }: { itemId: string; status: string }) =>
      updateLearningPlanItemStatus(itemId, status),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ['performance', 'learning-plans', userId],
      });
      showSuccess('Learning item updated');
    },
    onError: (err) => showError(getErrorMessage(err)),
  });

  const plans: LearningPlan[] = plansQuery.data ?? [];

  return (
    <Box sx={{ mt: 3 }}>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        spacing={1.5}
        sx={{ mb: 1.5, alignItems: { sm: 'center' } }}
      >
        <Box sx={{ flex: 1 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
            Learning plans
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Create a plan from skill-matrix gaps and track progress per skill.
          </Typography>
        </Box>
        <FilterSelect
          label="Person"
          value={userId}
          fullWidth={false}
          sx={{ minWidth: 220 }}
          onChange={(e) => setUserId(String(e.target.value))}
        >
          <MenuItem value="">Select person</MenuItem>
          {(usersQuery.data ?? []).map((user) => (
            <MenuItem key={user.id} value={user.id}>
              {userDisplayName(user)}
            </MenuItem>
          ))}
        </FilterSelect>
        {canManage ? (
          <Button
            variant="outlined"
            disabled={!userId || createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            Create from gaps
          </Button>
        ) : null}
      </Stack>

      {!userId ? (
        <Typography color="text.secondary">Select a person to view learning plans.</Typography>
      ) : plansQuery.isLoading ? (
        <LoadingState message="Loading learning plans…" />
      ) : plans.length === 0 ? (
        <Typography color="text.secondary">
          No learning plans yet. Create one from current skill gaps.
        </Typography>
      ) : (
        <Stack spacing={2}>
          {plans.map((plan) => (
            <Box
              key={plan.id}
              sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 1.5 }}
            >
              <Stack direction="row" spacing={1} sx={{ mb: 1, alignItems: 'center' }}>
                <Typography sx={{ fontWeight: 700, flex: 1 }}>{plan.title}</Typography>
                <Chip size="small" label={plan.status} />
              </Stack>
              {!plan.items.length ? (
                <Typography variant="body2" color="text.secondary">
                  No gap items (already at target proficiency).
                </Typography>
              ) : (
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Skill</TableCell>
                      <TableCell>Current</TableCell>
                      <TableCell>Target</TableCell>
                      <TableCell>Status</TableCell>
                      {canManage ? <TableCell align="right">Action</TableCell> : null}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {plan.items.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell>{item.skill_name || 'Skill'}</TableCell>
                        <TableCell>{item.current_proficiency || '—'}</TableCell>
                        <TableCell>{item.target_proficiency}</TableCell>
                        <TableCell>
                          <Chip size="small" label={item.status} variant="outlined" />
                        </TableCell>
                        {canManage ? (
                          <TableCell align="right">
                            {item.status !== 'done' ? (
                              <Button
                                size="small"
                                disabled={statusMutation.isPending}
                                onClick={() =>
                                  statusMutation.mutate({ itemId: item.id, status: 'done' })
                                }
                              >
                                Mark done
                              </Button>
                            ) : (
                              <Button
                                size="small"
                                disabled={statusMutation.isPending}
                                onClick={() =>
                                  statusMutation.mutate({ itemId: item.id, status: 'open' })
                                }
                              >
                                Reopen
                              </Button>
                            )}
                          </TableCell>
                        ) : null}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </Box>
          ))}
        </Stack>
      )}
    </Box>
  );
}
