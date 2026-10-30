import { useState } from 'react';
import {
  Alert,
  Button,
  Checkbox,
  FormControlLabel,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getErrorMessage } from '../../api/client';
import { fetchUsers } from '../../api/lookups';
import { createSkillPlan, fetchSkillPlans, fetchSkillTaxonomy, skillQueryKeys, updateSkillPlan } from '../../api/skills';
import { useToast } from '../../context/ToastContext';
import type { SkAccess, SkLevel, SkPlan, SkPlanStatus, SkPlanWrite } from '../../types/Skills';
import { formatDate, userDisplayName } from '../../utils/format';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { FilterSelect } from '../ui/design-system/FilterSelect';
import { levelText } from './skillFormat';
import { StateChip } from './skillUi';

const STATUS_LABELS: Record<SkPlanStatus, string> = {
  planned: 'Planned',
  in_progress: 'In progress',
  completed: 'Completed',
  cancelled: 'Cancelled',
};

function planBody(plan: SkPlan, status: SkPlanStatus): SkPlanWrite {
  return {
    skill_id: plan.skill_id,
    target_level: plan.target_level,
    objective: plan.objective,
    training_required: plan.training_required,
    training_requirement: plan.training_requirement,
    is_knowledge_transfer: plan.is_knowledge_transfer,
    mentor_id: plan.mentor_id,
    target_review_date: plan.target_review_date,
    status,
    progress_note: plan.progress_note,
  };
}

export function PlanTable({
  plans,
  levels,
  onStatus,
  busy,
}: {
  plans: SkPlan[];
  levels: SkLevel[];
  onStatus?: (plan: SkPlan, status: SkPlanStatus) => void;
  busy?: boolean;
}) {
  return (
    <Table size="small">
      <TableHead>
        <TableRow>
          <TableCell>Employee</TableCell>
          <TableCell>Skill</TableCell>
          <TableCell>Baseline → target</TableCell>
          <TableCell>Current verification</TableCell>
          <TableCell>Objective / training</TableCell>
          <TableCell>Mentor</TableCell>
          <TableCell>Review date</TableCell>
          <TableCell>Status</TableCell>
          {onStatus ? <TableCell /> : null}
        </TableRow>
      </TableHead>
      <TableBody>
        {plans.map((p) => (
          <TableRow key={p.id} hover>
            <TableCell>{p.user_name}</TableCell>
            <TableCell>{p.skill_name}</TableCell>
            <TableCell>
              {levelText(levels, p.baseline_verified_level)} → {levelText(levels, p.target_level)}
            </TableCell>
            <TableCell>
              <StateChip state={p.verification_outcome} />
              {p.current_verified_level ? ` ${levelText(levels, p.current_verified_level)}` : ''}
            </TableCell>
            <TableCell>
              {p.objective ?? '—'}
              <Typography variant="caption" color="text.secondary" component="div">
                {[p.training_required ? p.training_requirement || 'Training required' : null, p.is_knowledge_transfer ? 'Knowledge transfer' : null, p.progress_note]
                  .filter(Boolean)
                  .join(' · ')}
              </Typography>
            </TableCell>
            <TableCell>
              {p.mentor_name ?? '—'}
              {p.mentor_name ? (
                <Typography variant="caption" color="text.secondary" component="div">
                  {p.mentor_verified_level ? `verified ${levelText(levels, p.mentor_verified_level)}` : 'not verified in this skill'}
                </Typography>
              ) : null}
            </TableCell>
            <TableCell>{p.target_review_date ? formatDate(p.target_review_date) : '—'}</TableCell>
            <TableCell>{STATUS_LABELS[p.status]}</TableCell>
            {onStatus ? (
              <TableCell align="right">
                <Stack direction="row" spacing={0.5} sx={{ justifyContent: 'flex-end' }}>
                  {p.status === 'planned' ? (
                    <Button size="small" disabled={busy} onClick={() => onStatus(p, 'in_progress')}>
                      Start
                    </Button>
                  ) : null}
                  {p.status === 'planned' || p.status === 'in_progress' ? (
                    <>
                      <Button size="small" disabled={busy} onClick={() => onStatus(p, 'completed')}>
                        Complete
                      </Button>
                      <Button size="small" color="inherit" disabled={busy} onClick={() => onStatus(p, 'cancelled')}>
                        Cancel
                      </Button>
                    </>
                  ) : null}
                </Stack>
              </TableCell>
            ) : null}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export function SkillPlansPanel({ access }: { access: SkAccess }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [includeClosed, setIncludeClosed] = useState(false);
  const plansQuery = useQuery({
    queryKey: skillQueryKeys.plans({ include_closed: includeClosed }),
    queryFn: () => fetchSkillPlans({ include_closed: includeClosed }),
  });
  const taxonomyQuery = useQuery({ queryKey: skillQueryKeys.taxonomy(false), queryFn: () => fetchSkillTaxonomy(false) });
  const usersQuery = useQuery({ queryKey: ['lookups', 'users'], queryFn: () => fetchUsers(), enabled: access.can_review });

  const [userId, setUserId] = useState('');
  const [skillId, setSkillId] = useState('');
  const [target, setTarget] = useState('');
  const [objective, setObjective] = useState('');
  const [training, setTraining] = useState('');
  const [knowledgeTransfer, setKnowledgeTransfer] = useState(false);
  const [mentorId, setMentorId] = useState('');
  const [reviewDate, setReviewDate] = useState('');

  const refresh = () => void queryClient.invalidateQueries({ queryKey: skillQueryKeys.all });
  const onError = (err: unknown) => showError(getErrorMessage(err));
  const createMutation = useMutation({
    mutationFn: () =>
      createSkillPlan({
        user_id: userId,
        skill_id: skillId,
        target_level: Number(target),
        objective: objective.trim() || null,
        training_required: Boolean(training.trim()),
        training_requirement: training.trim() || null,
        is_knowledge_transfer: knowledgeTransfer,
        mentor_id: mentorId || null,
        target_review_date: reviewDate || null,
        status: 'planned',
        progress_note: null,
      }),
    onSuccess: () => {
      showSuccess('Development plan created');
      setSkillId('');
      setTarget('');
      setObjective('');
      setTraining('');
      setKnowledgeTransfer(false);
      setMentorId('');
      setReviewDate('');
      refresh();
    },
    onError,
  });
  const statusMutation = useMutation({
    mutationFn: ({ plan, status }: { plan: SkPlan; status: SkPlanStatus }) => updateSkillPlan(plan.id, planBody(plan, status)),
    onSuccess: refresh,
    onError,
  });

  const levels = taxonomyQuery.data?.proficiency_levels ?? [];
  const users = usersQuery.data ?? [];

  return (
    <Stack spacing={2}>
      <Alert severity="info">
        Development plans record the objective, training, mentoring and review date. Completing a plan does not change
        anyone&apos;s proficiency: a reviewer must assess the skill again.
      </Alert>
      {access.can_review ? (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="subtitle1" gutterBottom>
            New development plan
          </Typography>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} useFlexGap sx={{ flexWrap: 'wrap' }}>
            <FilterSelect label="Employee" value={userId} onChange={(e) => setUserId(e.target.value)} sx={{ minWidth: 200, maxWidth: 260 }}>
              <MenuItem value="">Select an employee</MenuItem>
              {users.map((u) => (
                <MenuItem key={u.id} value={u.id}>
                  {userDisplayName(u)}
                </MenuItem>
              ))}
            </FilterSelect>
            <FilterSelect label="Skill" value={skillId} onChange={(e) => setSkillId(e.target.value)} sx={{ minWidth: 200, maxWidth: 260 }}>
              <MenuItem value="">Select a skill</MenuItem>
              {(taxonomyQuery.data?.skills ?? []).map((s) => (
                <MenuItem key={s.id} value={s.id}>
                  {s.name}
                </MenuItem>
              ))}
            </FilterSelect>
            <FilterSelect label="Target level" value={target} onChange={(e) => setTarget(e.target.value)} sx={{ minWidth: 160, maxWidth: 200 }}>
              <MenuItem value="">Select</MenuItem>
              {levels.map((l) => (
                <MenuItem key={l.level} value={String(l.level)}>
                  {l.level} — {l.name}
                </MenuItem>
              ))}
            </FilterSelect>
            <FilterSelect label="Mentor" value={mentorId} onChange={(e) => setMentorId(e.target.value)} sx={{ minWidth: 200, maxWidth: 260 }}>
              <MenuItem value="">No mentor</MenuItem>
              {users
                .filter((u) => u.id !== userId)
                .map((u) => (
                  <MenuItem key={u.id} value={u.id}>
                    {userDisplayName(u)}
                  </MenuItem>
                ))}
            </FilterSelect>
            <TextField
              size="small"
              type="date"
              label="Review date"
              value={reviewDate}
              onChange={(e) => setReviewDate(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
              sx={{ width: 170 }}
            />
          </Stack>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} sx={{ mt: 1.5 }}>
            <TextField size="small" label="Objective" value={objective} onChange={(e) => setObjective(e.target.value)} fullWidth />
            <TextField size="small" label="Training requirement" value={training} onChange={(e) => setTraining(e.target.value)} fullWidth />
          </Stack>
          <Stack direction="row" spacing={2} sx={{ mt: 1, alignItems: 'center' }}>
            <FormControlLabel
              control={<Checkbox checked={knowledgeTransfer} onChange={(e) => setKnowledgeTransfer(e.target.checked)} />}
              label="Knowledge transfer (succession for a specialist skill)"
            />
            <Button
              variant="contained"
              disabled={!userId || !skillId || !target || createMutation.isPending}
              onClick={() => createMutation.mutate()}
            >
              Create plan
            </Button>
          </Stack>
        </Paper>
      ) : null}

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="subtitle1">Plans in scope</Typography>
          <FormControlLabel
            control={<Checkbox checked={includeClosed} onChange={(e) => setIncludeClosed(e.target.checked)} />}
            label="Include completed and cancelled"
          />
        </Stack>
        {plansQuery.isLoading ? <LoadingState message="Loading plans…" /> : null}
        {plansQuery.error ? <ErrorState error={plansQuery.error} /> : null}
        {plansQuery.data ? (
          plansQuery.data.length ? (
            <PlanTable
              plans={plansQuery.data}
              levels={levels}
              busy={statusMutation.isPending}
              onStatus={access.can_review ? (plan, status) => statusMutation.mutate({ plan, status }) : undefined}
            />
          ) : (
            <Typography variant="body2" color="text.secondary">
              No plans.
            </Typography>
          )
        ) : null}
      </Paper>
    </Stack>
  );
}
