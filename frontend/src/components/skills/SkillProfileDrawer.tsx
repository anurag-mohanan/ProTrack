import { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Divider,
  Drawer,
  IconButton,
  ListSubheader,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getErrorMessage } from '../../api/client';
import {
  addSkillEvidence,
  archiveSkillRecord,
  assessSkill,
  fetchSkillExperience,
  fetchSkillProfile,
  fetchSkillTaxonomy,
  removeSkillEvidence,
  skillQueryKeys,
} from '../../api/skills';
import { useToast } from '../../context/ToastContext';
import type { SkDecision, SkMethod } from '../../types/Skills';
import { formatDate, formatNumber } from '../../utils/format';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { FilterSelect } from '../ui/design-system/FilterSelect';
import { SkillRecordList } from './SkillRecordList';
import { levelText } from './skillFormat';

interface Props {
  userId: string | null;
  initialSkillId?: string | null;
  onClose: () => void;
}

export function SkillProfileDrawer({ userId, initialSkillId, onClose }: Props) {
  return (
    <Drawer anchor="right" open={Boolean(userId)} onClose={onClose} slotProps={{ paper: { sx: { width: { xs: '100%', md: 980 } } } }}>
      {userId ? <ProfileBody key={`${userId}:${initialSkillId ?? ''}`} userId={userId} initialSkillId={initialSkillId} onClose={onClose} /> : null}
    </Drawer>
  );
}

function ProfileBody({ userId, initialSkillId, onClose }: { userId: string; initialSkillId?: string | null; onClose: () => void }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const profileQuery = useQuery({ queryKey: skillQueryKeys.profile(userId), queryFn: () => fetchSkillProfile(userId) });
  const experienceQuery = useQuery({ queryKey: skillQueryKeys.experience(userId), queryFn: () => fetchSkillExperience(userId) });
  const taxonomyQuery = useQuery({ queryKey: skillQueryKeys.taxonomy(false), queryFn: () => fetchSkillTaxonomy(false) });

  const [assessSkillId, setAssessSkillId] = useState(initialSkillId ?? '');
  const [decision, setDecision] = useState<SkDecision>('verify');
  const [level, setLevel] = useState('');
  const [method, setMethod] = useState<SkMethod>('manager_assessment');
  const [feedback, setFeedback] = useState('');
  const [confidential, setConfidential] = useState('');

  const profile = profileQuery.data;
  const recordFor = (skillId: string) => profile?.records.find((r) => r.skill_id === skillId && r.state !== 'archived');
  const record = recordFor(assessSkillId);
  const levelValue = level || (record ? String(record.declared_level ?? record.verified_level ?? '') : '');
  const pickSkill = (skillId: string) => {
    setAssessSkillId(skillId);
    setLevel('');
    setDecision('verify');
  };

  const refresh = () => void queryClient.invalidateQueries({ queryKey: skillQueryKeys.all });
  const onError = (err: unknown) => showError(getErrorMessage(err));
  const assessMutation = useMutation({
    mutationFn: () =>
      assessSkill(userId, {
        skill_id: assessSkillId,
        decision,
        level: decision === 'verify' ? Number(levelValue) : null,
        method,
        feedback: feedback.trim() || null,
        confidential_note: confidential.trim() || null,
      }),
    onSuccess: () => {
      showSuccess(decision === 'verify' ? 'Skill verified' : decision === 'reject' ? 'Claim not confirmed' : 'Reassessment requested');
      setFeedback('');
      setConfidential('');
      refresh();
    },
    onError,
  });
  const actionMutation = useMutation({ mutationFn: (fn: () => Promise<void>) => fn(), onSuccess: refresh, onError });

  if (profileQuery.isLoading) return <LoadingState message="Loading profile…" />;
  if (profileQuery.error) return <Box sx={{ p: 2 }}><ErrorState error={profileQuery.error} /></Box>;
  const p = profile!;
  const levels = p.proficiency_levels;
  const skills = taxonomyQuery.data?.skills ?? [];
  const categories = [...new Set(skills.map((s) => s.category || 'Uncategorised'))];
  const canDecide =
    assessSkillId &&
    (decision !== 'verify' || levelValue) &&
    (decision === 'verify' || record) &&
    (decision !== 'request_reassessment' || record?.status === 'verified');

  return (
    <Stack spacing={2} sx={{ p: 2.5 }}>
      <Stack direction="row" sx={{ alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <Box>
          <Typography variant="h6">{p.name}</Typography>
          <Typography variant="body2" color="text.secondary">
            {[p.designation, p.teams.join(', ')].filter(Boolean).join(' · ') || 'No team recorded'}
          </Typography>
        </Box>
        <IconButton onClick={onClose} aria-label="Close">
          <CloseRoundedIcon />
        </IconButton>
      </Stack>

      {p.can_review ? (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="subtitle1" gutterBottom>
            Assess a skill
          </Typography>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} sx={{ alignItems: { md: 'center' } }}>
            <FilterSelect label="Skill" value={assessSkillId} onChange={(e) => pickSkill(e.target.value)} sx={{ minWidth: 240 }}>
              <MenuItem value="">Select a skill</MenuItem>
              {categories.flatMap((category) => [
                <ListSubheader key={`h-${category}`}>{category}</ListSubheader>,
                ...skills
                  .filter((s) => (s.category || 'Uncategorised') === category)
                  .map((s) => (
                    <MenuItem key={s.id} value={s.id}>
                      {s.name}
                    </MenuItem>
                  )),
              ])}
            </FilterSelect>
            <ToggleButtonGroup size="small" exclusive value={decision} onChange={(_, v: SkDecision | null) => v && setDecision(v)}>
              <ToggleButton value="verify">Verify</ToggleButton>
              <ToggleButton value="reject" disabled={!record}>
                Not confirmed
              </ToggleButton>
              <ToggleButton value="request_reassessment" disabled={record?.status !== 'verified'}>
                Request reassessment
              </ToggleButton>
            </ToggleButtonGroup>
          </Stack>
          {assessSkillId ? (
            <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 1 }}>
              {record
                ? `Current: ${record.state_label}; claims ${levelText(levels, record.declared_level)}; verified ${levelText(levels, record.verified_level)}.`
                : 'No record yet. Verifying creates a manager-entered record.'}
            </Typography>
          ) : null}
          {decision === 'verify' ? (
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} sx={{ mt: 1.5 }}>
              <FilterSelect label="Verified level" value={levelValue} onChange={(e) => setLevel(e.target.value)} sx={{ minWidth: 200 }}>
                <MenuItem value="">Select a level</MenuItem>
                {levels.map((l) => (
                  <MenuItem key={l.level} value={String(l.level)}>
                    {l.level} — {l.name}
                  </MenuItem>
                ))}
              </FilterSelect>
              <FilterSelect label="Method" value={method} onChange={(e) => setMethod(e.target.value as SkMethod)} sx={{ minWidth: 220 }}>
                {(taxonomyQuery.data?.verification_methods ?? []).map((m) => (
                  <MenuItem key={m.value} value={m.value}>
                    {m.label}
                  </MenuItem>
                ))}
              </FilterSelect>
            </Stack>
          ) : null}
          <TextField
            size="small"
            label="Feedback (visible to the employee)"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            fullWidth
            multiline
            sx={{ mt: 1.5 }}
          />
          <TextField
            size="small"
            label="Confidential note (reviewers only)"
            value={confidential}
            onChange={(e) => setConfidential(e.target.value)}
            fullWidth
            multiline
            sx={{ mt: 1.5 }}
          />
          <Button variant="contained" sx={{ mt: 1.5 }} disabled={!canDecide || assessMutation.isPending} onClick={() => assessMutation.mutate()}>
            Record decision
          </Button>
        </Paper>
      ) : (
        <Alert severity="info">You can view this profile but are not an authorised reviewer for this employee.</Alert>
      )}

      <Box>
        <Typography variant="subtitle1" gutterBottom>
          Skills
        </Typography>
        <SkillRecordList
          records={p.records}
          levels={levels}
          isSelf={p.is_self}
          canReview={p.can_review}
          evidenceProjects={experienceQuery.data?.projects ?? []}
          busy={actionMutation.isPending}
          onAssess={(r) => pickSkill(r.skill_id)}
          onArchive={(r) => actionMutation.mutate(() => archiveSkillRecord(r.id, null))}
          onAddEvidence={(r, projectId, note) => actionMutation.mutate(() => addSkillEvidence(r.id, projectId, note))}
          onRemoveEvidence={(id) => actionMutation.mutate(() => removeSkillEvidence(id))}
        />
      </Box>

      <Divider />
      <Box>
        <Typography variant="subtitle1" gutterBottom>
          Project experience (supporting evidence only)
        </Typography>
        {experienceQuery.isLoading ? <LoadingState message="Loading project history…" /> : null}
        {experienceQuery.error ? <ErrorState error={experienceQuery.error} /> : null}
        {experienceQuery.data ? (
          <>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Project</TableCell>
                  <TableCell>Customer / stream</TableCell>
                  <TableCell>Role</TableCell>
                  <TableCell align="right">Own hours</TableCell>
                  <TableCell>Booked</TableCell>
                  <TableCell>Status</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {experienceQuery.data.projects.map((row) => (
                  <TableRow key={row.project_id}>
                    <TableCell>
                      {row.tool_number}
                      <Typography variant="caption" color="text.secondary" component="div">
                        {[row.part_description, row.tool_type].filter(Boolean).join(' · ')}
                      </Typography>
                    </TableCell>
                    <TableCell>{[row.customer_name, row.stream_name].filter(Boolean).join(' / ') || '—'}</TableCell>
                    <TableCell>{row.roles.length ? row.roles.map((r) => r.replace('_', ' ')).join(', ') : 'Timesheet only'}</TableCell>
                    <TableCell align="right" title={Object.entries(row.hours_by_status).map(([k, v]) => `${k}: ${v} h`).join(', ')}>
                      {formatNumber(row.hours_total, 1)}
                    </TableCell>
                    <TableCell>
                      {row.first_booked ? `${formatDate(row.first_booked)} – ${formatDate(row.last_booked)}` : '—'}
                    </TableCell>
                    <TableCell>{(row.execution_status ?? '').replace(/_/g, ' ')}</TableCell>
                  </TableRow>
                ))}
                {!experienceQuery.data.projects.length ? (
                  <TableRow>
                    <TableCell colSpan={6}>
                      <Typography variant="body2" color="text.secondary">
                        No assigned or booked projects you can see.
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
            {experienceQuery.data.hidden_project_count ? (
              <Typography variant="caption" color="text.secondary">
                {experienceQuery.data.hidden_project_count} further project(s) are outside your project access.
              </Typography>
            ) : null}
            <Alert severity="info" sx={{ mt: 1 }}>
              <Stack component="ul" sx={{ m: 0, pl: 2 }}>
                {experienceQuery.data.limitations.map((line) => (
                  <li key={line}>
                    <Typography variant="caption">{line}</Typography>
                  </li>
                ))}
              </Stack>
            </Alert>
          </>
        ) : null}
      </Box>
    </Stack>
  );
}
