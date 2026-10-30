import { useState, type ReactNode } from 'react';
import {
  Alert,
  Box,
  Checkbox,
  Chip,
  FormControlLabel,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { fetchTeams } from '../../api/lookups';
import { fetchSkillGaps, fetchSkillTaxonomy, skillQueryKeys } from '../../api/skills';
import type { SkGapParams } from '../../types/Skills';
import { formatDate } from '../../utils/format';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { FilterSelect } from '../ui/design-system/FilterSelect';

const FLAG_LABELS: Record<string, string> = {
  no_verified_coverage: 'No verified coverage',
  single_verified_specialist: 'Single verified specialist',
  no_verified_specialist: 'No verified specialist',
  below_coverage_target: 'Below coverage target',
  reassessment_pending: 'Reassessment pending',
};
const SEVERITY_COLOR = { high: 'error', medium: 'warning', info: 'info' } as const;
const DEPTH_COLOR = { none: 'error', single: 'warning', adequate: 'success' } as const;

export function SkillGapsPanel() {
  const [teamId, setTeamId] = useState('');
  const [category, setCategory] = useState('');
  const [kind, setKind] = useState('');
  const [minLevel, setMinLevel] = useState('1');
  const [criticalOnly, setCriticalOnly] = useState(false);
  const params: SkGapParams = {
    team_id: teamId || undefined,
    category: category || undefined,
    kind: kind || undefined,
    min_level: Number(minLevel),
    critical_only: criticalOnly || undefined,
  };
  const gapsQuery = useQuery({ queryKey: skillQueryKeys.gaps(params), queryFn: () => fetchSkillGaps(params), placeholderData: keepPreviousData });
  const taxonomyQuery = useQuery({ queryKey: skillQueryKeys.taxonomy(false), queryFn: () => fetchSkillTaxonomy(false) });
  const teamsQuery = useQuery({ queryKey: ['lookups', 'teams'], queryFn: () => fetchTeams() });
  const report = gapsQuery.data;
  const levels = taxonomyQuery.data?.proficiency_levels ?? [];

  return (
    <Stack spacing={2}>
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} useFlexGap sx={{ flexWrap: 'wrap' }}>
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
          <FilterSelect label="Count holders at" value={minLevel} onChange={(e) => setMinLevel(e.target.value)} sx={{ minWidth: 150, maxWidth: 200 }}>
            {levels.map((l) => (
              <MenuItem key={l.level} value={String(l.level)}>
                {l.level}+ {l.name}
              </MenuItem>
            ))}
          </FilterSelect>
          <FormControlLabel control={<Checkbox checked={criticalOnly} onChange={(e) => setCriticalOnly(e.target.checked)} />} label="Critical only" />
        </Stack>
      </Paper>

      {gapsQuery.isLoading ? <LoadingState message="Analysing coverage…" /> : null}
      {gapsQuery.error ? <ErrorState error={gapsQuery.error} onRetry={() => void gapsQuery.refetch()} /> : null}
      {report ? (
        <>
          <Alert severity="info">
            <Stack component="ul" sx={{ m: 0, pl: 2 }}>
              {report.rules.map((rule) => (
                <li key={rule}>
                  <Typography variant="caption">{rule}</Typography>
                </li>
              ))}
            </Stack>
          </Alert>

          <Section title={`Findings (${report.findings.length})`}>
            {report.findings.length ? (
              <Stack spacing={1}>
                {report.findings.map((f) => (
                  <Alert key={`${f.code}:${f.skill_id}`} severity={SEVERITY_COLOR[f.severity]} variant="outlined">
                    {f.explanation}
                  </Alert>
                ))}
              </Stack>
            ) : (
              <Typography variant="body2" color="text.secondary">
                No findings. Critical skills are flagged by management in the taxonomy; none may be marked yet.
              </Typography>
            )}
          </Section>

          <Section title={`Coverage by skill — ${report.population} people in scope`}>
            <TableContainer sx={{ maxHeight: 520 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>Skill</TableCell>
                    <TableCell align="right">Verified</TableCell>
                    <TableCell align="right">At min level</TableCell>
                    <TableCell>Specialists</TableCell>
                    <TableCell align="right">Unverified claims</TableCell>
                    <TableCell align="right">Reassessment</TableCell>
                    <TableCell align="right">No record (unknown)</TableCell>
                    <TableCell>Flags</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {report.skills.map((s) => (
                    <TableRow key={s.skill_id} hover>
                      <TableCell>
                        {s.skill_name}
                        {s.is_critical ? <Chip size="small" color="error" label="Critical" sx={{ ml: 1 }} /> : null}
                        <Typography variant="caption" color="text.secondary" component="div">
                          {s.category ?? '—'}
                          {s.min_verified_coverage ? ` · target ${s.min_verified_coverage} verified` : ''}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">{s.verified_count}</TableCell>
                      <TableCell align="right">{s.verified_at_min_level}</TableCell>
                      <TableCell>
                        {s.verified_specialists} at L{s.specialist_level}+
                        {s.specialist_names.length ? (
                          <Typography variant="caption" color="text.secondary" component="div">
                            {s.specialist_names.join(', ')}
                          </Typography>
                        ) : null}
                      </TableCell>
                      <TableCell align="right">{s.claimed_unverified}</TableCell>
                      <TableCell align="right">{s.reassessment_due}</TableCell>
                      <TableCell align="right">{s.no_record}</TableCell>
                      <TableCell>
                        <Stack direction="row" spacing={0.5} useFlexGap sx={{ flexWrap: 'wrap' }}>
                          {s.flags.map((flag) => (
                            <Chip key={flag} size="small" variant="outlined" label={FLAG_LABELS[flag] ?? flag} />
                          ))}
                        </Stack>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Section>

          {report.team_depth.length ? (
            <Section title="Specialist depth by team (critical skills)">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Team</TableCell>
                    <TableCell>Skill</TableCell>
                    <TableCell align="right">Members</TableCell>
                    <TableCell align="right">Verified specialists</TableCell>
                    <TableCell>Depth</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {report.team_depth.map((d) => (
                    <TableRow key={`${d.team_id}:${d.skill_id}`}>
                      <TableCell>{d.team_name}</TableCell>
                      <TableCell>{d.skill_name}</TableCell>
                      <TableCell align="right">{d.members}</TableCell>
                      <TableCell align="right">{d.verified_specialists}</TableCell>
                      <TableCell>
                        <Chip size="small" color={DEPTH_COLOR[d.depth]} label={d.depth} variant="outlined" />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Section>
          ) : null}

          <Section title={`Project skill requirements (${report.project_requirements.length})`}>
            {report.project_requirements.length ? (
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Project</TableCell>
                    <TableCell>Skill</TableCell>
                    <TableCell>Minimum</TableCell>
                    <TableCell align="right">Verified holders (org-wide)</TableCell>
                    <TableCell align="right">Unverified claims</TableCell>
                    <TableCell>Coverage</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {report.project_requirements.map((r) => (
                    <TableRow key={r.requirement_id}>
                      <TableCell>
                        {r.tool_number}
                        <Typography variant="caption" color="text.secondary" component="div">
                          {r.part_description}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        {r.skill_name}
                        {r.is_mandatory ? '' : ' (optional)'}
                      </TableCell>
                      <TableCell>L{r.min_level}</TableCell>
                      <TableCell align="right">{r.verified_holders}</TableCell>
                      <TableCell align="right">{r.claimed_unverified}</TableCell>
                      <TableCell>{r.status.replace(/_/g, ' ')}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <Typography variant="body2" color="text.secondary">
                No open project records skill requirements yet. Add them from the candidate finder.
              </Typography>
            )}
          </Section>

          <Stack direction={{ xs: 'column', lg: 'row' }} spacing={2}>
            <Box sx={{ flex: 1 }}>
              <Section title={`Training and development (${report.training.length} open)`}>
                {report.training.length ? (
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Employee</TableCell>
                        <TableCell>Skill</TableCell>
                        <TableCell>Target</TableCell>
                        <TableCell>Training / mentor</TableCell>
                        <TableCell>Review</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {report.training.map((t) => (
                        <TableRow key={t.plan_id}>
                          <TableCell>{t.name}</TableCell>
                          <TableCell>{t.skill_name}</TableCell>
                          <TableCell>
                            L{t.baseline_verified_level ?? '–'} → L{t.target_level}
                          </TableCell>
                          <TableCell>
                            {[t.training_requirement, t.mentor_name ? `Mentor: ${t.mentor_name}` : null, t.is_knowledge_transfer ? 'Knowledge transfer' : null]
                              .filter(Boolean)
                              .join(' · ') || '—'}
                          </TableCell>
                          <TableCell sx={{ color: t.overdue ? 'error.main' : undefined }}>
                            {t.target_review_date ? formatDate(t.target_review_date) : '—'}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    No open development plans in scope.
                  </Typography>
                )}
              </Section>
            </Box>
            <Box sx={{ flex: 1 }}>
              <Section title={`Reassessment due (${report.reassessment.length})`}>
                {report.reassessment.length ? (
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Employee</TableCell>
                        <TableCell>Skill</TableCell>
                        <TableCell>Verified</TableCell>
                        <TableCell>Reason</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {report.reassessment.map((r) => (
                        <TableRow key={r.record_id}>
                          <TableCell>{r.name}</TableCell>
                          <TableCell>{r.skill_name}</TableCell>
                          <TableCell>
                            L{r.verified_level} · {r.verified_at ? formatDate(r.verified_at) : '—'}
                          </TableCell>
                          <TableCell>{r.reason}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    Nothing due.
                  </Typography>
                )}
              </Section>
            </Box>
          </Stack>
        </>
      ) : null}
    </Stack>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="subtitle1" gutterBottom>
        {title}
      </Typography>
      {children}
    </Paper>
  );
}
