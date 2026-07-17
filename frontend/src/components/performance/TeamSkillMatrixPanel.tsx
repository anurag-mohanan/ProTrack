import { useEffect, useMemo, useState } from 'react';
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
  Select,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient, getErrorMessage } from '../../api/client';
import { fetchStreams } from '../../api/lookups';
import { LoadingState } from '../common/LoadingState';
import { FilterSelect } from '../ui/design-system/FilterSelect';
import { useToast } from '../../context/ToastContext';

type ProficiencyScaleItem = {
  value: string;
  label: string;
  short_label: string;
  tone: string;
  guidance: string;
};

type SkillColumn = { id: string; name: string; sort_order: number };

type SkillMatrixPerson = {
  user_id: string;
  name: string;
  role?: string | null;
  primary_tool?: string | null;
  work_function?: string | null;
  team_id?: string | null;
  team_name?: string | null;
  stream_name?: string | null;
  company_experience?: string | null;
  industry_experience?: string | null;
  ratings: Record<string, string | null>;
};

type SkillMatrix = {
  team_id?: string | null;
  stream_id?: string | null;
  stream_name?: string | null;
  title: string;
  proficiency_scale: ProficiencyScaleItem[];
  skills: SkillColumn[];
  people: SkillMatrixPerson[];
};

type TeamOption = { id: string; name: string };

const TONE_COLORS: Record<string, { bg: string; fg: string }> = {
  error: { bg: '#c62828', fg: '#fff' },
  warning: { bg: '#ef6c00', fg: '#fff' },
  success: { bg: '#2e7d32', fg: '#fff' },
  info: { bg: '#1565c0', fg: '#fff' },
  neutral: { bg: '#eceff1', fg: '#455a64' },
};

function cellColor(scale: ProficiencyScaleItem[], value?: string | null) {
  if (!value) return TONE_COLORS.neutral;
  const match = scale.find((row) => row.value === value);
  return TONE_COLORS[match?.tone ?? 'neutral'] ?? TONE_COLORS.neutral;
}

type TeamSkillMatrixPanelProps = {
  canManage: boolean;
  defaultTeamId?: string;
};

export function TeamSkillMatrixPanel({ canManage, defaultTeamId = '' }: TeamSkillMatrixPanelProps) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [teamId, setTeamId] = useState(defaultTeamId);
  const [streamId, setStreamId] = useState('');
  const [draft, setDraft] = useState<Record<string, Record<string, string | null>>>({});
  const showAllTeams = !teamId;

  const teamsQuery = useQuery({
    queryKey: ['performance', 'teams'],
    queryFn: async () => (await apiClient.get<TeamOption[]>('/hr/teams')).data,
  });

  const streamsQuery = useQuery({
    queryKey: ['lookups', 'streams'],
    queryFn: () => fetchStreams(),
  });

  useEffect(() => {
    if (defaultTeamId && !teamId) {
      setTeamId(defaultTeamId);
    }
  }, [defaultTeamId, teamId]);

  const matrixQuery = useQuery({
    queryKey: ['performance', 'skill-matrix', teamId || 'all', streamId || 'auto'],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (teamId) params.set('team_id', teamId);
      if (streamId) params.set('stream_id', streamId);
      const query = params.toString();
      return (
        await apiClient.get<SkillMatrix>(
          `/hr/performance/skill-matrix${query ? `?${query}` : ''}`,
        )
      ).data;
    },
  });

  useEffect(() => {
    if (!matrixQuery.data) return;
    const next: Record<string, Record<string, string | null>> = {};
    for (const person of matrixQuery.data.people) {
      next[person.user_id] = { ...person.ratings };
    }
    setDraft(next);
    if (matrixQuery.data.stream_id && !streamId) {
      setStreamId(matrixQuery.data.stream_id);
    }
  }, [matrixQuery.data]);

  const dirtyRatings = useMemo(() => {
    if (!matrixQuery.data) return [];
    const rows: Array<{ user_id: string; stream_skill_id: string; proficiency: string | null }> = [];
    for (const person of matrixQuery.data.people) {
      for (const skill of matrixQuery.data.skills) {
        const current = draft[person.user_id]?.[skill.id] ?? null;
        const original = person.ratings[skill.id] ?? null;
        if (current !== original) {
          rows.push({
            user_id: person.user_id,
            stream_skill_id: skill.id,
            proficiency: current,
          });
        }
      }
    }
    return rows;
  }, [draft, matrixQuery.data]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const params = new URLSearchParams();
      if (teamId) params.set('team_id', teamId);
      if (streamId) params.set('stream_id', streamId);
      const query = params.toString();
      return (
        await apiClient.put(`/hr/performance/skill-matrix${query ? `?${query}` : ''}`, {
          ratings: dirtyRatings,
        })
      ).data;
    },
    onSuccess: () => {
      showSuccess('Skill matrix saved');
      queryClient.invalidateQueries({ queryKey: ['performance', 'skill-matrix'] });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  if (teamsQuery.isLoading) return <LoadingState message="Loading teams…" />;

  const matrix = matrixQuery.data;
  const scale = matrix?.proficiency_scale ?? [];

  return (
    <Box>
      <Stack
        direction={{ xs: 'column', md: 'row' }}
        spacing={1.5}
        sx={{ mb: 2, alignItems: { md: 'center' }, justifyContent: 'space-between' }}
      >
        <Box>
          <Typography sx={{ fontWeight: 800, fontSize: 16 }}>
            {matrix?.title || 'Team skillset chart'}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Industry-style proficiency grid (Learning → Expert). Choose All teams for a cross-team
            view, or one team to focus. Skills follow the selected stream.
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
          <FilterSelect
            label="Team"
            value={teamId}
            fullWidth={false}
            sx={{ minWidth: 200 }}
            onChange={(e) => {
              setTeamId(String(e.target.value));
              setStreamId('');
            }}
          >
            <MenuItem value="">All teams</MenuItem>
            {(teamsQuery.data ?? []).map((team) => (
              <MenuItem key={team.id} value={team.id}>
                {team.name}
              </MenuItem>
            ))}
          </FilterSelect>
          <FilterSelect
            label="Stream"
            value={streamId}
            fullWidth={false}
            sx={{ minWidth: 180 }}
            onChange={(e) => setStreamId(String(e.target.value))}
          >
            <MenuItem value="">Auto from team</MenuItem>
            {(streamsQuery.data ?? []).map((stream) => (
              <MenuItem key={stream.id} value={stream.id}>
                {stream.name}
              </MenuItem>
            ))}
          </FilterSelect>
          {canManage ? (
            <Button
              variant="contained"
              disabled={!dirtyRatings.length || saveMutation.isPending}
              onClick={() => saveMutation.mutate()}
            >
              Save ratings
            </Button>
          ) : null}
        </Stack>
      </Stack>

      <Stack direction="row" spacing={1} sx={{ mb: 1.5, flexWrap: 'wrap' }}>
        {scale.map((row) => {
          const color = cellColor(scale, row.value);
          return (
            <Chip
              key={row.value}
              size="small"
              label={`${row.label}`}
              sx={{ bgcolor: color.bg, color: color.fg, fontWeight: 700 }}
              title={row.guidance}
            />
          );
        })}
      </Stack>

      {matrixQuery.isLoading ? (
        <LoadingState message="Loading skill matrix…" />
      ) : !matrix ? (
        <Typography color="text.secondary">Unable to load the skillset chart.</Typography>
      ) : matrix.people.length === 0 ? (
        <Typography color="text.secondary">
          No team members with this stream assigned. Set Stream on each user in Admin → Users.
        </Typography>
      ) : (
        <Box sx={{ overflow: 'auto', border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 800, minWidth: 140 }}>Designer</TableCell>
                {showAllTeams ? (
                  <TableCell sx={{ fontWeight: 800, minWidth: 120 }}>Team</TableCell>
                ) : null}
                <TableCell sx={{ fontWeight: 800, minWidth: 110 }}>Role</TableCell>
                <TableCell sx={{ fontWeight: 800, minWidth: 90 }}>CAD</TableCell>
                <TableCell sx={{ fontWeight: 800, minWidth: 110 }}>Function</TableCell>
                <TableCell sx={{ fontWeight: 800, minWidth: 90 }}>Exp company</TableCell>
                <TableCell sx={{ fontWeight: 800, minWidth: 90 }}>Exp industry</TableCell>
                {matrix.skills.map((skill) => (
                  <TableCell
                    key={skill.id}
                    align="center"
                    sx={{
                      fontWeight: 800,
                      fontSize: 10,
                      writingMode: 'vertical-rl',
                      transform: 'rotate(180deg)',
                      height: 120,
                      px: 0.5,
                    }}
                  >
                    {skill.name}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {matrix.people.map((person) => (
                <TableRow key={person.user_id} hover>
                  <TableCell sx={{ fontWeight: 700, fontSize: 12 }}>{person.name}</TableCell>
                  {showAllTeams ? (
                    <TableCell sx={{ fontSize: 11 }}>{person.team_name || '—'}</TableCell>
                  ) : null}
                  <TableCell sx={{ fontSize: 11 }}>{person.role || '—'}</TableCell>
                  <TableCell sx={{ fontSize: 11 }}>{person.primary_tool || '—'}</TableCell>
                  <TableCell sx={{ fontSize: 11 }}>{person.work_function || '—'}</TableCell>
                  <TableCell sx={{ fontSize: 11 }}>{person.company_experience || '—'}</TableCell>
                  <TableCell sx={{ fontSize: 11 }}>{person.industry_experience || '—'}</TableCell>
                  {matrix.skills.map((skill) => {
                    const value = draft[person.user_id]?.[skill.id] ?? null;
                    const color = cellColor(scale, value);
                    if (!canManage) {
                      return (
                        <TableCell key={skill.id} align="center" sx={{ p: 0.4 }}>
                          <Box
                            sx={{
                              width: 28,
                              height: 28,
                              mx: 'auto',
                              borderRadius: 0.75,
                              bgcolor: color.bg,
                              color: color.fg,
                              display: 'grid',
                              placeItems: 'center',
                              fontSize: 10,
                              fontWeight: 800,
                            }}
                          >
                            {scale.find((row) => row.value === value)?.short_label || '·'}
                          </Box>
                        </TableCell>
                      );
                    }
                    return (
                      <TableCell key={skill.id} align="center" sx={{ p: 0.35 }}>
                        <Select
                          size="small"
                          value={value || ''}
                          displayEmpty
                          onChange={(e) => {
                            const next = e.target.value || null;
                            setDraft((current) => ({
                              ...current,
                              [person.user_id]: {
                                ...(current[person.user_id] || {}),
                                [skill.id]: next,
                              },
                            }));
                          }}
                          sx={{
                            minWidth: 52,
                            bgcolor: color.bg,
                            color: color.fg,
                            fontWeight: 700,
                            fontSize: 11,
                            '& .MuiSelect-icon': { color: color.fg },
                            '& .MuiOutlinedInput-notchedOutline': { border: 0 },
                          }}
                        >
                          <MenuItem value="">
                            <em>—</em>
                          </MenuItem>
                          {scale.map((row) => (
                            <MenuItem key={row.value} value={row.value}>
                              {row.label}
                            </MenuItem>
                          ))}
                        </Select>
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      )}
    </Box>
  );
}
