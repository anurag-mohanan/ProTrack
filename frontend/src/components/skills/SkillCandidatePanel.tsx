import { useState } from 'react';
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Checkbox,
  Chip,
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
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getErrorMessage } from '../../api/client';
import { fetchTeams } from '../../api/lookups';
import {
  fetchProjectSkillRequirements,
  fetchSkillTaxonomy,
  matchSkillCandidates,
  removeProjectSkillRequirement,
  setProjectSkillRequirement,
  skillQueryKeys,
} from '../../api/skills';
import { useToast } from '../../context/ToastContext';
import { getProjects } from '../../services/projectService';
import type { Project } from '../../types';
import type { SkAvailability, SkMatchResult, SkRequirementSpec, SkSuitability } from '../../types/Skills';
import { formatDate, formatNumber } from '../../utils/format';
import { ErrorState } from '../common/ErrorState';
import { FilterSelect } from '../ui/design-system/FilterSelect';

const SUITABILITY_COLOR: Record<SkSuitability, 'success' | 'default' | 'warning'> = {
  confirmed: 'success',
  unconfirmed: 'default',
  below_requirement: 'warning',
};
const AVAILABILITY_COLOR: Record<SkAvailability, 'success' | 'info' | 'warning' | 'default'> = {
  capacity_indicated: 'success',
  uncertain: 'info',
  committed: 'warning',
  unavailable: 'default',
};
const SUITABILITY_SHORT: Record<SkSuitability, string> = {
  confirmed: 'Confirmed match',
  unconfirmed: 'Unconfirmed',
  below_requirement: 'Below requirement',
};
const AVAILABILITY_SHORT: Record<SkAvailability, string> = {
  capacity_indicated: 'Capacity indicated',
  uncertain: 'Uncertain',
  committed: 'Committed',
  unavailable: 'No hours',
};

/** Read-only candidate finder. Recommendations never assign anyone. */
export function SkillCandidatePanel({ teamId: fixedTeamId }: { teamId?: string }) {
  const { showError } = useToast();
  const queryClient = useQueryClient();
  const [projectSearch, setProjectSearch] = useState('');
  const [project, setProject] = useState<Project | null>(null);
  const [adHoc, setAdHoc] = useState<SkRequirementSpec[]>([]);
  const [reqSkill, setReqSkill] = useState('');
  const [reqLevel, setReqLevel] = useState('3');
  const [reqMandatory, setReqMandatory] = useState(true);
  const [teamId, setTeamId] = useState(fixedTeamId ?? '');
  const [periods, setPeriods] = useState('4');
  const [result, setResult] = useState<SkMatchResult | null>(null);

  const taxonomyQuery = useQuery({ queryKey: skillQueryKeys.taxonomy(false), queryFn: () => fetchSkillTaxonomy(false) });
  const teamsQuery = useQuery({ queryKey: ['lookups', 'teams'], queryFn: () => fetchTeams() });
  const projectsQuery = useQuery({
    queryKey: ['skills', 'project-search', projectSearch],
    queryFn: () => getProjects({ q: projectSearch || undefined, lifecycle: 'active', page_size: 25 }),
  });
  const requirementsQuery = useQuery({
    queryKey: skillQueryKeys.requirements(project?.id ?? ''),
    queryFn: () => fetchProjectSkillRequirements(project!.id),
    enabled: Boolean(project),
  });

  const levels = taxonomyQuery.data?.proficiency_levels ?? [];
  const skills = taxonomyQuery.data?.skills ?? [];
  const skillName = (id: string) => skills.find((s) => s.id === id)?.name ?? id;
  const onError = (err: unknown) => showError(getErrorMessage(err));

  const requirementMutation = useMutation({
    mutationFn: (fn: () => Promise<unknown>) => fn(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: skillQueryKeys.requirements(project?.id ?? '') });
      void queryClient.invalidateQueries({ queryKey: ['skills', 'gaps'] });
      setReqSkill('');
    },
    onError,
  });
  const matchMutation = useMutation({
    mutationFn: () =>
      matchSkillCandidates({
        project_id: project?.id,
        requirements: project ? undefined : adHoc,
        team_id: teamId || undefined,
        granularity: 'week',
        periods: Number(periods),
      }),
    onSuccess: setResult,
    onError,
  });

  const requirements = project ? requirementsQuery.data?.requirements ?? [] : adHoc;
  const canEdit = project ? Boolean(requirementsQuery.data?.can_edit) : true;
  const addRequirement = () => {
    if (!reqSkill) return;
    if (project) {
      requirementMutation.mutate(() =>
        setProjectSkillRequirement(project.id, { skill_id: reqSkill, min_level: Number(reqLevel), is_mandatory: reqMandatory, note: null }),
      );
    } else {
      setAdHoc((prev) => [...prev.filter((r) => r.skill_id !== reqSkill), { skill_id: reqSkill, min_level: Number(reqLevel), is_mandatory: reqMandatory }]);
      setReqSkill('');
    }
  };

  return (
    <Stack spacing={2}>
      <Alert severity="info">
        Skill suitability and availability are shown side by side and never combined into a score. Only verified skills
        make a confirmed match. Availability uses the preliminary capacity forecast. Recommendations never assign
        anyone; assignment stays a manager decision.
      </Alert>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5}>
          <Autocomplete
            sx={{ minWidth: 320, flex: 1 }}
            size="small"
            options={projectsQuery.data ?? []}
            value={project}
            onChange={(_, value) => {
              setProject(value);
              setResult(null);
            }}
            onInputChange={(_, value, reason) => reason === 'input' && setProjectSearch(value)}
            getOptionLabel={(p) => `${p.tool_number}${p.part_description ? ` — ${p.part_description}` : ''}`}
            isOptionEqualToValue={(a, b) => a.id === b.id}
            renderInput={(params) => <TextField {...params} label="Project (optional — leave empty for an ad-hoc search)" />}
          />
          {fixedTeamId ? null : (
            <FilterSelect label="Team" value={teamId} onChange={(e) => setTeamId(e.target.value)} sx={{ minWidth: 180, maxWidth: 240 }}>
              <MenuItem value="">All teams in scope</MenuItem>
              {(teamsQuery.data ?? []).map((t) => (
                <MenuItem key={t.id} value={t.id}>
                  {t.name}
                </MenuItem>
              ))}
            </FilterSelect>
          )}
          <FilterSelect label="Horizon" value={periods} onChange={(e) => setPeriods(e.target.value)} sx={{ minWidth: 140, maxWidth: 160 }}>
            {['2', '4', '8', '12'].map((p) => (
              <MenuItem key={p} value={p}>
                {p} weeks
              </MenuItem>
            ))}
          </FilterSelect>
        </Stack>

        <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>
          {project ? `Skill requirements recorded on ${project.tool_number}` : 'Skill requirements for this search'}
        </Typography>
        {requirementsQuery.error ? <ErrorState error={requirementsQuery.error} /> : null}
        {requirements.length ? (
          <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap', mb: 1 }}>
            {requirements.map((r) => {
              const id = 'id' in r ? (r as { id: string }).id : r.skill_id;
              return (
                <Chip
                  key={id}
                  label={`${'skill_name' in r && r.skill_name ? r.skill_name : skillName(r.skill_id)} ≥ L${r.min_level}${r.is_mandatory ? '' : ' (optional)'}`}
                  onDelete={
                    canEdit
                      ? () =>
                          project
                            ? requirementMutation.mutate(() => removeProjectSkillRequirement(project.id, id))
                            : setAdHoc((prev) => prev.filter((x) => x.skill_id !== r.skill_id))
                      : undefined
                  }
                  deleteIcon={<DeleteOutlineRoundedIcon />}
                />
              );
            })}
          </Stack>
        ) : (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            No requirements yet.
          </Typography>
        )}
        {canEdit ? (
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} sx={{ alignItems: { md: 'center' } }}>
            <FilterSelect label="Skill" value={reqSkill} onChange={(e) => setReqSkill(e.target.value)} sx={{ minWidth: 220, maxWidth: 300 }}>
              <MenuItem value="">Select a skill</MenuItem>
              {skills.map((s) => (
                <MenuItem key={s.id} value={s.id}>
                  {s.name}
                </MenuItem>
              ))}
            </FilterSelect>
            <FilterSelect label="Minimum level" value={reqLevel} onChange={(e) => setReqLevel(e.target.value)} sx={{ minWidth: 170, maxWidth: 200 }}>
              {levels.map((l) => (
                <MenuItem key={l.level} value={String(l.level)}>
                  {l.level} — {l.name}
                </MenuItem>
              ))}
            </FilterSelect>
            <FormControlLabel control={<Checkbox checked={reqMandatory} onChange={(e) => setReqMandatory(e.target.checked)} />} label="Mandatory" />
            <Button variant="outlined" disabled={!reqSkill || requirementMutation.isPending} onClick={addRequirement}>
              {project ? 'Save requirement' : 'Add'}
            </Button>
          </Stack>
        ) : project ? (
          <Typography variant="caption" color="text.secondary">
            You can read this project&apos;s requirements but not change them.
          </Typography>
        ) : null}

        <Box sx={{ mt: 2 }}>
          <Button variant="contained" disabled={!requirements.length || matchMutation.isPending} onClick={() => matchMutation.mutate()}>
            Find candidates
          </Button>
        </Box>
      </Paper>

      {result ? (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="subtitle1">
            {result.summary.candidates} people · {result.summary.confirmed} confirmed ({result.summary.confirmed_with_capacity_indicated} with capacity
            indicated) · {result.summary.unconfirmed} unconfirmed · {result.summary.below_requirement} below requirement
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Horizon {formatDate(result.horizon_start)} – {formatDate(result.horizon_end)} · capacity status {result.capacity_status}
          </Typography>
          <Table size="small" sx={{ mt: 1 }}>
            <TableHead>
              <TableRow>
                <TableCell>Person</TableCell>
                <TableCell>Skill suitability</TableCell>
                <TableCell>Availability</TableCell>
                <TableCell align="right">Allocatable h</TableCell>
                <TableCell align="right">Approved remaining h</TableCell>
                <TableCell>Why</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {result.candidates.map((c) => (
                <TableRow key={c.user_id} hover>
                  <TableCell>
                    {c.name}
                    <Typography variant="caption" color="text.secondary" component="div">
                      {c.team_name ?? 'No team'}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip size="small" color={SUITABILITY_COLOR[c.suitability]} label={SUITABILITY_SHORT[c.suitability]} title={c.suitability_label} />
                  </TableCell>
                  <TableCell>
                    <Chip size="small" variant="outlined" color={AVAILABILITY_COLOR[c.availability]} label={AVAILABILITY_SHORT[c.availability]} title={c.availability_reason} />
                  </TableCell>
                  <TableCell align="right">{formatNumber(c.allocatable_hours, 1)}</TableCell>
                  <TableCell align="right">
                    {formatNumber(c.approved_remaining_hours, 1)}
                    {c.open_assignments_without_estimate ? (
                      <Typography variant="caption" color="text.secondary" component="div">
                        +{c.open_assignments_without_estimate} without estimate
                      </Typography>
                    ) : null}
                  </TableCell>
                  <TableCell>
                    {c.explanation.map((line) => (
                      <Typography key={line} variant="caption" component="div">
                        {line}
                      </Typography>
                    ))}
                    <Typography variant="caption" color="text.secondary" component="div">
                      {c.availability_reason}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Stack component="ul" sx={{ m: 0, mt: 1.5, pl: 2 }}>
            {[...result.rules, ...result.capacity_limitations].map((line) => (
              <li key={line}>
                <Typography variant="caption" color="text.secondary">
                  {line}
                </Typography>
              </li>
            ))}
          </Stack>
        </Paper>
      ) : null}
    </Stack>
  );
}
