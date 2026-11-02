import { useState, type ReactNode } from 'react';
import {
  Alert,
  Box,
  Chip,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { fetchPredictions, predictiveQueryKeys } from '../../api/predictive';
import type { Prediction } from '../../types/Predictive';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { KpiCard, SectionTitle } from '../reports/ReportKpi';
import { InsufficientList } from './PredictionParts';
import { dataFlag, dataString, hoursText, shareText } from './predictiveFormat';

const WEEKS = [2, 4, 8, 12] as const;

function utilisation(r: Prediction): number {
  return Number(dataString(r.data_used, 'utilisation_percent') ?? 0);
}

function UtilisationCell({ row }: { row: Prediction }) {
  const pct = dataString(row.data_used, 'utilisation_percent');
  const shortage = dataFlag(row.data_used, 'shortage');
  return (
    <TableCell align="right">
      <Typography variant="body2" sx={{ fontWeight: shortage ? 700 : 400, color: shortage ? 'error.main' : undefined }}>
        {pct ? `${pct}%` : '—'}
      </Typography>
    </TableCell>
  );
}

function Flags({ children }: { children: ReactNode }) {
  return (
    <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap', gap: 0.5 }}>
      {children}
    </Stack>
  );
}

function ProjectsTooltip({ row }: { row: Prediction }) {
  const projects = (row.data_used.projects as Array<{ label: string; hours_in_window: string }> | undefined) ?? [];
  const hidden = Number(row.data_used.projects_not_visible_to_you ?? 0);
  if (!projects.length && !hidden) return <>{row.subject_label}</>;
  const title = [
    ...projects.map((p) => `${p.label}: ${hoursText(p.hours_in_window)}`),
    ...(hidden ? [`${hidden} project(s) outside your access`] : []),
  ].join('\n');
  return (
    <Tooltip title={<span style={{ whiteSpace: 'pre-line' }}>{title}</span>}>
      <span style={{ textDecoration: 'underline dotted' }}>{row.subject_label}</span>
    </Tooltip>
  );
}

function DemandTable({ title, subtitle, rows, kind }: { title: string; subtitle: string; rows: Prediction[]; kind: 'person' | 'team' | 'skill' }) {
  if (!rows.length) return null;
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <SectionTitle title={title} subtitle={subtitle} />
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>{kind === 'person' ? 'Designer' : kind === 'team' ? 'Team' : 'Skill'}</TableCell>
              <TableCell align="right">Forecast demand</TableCell>
              <TableCell align="right">{kind === 'skill' ? 'Verified holder capacity' : 'Capacity'}</TableCell>
              <TableCell align="right">Utilisation</TableCell>
              <TableCell>Signals</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {[...rows].sort((a, b) => utilisation(b) - utilisation(a)).map((r) => {
              const overloaded = (r.data_used.overloaded_weeks as string[] | undefined) ?? [];
              return (
                <TableRow key={r.id}>
                  <TableCell>{kind === 'person' ? <ProjectsTooltip row={r} /> : r.subject_label}</TableCell>
                  <TableCell align="right">{hoursText(r.predicted_value)}</TableCell>
                  <TableCell align="right">{hoursText(r.baseline_value)}</TableCell>
                  <UtilisationCell row={r} />
                  <TableCell>
                    <Flags>
                      {dataFlag(r.data_used, 'shortage') ? <Chip size="small" color="error" variant="outlined" label="Shortage" /> : null}
                      {overloaded.length ? (
                        <Tooltip title={`Weeks starting ${overloaded.join(', ')}`}>
                          <Chip size="small" color="warning" variant="outlined" label={`${overloaded.length} overloaded week(s)`} />
                        </Tooltip>
                      ) : null}
                      {dataFlag(r.data_used, 'single_person_dependency') ? (
                        <Chip
                          size="small"
                          color="warning"
                          variant="outlined"
                          label={
                            kind === 'skill'
                              ? 'Single verified holder'
                              : `One person carries ${shareText(dataString(r.data_used, 'largest_individual_share'))}`
                          }
                        />
                      ) : null}
                      {dataFlag(r.data_used, 'underutilized') ? <Chip size="small" variant="outlined" label="Under-utilised" /> : null}
                      {r.data_used.demand_complete === false ? (
                        <Tooltip title="Some open projects have no approved estimate or forecast, so demand is understated.">
                          <Chip size="small" variant="outlined" label="Demand incomplete" />
                        </Tooltip>
                      ) : null}
                    </Flags>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
}

export function ResourceDemandTab({ canView }: { canView: boolean }) {
  const [weeks, setWeeks] = useState<number>(4);
  const query = useQuery({
    queryKey: predictiveQueryKeys.list('resource_demand', weeks),
    queryFn: () => fetchPredictions({ prediction_type: 'resource_demand', weeks }),
    enabled: canView,
    placeholderData: keepPreviousData,
  });
  if (!canView) {
    return <Alert severity="info">Workload and capacity forecasts require Resource Planning access.</Alert>;
  }
  const rows = query.data?.predictions ?? [];
  const predicted = rows.filter((r) => r.status === 'predicted');
  const of = (type: string) => predicted.filter((r) => r.subject_type === type);
  const teams = of('team');
  const people = of('person');
  const skills = of('skill');
  const demand = teams.reduce((sum, r) => sum + Number(r.predicted_value ?? 0), 0);
  const capacity = teams.reduce((sum, r) => sum + Number(r.baseline_value ?? 0), 0);
  return (
    <Box>
      <Stack direction="row" spacing={1.5} sx={{ mb: 2, alignItems: 'center' }}>
        <Typography variant="body2" color="text.secondary">
          Horizon
        </Typography>
        <ToggleButtonGroup size="small" exclusive value={weeks} onChange={(_, next: number | null) => next && setWeeks(next)}>
          {WEEKS.map((w) => (
            <ToggleButton key={w} value={w}>
              {w} weeks
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      </Stack>
      {query.isLoading ? <LoadingState message="Loading workload forecast…" /> : null}
      {query.error ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : null}
      {query.data ? (
        <Stack spacing={2}>
          <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' } }}>
            <KpiCard label="Forecast project demand" value={hoursText(demand)} caption={`Teams in scope, next ${weeks} weeks`} />
            <KpiCard label="Allocatable capacity" value={hoursText(capacity)} caption="After historical non-project time" />
            <KpiCard
              label="People over capacity"
              value={String(people.filter((r) => dataFlag(r.data_used, 'shortage')).length)}
              caption={`of ${people.length} forecast`}
            />
            <KpiCard
              label="Skill bottlenecks"
              value={String(skills.filter((r) => dataFlag(r.data_used, 'shortage') || dataFlag(r.data_used, 'single_person_dependency')).length)}
              caption={`of ${skills.length} required skills`}
            />
          </Box>
          <DemandTable title="Teams" subtitle="Forecast project demand against allocatable capacity." rows={teams} kind="team" />
          <DemandTable
            title="Designers"
            subtitle="Overloaded weeks are where overlapping projects need more hours than the designer has. Hover a name for the projects."
            rows={people}
            kind="person"
          />
          <DemandTable
            title="Required skills"
            subtitle="Demand on projects that require the skill against the capacity of verified holders."
            rows={skills}
            kind="skill"
          />
          {!predicted.length ? (
            <Typography variant="body2" color="text.secondary">
              No workload could be forecast for this horizon.
            </Typography>
          ) : null}
          <InsufficientList rows={rows.filter((r) => r.status !== 'predicted')} title="Not forecast" />
        </Stack>
      ) : null}
    </Box>
  );
}
