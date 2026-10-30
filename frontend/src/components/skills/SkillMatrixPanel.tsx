import { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { fetchTeams } from '../../api/lookups';
import { fetchSkillMatrix, fetchSkillReviewQueue, fetchSkillTaxonomy, skillQueryKeys } from '../../api/skills';
import type { SkAccess, SkMatrixParams, SkState } from '../../types/Skills';
import { formatDate } from '../../utils/format';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { FilterSelect } from '../ui/design-system/FilterSelect';
import { levelText } from './skillFormat';
import { HeatCell, HeatLegend, StateChip } from './skillUi';
import { SkillProfileDrawer } from './SkillProfileDrawer';

const STATE_FILTERS: { value: SkState; label: string }[] = [
  { value: 'verified', label: 'Verified' },
  { value: 'claimed', label: 'Self-declared / unverified' },
  { value: 'reassessment', label: 'Needs reassessment' },
  { value: 'rejected', label: 'Not confirmed' },
  { value: 'no_record', label: 'No record' },
];

export function SkillMatrixPanel({ access }: { access: SkAccess }) {
  const [view, setView] = useState<'heatmap' | 'table'>('heatmap');
  const [teamId, setTeamId] = useState('');
  const [category, setCategory] = useState('');
  const [kind, setKind] = useState('');
  const [software, setSoftware] = useState('');
  const [minLevel, setMinLevel] = useState('');
  const [states, setStates] = useState<string[]>([]);
  const [search, setSearch] = useState('');
  const [criticalOnly, setCriticalOnly] = useState(false);
  const [drawer, setDrawer] = useState<{ userId: string; skillId?: string } | null>(null);

  const params: SkMatrixParams = {
    team_id: teamId || undefined,
    category: category || undefined,
    kind: kind || undefined,
    software_skill_id: software || undefined,
    min_level: minLevel ? Number(minLevel) : undefined,
    state: states.length ? states : undefined,
    q: search.trim() || undefined,
    critical_only: criticalOnly || undefined,
  };
  const matrixQuery = useQuery({
    queryKey: skillQueryKeys.matrix(params),
    queryFn: () => fetchSkillMatrix(params),
    placeholderData: keepPreviousData,
  });
  const taxonomyQuery = useQuery({ queryKey: skillQueryKeys.taxonomy(false), queryFn: () => fetchSkillTaxonomy(false) });
  const teamsQuery = useQuery({ queryKey: ['lookups', 'teams'], queryFn: () => fetchTeams() });
  const queueQuery = useQuery({ queryKey: skillQueryKeys.queue, queryFn: fetchSkillReviewQueue, enabled: access.can_review });

  const data = matrixQuery.data;
  const levels = data?.proficiency_levels ?? [];
  const softwareSkills = (taxonomyQuery.data?.skills ?? []).filter((s) => s.kind === 'software');

  const tableRows = useMemo(() => {
    if (!data) return [];
    const includeMissing = states.includes('no_record');
    return data.people.flatMap((person) =>
      data.skills
        .map((skill) => ({ person, skill, cell: person.cells[skill.id] }))
        .filter(({ cell }) => cell && cell.matches && (cell.state !== 'no_record' || includeMissing)),
    );
  }, [data, states]);

  const categoryGroups = useMemo(() => {
    const groups: { category: string; count: number }[] = [];
    (data?.skills ?? []).forEach((s) => {
      const key = s.category || 'Uncategorised';
      const last = groups[groups.length - 1];
      if (last && last.category === key) last.count += 1;
      else groups.push({ category: key, count: 1 });
    });
    return groups;
  }, [data]);

  return (
    <Stack spacing={2}>
      {access.can_review && queueQuery.data && queueQuery.data.length ? (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="subtitle1" gutterBottom>
            Awaiting your review ({queueQuery.data.length})
          </Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Employee</TableCell>
                <TableCell>Skill</TableCell>
                <TableCell>Reason</TableCell>
                <TableCell>Claim</TableCell>
                <TableCell>Verified</TableCell>
                <TableCell>Since</TableCell>
                <TableCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {queueQuery.data.slice(0, 15).map((q) => (
                <TableRow key={q.record_id} hover>
                  <TableCell>{q.name}</TableCell>
                  <TableCell>{q.skill_name}</TableCell>
                  <TableCell>{q.reason}</TableCell>
                  <TableCell>{levelText(levels, q.declared_level)}</TableCell>
                  <TableCell>{levelText(levels, q.verified_level)}</TableCell>
                  <TableCell>{q.since ? formatDate(q.since) : '—'}</TableCell>
                  <TableCell align="right">
                    <Button size="small" onClick={() => setDrawer({ userId: q.user_id, skillId: q.skill_id })}>
                      Review
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Paper>
      ) : null}

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack direction={{ xs: 'column', lg: 'row' }} spacing={1.5} useFlexGap sx={{ flexWrap: 'wrap' }}>
          <FilterSelect label="Team" value={teamId} onChange={(e) => setTeamId(e.target.value)} sx={{ minWidth: 160, maxWidth: 220 }}>
            <MenuItem value="">All teams in scope</MenuItem>
            {(teamsQuery.data ?? []).map((t) => (
              <MenuItem key={t.id} value={t.id}>
                {t.name}
              </MenuItem>
            ))}
          </FilterSelect>
          <FilterSelect label="Category" value={category} onChange={(e) => setCategory(e.target.value)} sx={{ minWidth: 160, maxWidth: 240 }}>
            <MenuItem value="">All categories</MenuItem>
            {(taxonomyQuery.data?.categories ?? []).map((c) => (
              <MenuItem key={c} value={c}>
                {c}
              </MenuItem>
            ))}
          </FilterSelect>
          <FilterSelect label="Type" value={kind} onChange={(e) => setKind(e.target.value)} sx={{ minWidth: 140, maxWidth: 200 }}>
            <MenuItem value="">All types</MenuItem>
            {(taxonomyQuery.data?.kinds ?? []).map((k) => (
              <MenuItem key={k.value} value={k.value}>
                {k.label}
              </MenuItem>
            ))}
          </FilterSelect>
          <FilterSelect label="Uses software" value={software} onChange={(e) => setSoftware(e.target.value)} sx={{ minWidth: 150, maxWidth: 200 }}>
            <MenuItem value="">Any</MenuItem>
            {softwareSkills.map((s) => (
              <MenuItem key={s.id} value={s.id}>
                {s.name}
              </MenuItem>
            ))}
          </FilterSelect>
          <FilterSelect label="Min level" value={minLevel} onChange={(e) => setMinLevel(e.target.value)} sx={{ minWidth: 130, maxWidth: 180 }}>
            <MenuItem value="">Any</MenuItem>
            {levels.map((l) => (
              <MenuItem key={l.level} value={String(l.level)}>
                {l.level}+ {l.name}
              </MenuItem>
            ))}
          </FilterSelect>
          <FormControl size="small" sx={{ minWidth: 160, maxWidth: 260 }}>
            <InputLabel shrink>Status</InputLabel>
            <Select<string[]>
              multiple
              displayEmpty
              notched
              label="Status"
              value={states}
              onChange={(e) => setStates(typeof e.target.value === 'string' ? e.target.value.split(',') : e.target.value)}
              renderValue={(selected) =>
                selected.length ? selected.map((v) => STATE_FILTERS.find((s) => s.value === v)?.label ?? v).join(', ') : 'All'
              }
            >
              {STATE_FILTERS.map((s) => (
                <MenuItem key={s.value} value={s.value}>
                  <Checkbox size="small" checked={states.includes(s.value)} />
                  {s.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField size="small" label="Search person or skill" value={search} onChange={(e) => setSearch(e.target.value)} sx={{ minWidth: 200 }} />
          <FormControlLabel control={<Checkbox checked={criticalOnly} onChange={(e) => setCriticalOnly(e.target.checked)} />} label="Critical only" />
          <ToggleButtonGroup size="small" exclusive value={view} onChange={(_, v) => v && setView(v)}>
            <ToggleButton value="heatmap">Heatmap</ToggleButton>
            <ToggleButton value="table">Table</ToggleButton>
          </ToggleButtonGroup>
        </Stack>
      </Paper>

      {matrixQuery.isLoading ? <LoadingState message="Loading skills matrix…" /> : null}
      {matrixQuery.error ? <ErrorState error={matrixQuery.error} onRetry={() => void matrixQuery.refetch()} /> : null}

      {data ? (
        <>
          <HeatLegend levels={levels} />
          {!data.people.length || !data.skills.length ? (
            <Alert severity="info">No people or skills match these filters.</Alert>
          ) : view === 'heatmap' ? (
            <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: '70vh' }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ minWidth: 200 }} />
                    {categoryGroups.map((g) => (
                      <TableCell key={g.category} colSpan={g.count} align="center" sx={{ fontWeight: 600, borderLeft: 1, borderColor: 'divider' }}>
                        {g.category}
                      </TableCell>
                    ))}
                    <TableCell />
                  </TableRow>
                  <TableRow>
                    <TableCell sx={{ top: 37 }}>Employee</TableCell>
                    {data.skills.map((s) => (
                      <TableCell key={s.id} align="center" sx={{ top: 37, px: 0.5, verticalAlign: 'bottom' }}>
                        <Box sx={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)', whiteSpace: 'nowrap', fontSize: 12, mx: 'auto', maxHeight: 160 }}>
                          {s.name}
                          {s.is_critical ? ' ★' : ''}
                        </Box>
                      </TableCell>
                    ))}
                    <TableCell sx={{ top: 37 }}>Training</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.people.map((person) => (
                    <TableRow key={person.user_id} hover>
                      <TableCell>
                        <Button size="small" sx={{ textTransform: 'none', p: 0, minWidth: 0 }} onClick={() => setDrawer({ userId: person.user_id })}>
                          {person.name}
                        </Button>
                        <Typography variant="caption" color="text.secondary" component="div">
                          {person.team_name ?? 'No team'}
                        </Typography>
                      </TableCell>
                      {data.skills.map((s) => {
                        const cell = person.cells[s.id];
                        return (
                          <TableCell key={s.id} align="center" sx={{ px: 0.25 }}>
                            <HeatCell
                              cell={cell}
                              levels={levels}
                              dimmed={!cell.matches}
                              onClick={() => setDrawer({ userId: person.user_id, skillId: s.id })}
                            />
                          </TableCell>
                        );
                      })}
                      <TableCell>{person.training_plans_open ? `${person.training_plans_open} open` : '—'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          ) : (
            <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: '70vh' }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>Employee</TableCell>
                    <TableCell>Team</TableCell>
                    <TableCell>Category</TableCell>
                    <TableCell>Skill</TableCell>
                    <TableCell>Proficiency</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Last verified</TableCell>
                    <TableCell>Training</TableCell>
                    <TableCell />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {tableRows.map(({ person, skill, cell }) => (
                    <TableRow key={`${person.user_id}:${skill.id}`} hover>
                      <TableCell>{person.name}</TableCell>
                      <TableCell>{person.team_name ?? '—'}</TableCell>
                      <TableCell>{skill.category ?? '—'}</TableCell>
                      <TableCell>
                        {skill.name}
                        {skill.is_critical ? ' ★' : ''}
                      </TableCell>
                      <TableCell>
                        {cell.state === 'verified' || cell.state === 'reassessment'
                          ? levelText(levels, cell.verified_level)
                          : cell.declared_level
                            ? `Claims ${levelText(levels, cell.declared_level)}`
                            : '—'}
                      </TableCell>
                      <TableCell>
                        <StateChip state={cell.state} />
                      </TableCell>
                      <TableCell>{cell.last_verified_at ? formatDate(cell.last_verified_at) : '—'}</TableCell>
                      <TableCell>{person.training_plans_open ? `${person.training_plans_open} open` : '—'}</TableCell>
                      <TableCell align="right">
                        <Button size="small" onClick={() => setDrawer({ userId: person.user_id, skillId: skill.id })}>
                          {person.can_review ? 'Assess' : 'Open'}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                  {!tableRows.length ? (
                    <TableRow>
                      <TableCell colSpan={9}>
                        <Typography variant="body2" color="text.secondary">
                          No recorded skills match. Choose the “No record” status to list unknown cells.
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ) : null}
                </TableBody>
              </Table>
            </TableContainer>
          )}
          <Stack component="ul" sx={{ m: 0, pl: 2 }}>
            {data.legend.map((line) => (
              <li key={line}>
                <Typography variant="caption" color="text.secondary">
                  {line}
                </Typography>
              </li>
            ))}
          </Stack>
        </>
      ) : null}

      <SkillProfileDrawer userId={drawer?.userId ?? null} initialSkillId={drawer?.skillId} onClose={() => setDrawer(null)} />
    </Stack>
  );
}
