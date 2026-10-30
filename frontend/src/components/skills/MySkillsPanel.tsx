import { useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Checkbox,
  FormControlLabel,
  ListSubheader,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getErrorMessage } from '../../api/client';
import {
  addSkillEvidence,
  archiveSkillRecord,
  declareSkill,
  fetchMySkills,
  fetchSkillExperience,
  fetchSkillPlans,
  fetchSkillTaxonomy,
  removeSkillEvidence,
  skillQueryKeys,
  submitSkillRecord,
} from '../../api/skills';
import { useToast } from '../../context/ToastContext';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { FilterSelect } from '../ui/design-system/FilterSelect';
import { SkillRecordList } from './SkillRecordList';
import { PlanTable } from './SkillPlansPanel';

export function MySkillsPanel() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const meQuery = useQuery({ queryKey: skillQueryKeys.me, queryFn: fetchMySkills });
  const taxonomyQuery = useQuery({ queryKey: skillQueryKeys.taxonomy(false), queryFn: () => fetchSkillTaxonomy(false) });
  const userId = meQuery.data?.user_id;
  const experienceQuery = useQuery({
    queryKey: skillQueryKeys.experience(userId ?? ''),
    queryFn: () => fetchSkillExperience(userId!),
    enabled: Boolean(userId),
  });
  const plansQuery = useQuery({
    queryKey: skillQueryKeys.plans({ include_closed: true }),
    queryFn: () => fetchSkillPlans({ include_closed: true }),
  });

  const [skillId, setSkillId] = useState('');
  const [level, setLevel] = useState('');
  const [years, setYears] = useState('');
  const [lastUsed, setLastUsed] = useState('');
  const [note, setNote] = useState('');
  const [submit, setSubmit] = useState(true);

  const refresh = () => void queryClient.invalidateQueries({ queryKey: skillQueryKeys.all });
  const onError = (err: unknown) => showError(getErrorMessage(err));

  const declareMutation = useMutation({
    mutationFn: () =>
      declareSkill({
        skill_id: skillId,
        declared_level: Number(level),
        years_experience: years === '' ? null : Number(years),
        last_used_on: lastUsed || null,
        employee_note: note.trim() || null,
        submit_for_verification: submit,
      }),
    onSuccess: () => {
      showSuccess(submit ? 'Claim submitted for verification' : 'Skill recorded as self-declared');
      setSkillId('');
      setLevel('');
      setYears('');
      setLastUsed('');
      setNote('');
      refresh();
    },
    onError,
  });
  const actionMutation = useMutation({
    mutationFn: (fn: () => Promise<void>) => fn(),
    onSuccess: refresh,
    onError,
  });

  const existing = useMemo(() => {
    const map = new Map<string, number | null>();
    (meQuery.data?.records ?? []).forEach((r) => {
      if (r.state !== 'archived') map.set(r.skill_id, r.declared_level);
    });
    return map;
  }, [meQuery.data]);

  const grouped = useMemo(() => {
    const groups = new Map<string, { id: string; name: string }[]>();
    (taxonomyQuery.data?.skills ?? []).forEach((s) => {
      const key = s.category || 'Uncategorised';
      groups.set(key, [...(groups.get(key) ?? []), { id: s.id, name: s.name }]);
    });
    return [...groups.entries()];
  }, [taxonomyQuery.data]);

  if (meQuery.isLoading || taxonomyQuery.isLoading) return <LoadingState message="Loading your skills…" />;
  if (meQuery.error) return <ErrorState error={meQuery.error} onRetry={() => void meQuery.refetch()} />;
  if (taxonomyQuery.error) return <ErrorState error={taxonomyQuery.error} />;
  const profile = meQuery.data!;
  const levels = profile.proficiency_levels;
  const myPlans = (plansQuery.data ?? []).filter((p) => p.user_id === profile.user_id);

  return (
    <Stack spacing={3}>
      <Alert severity="info">
        Your own declarations are recorded as <strong>self-declared</strong>. Only an authorised reviewer can verify a
        skill, and only verified skills count towards coverage and recommendations. Years of experience and project
        history are supporting information; they never set a level.
      </Alert>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle1" gutterBottom>
          Declare or update a skill
        </Typography>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} sx={{ alignItems: { md: 'flex-start' } }}>
          <FilterSelect label="Skill" value={skillId} onChange={(e) => {
            setSkillId(e.target.value);
            const current = existing.get(e.target.value);
            if (current) setLevel(String(current));
          }} sx={{ minWidth: 240 }}>
            <MenuItem value="">Select a skill</MenuItem>
            {grouped.flatMap(([category, skills]) => [
              <ListSubheader key={`h-${category}`}>{category}</ListSubheader>,
              ...skills.map((s) => (
                <MenuItem key={s.id} value={s.id}>
                  {s.name}
                  {existing.has(s.id) ? ' (recorded)' : ''}
                </MenuItem>
              )),
            ])}
          </FilterSelect>
          <FilterSelect label="Your level" value={level} onChange={(e) => setLevel(e.target.value)} sx={{ minWidth: 200 }}>
            <MenuItem value="">Select a level</MenuItem>
            {levels.map((l) => (
              <MenuItem key={l.level} value={String(l.level)}>
                {l.level} — {l.name}
              </MenuItem>
            ))}
          </FilterSelect>
          <TextField
            size="small"
            type="number"
            label="Years of experience"
            value={years}
            onChange={(e) => setYears(e.target.value)}
            slotProps={{ htmlInput: { min: 0, max: 60, step: 0.5 }, inputLabel: { shrink: true } }}
            sx={{ width: 170 }}
          />
          <TextField
            size="small"
            type="date"
            label="Last used"
            value={lastUsed}
            onChange={(e) => setLastUsed(e.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
            sx={{ width: 170 }}
          />
        </Stack>
        {level ? (
          <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 1 }}>
            {levels.find((l) => String(l.level) === level)?.description}
          </Typography>
        ) : null}
        <TextField
          size="small"
          label="Note for your reviewer (optional)"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          fullWidth
          multiline
          minRows={1}
          sx={{ mt: 1.5 }}
        />
        <Stack direction="row" spacing={2} sx={{ mt: 1.5, alignItems: 'center' }}>
          <FormControlLabel
            control={<Checkbox checked={submit} onChange={(e) => setSubmit(e.target.checked)} />}
            label="Submit for verification now"
          />
          <Button
            variant="contained"
            disabled={!skillId || !level || declareMutation.isPending}
            onClick={() => declareMutation.mutate()}
          >
            Save
          </Button>
        </Stack>
      </Paper>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle1" gutterBottom>
          My skills
        </Typography>
        <SkillRecordList
          records={profile.records}
          levels={levels}
          isSelf
          canReview={false}
          evidenceProjects={experienceQuery.data?.projects ?? []}
          busy={actionMutation.isPending}
          onSubmit={(r) => actionMutation.mutate(() => submitSkillRecord(r.id))}
          onArchive={(r) => actionMutation.mutate(() => archiveSkillRecord(r.id, null))}
          onAddEvidence={(r, projectId, evidenceNote) => actionMutation.mutate(() => addSkillEvidence(r.id, projectId, evidenceNote))}
          onRemoveEvidence={(id) => actionMutation.mutate(() => removeSkillEvidence(id))}
        />
      </Paper>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle1" gutterBottom>
          My development plans
        </Typography>
        {myPlans.length ? (
          <PlanTable plans={myPlans} levels={levels} />
        ) : (
          <Typography variant="body2" color="text.secondary">
            No development plans. Your manager or reviewer creates them with you.
          </Typography>
        )}
      </Paper>
    </Stack>
  );
}
