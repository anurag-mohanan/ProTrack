import { useMemo, useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Chip,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import DevicesOtherRoundedIcon from '@mui/icons-material/DevicesOtherRounded';
import ScheduleRoundedIcon from '@mui/icons-material/ScheduleRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import { useQuery } from '@tanstack/react-query';
import {
  fetchShiftHierarchy,
  resourcePlanningQueryKeys,
  type ShiftHierarchyPerson,
} from '../../api/resourcePlanning';
import { QUERY_STALE_TIMES } from '../../config/queryConfig';
import { LoadingState } from '../common/LoadingState';
import { ErrorState } from '../common/ErrorState';
import { DashboardPanel, KpiMetricCard } from '../ui/design-system';
import { KpiStrip } from '../analytics/KpiStrip';

type Props = {
  teamId?: string;
};

function matchesSearch(person: ShiftHierarchyPerson, query: string): boolean {
  if (!query) return true;
  const haystack = [
    person.name,
    person.team_name,
    person.computer?.computer_name,
    person.computer?.asset_number,
    ...(person.ips ?? []).map((ip) => ip.address),
    ...(person.software ?? []),
    ...(person.projects ?? []).map((row) => row.tool_number || row.name || ''),
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  return haystack.includes(query);
}

function PersonNode({ person }: { person: ShiftHierarchyPerson }) {
  return (
    <Stack spacing={0.5} sx={{ pl: 1, py: 0.75, borderBottom: 1, borderColor: 'divider' }}>
      <Stack direction="row" spacing={0.75} sx={{ flexWrap: 'wrap', alignItems: 'center' }}>
        <Typography sx={{ fontWeight: 600 }}>{person.name}</Typography>
        {person.has_shortage ? (
          <Chip size="small" color="warning" label="Shortage" />
        ) : (
          <Chip size="small" color="success" variant="outlined" label="Ready" />
        )}
      </Stack>
      <Typography variant="body2" color="text.secondary">
        Computer:{' '}
        {person.computer
          ? `${person.computer.computer_name || 'Workstation'}${
              person.computer.asset_number ? ` · ${person.computer.asset_number}` : ''
            }`
          : 'None'}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        IP: {(person.ips ?? []).map((ip) => ip.address).join(', ') || 'None'}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        Licensed: {(person.software ?? []).join(', ') || 'None'}
        {(person.installed ?? []).length
          ? ` · Installed: ${person.installed.join(', ')}`
          : ''}
      </Typography>
      {(person.missing_software ?? []).length ? (
        <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap' }}>
          {person.missing_software.map((name) => (
            <Chip key={name} size="small" color="warning" label={`Missing: ${name}`} />
          ))}
        </Stack>
      ) : null}
      <Typography variant="body2" color="text.secondary">
        Projects:{' '}
        {(person.projects ?? [])
          .map((row) => row.tool_number || row.name)
          .filter(Boolean)
          .join(', ') || 'None'}
      </Typography>
    </Stack>
  );
}

export function ResourcePlanningShiftHierarchyPanel({ teamId }: Props) {
  const [onDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [search, setSearch] = useState('');
  const queryText = search.trim().toLowerCase();

  const query = useQuery({
    queryKey: resourcePlanningQueryKeys.shiftHierarchy({ team_id: teamId, on_date: onDate }),
    queryFn: () => fetchShiftHierarchy({ team_id: teamId, on_date: onDate }),
    staleTime: QUERY_STALE_TIMES.dashboard,
  });

  const report = query.data;
  const filteredShifts = useMemo(() => {
    if (!report) return [];
    return report.shifts.map((shift) => ({
      ...shift,
      teams: shift.teams
        .map((team) => ({
          ...team,
          people: team.people.filter((person) => matchesSearch(person, queryText)),
        }))
        .filter((team) => team.people.length > 0),
    }));
  }, [report, queryText]);

  const filteredUnassigned = useMemo(
    () => (report?.unassigned.people ?? []).filter((person) => matchesSearch(person, queryText)),
    [report, queryText],
  );

  if (query.isLoading) return <LoadingState message="Loading shift hierarchy…" />;
  if (query.error) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  if (!report) return null;

  return (
    <DashboardPanel
      title="Shift hierarchy"
      subtitle={`SHIFT → TEAM → EMPLOYEE → computer / IP / software / project · ${report.on_date}`}
    >
      <KpiStrip columns={4}>
        <KpiMetricCard compact title="Employees" value={String(report.totals.employees)} icon={GroupsRoundedIcon} />
        <KpiMetricCard
          compact
          title="With computer"
          value={String(report.totals.with_computer)}
          accent="success"
          icon={DevicesOtherRoundedIcon}
        />
        <KpiMetricCard
          compact
          title="Unassigned shift"
          value={String(report.totals.unassigned_shift)}
          accent={report.totals.unassigned_shift > 0 ? 'warning' : 'success'}
          icon={ScheduleRoundedIcon}
        />
        <KpiMetricCard
          compact
          title="Shortages"
          value={String(report.totals.with_shortage)}
          accent={report.totals.with_shortage > 0 ? 'warning' : 'success'}
          icon={WarningAmberRoundedIcon}
        />
      </KpiStrip>

      <TextField
        size="small"
        fullWidth
        sx={{ mt: 2, mb: 1.5 }}
        label="Search people, computers, IP, software"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
      />

      <Accordion
        defaultExpanded
        disableGutters
        elevation={0}
        sx={{ border: 1, borderColor: 'divider', borderRadius: 1, mb: 1, '&:before': { display: 'none' } }}
      >
        <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
            <Typography sx={{ fontWeight: 700 }}>Unassigned</Typography>
            <Chip size="small" label={`${filteredUnassigned.length} people`} />
            {report.unassigned.shortage_count > 0 ? (
              <Chip size="small" color="warning" label={`${report.unassigned.shortage_count} shortage`} />
            ) : null}
          </Stack>
        </AccordionSummary>
        <AccordionDetails>
          {filteredUnassigned.length ? (
            filteredUnassigned.map((person) => <PersonNode key={person.user_id} person={person} />)
          ) : (
            <Typography variant="body2" color="text.secondary">
              No unassigned employees{queryText ? ' match this search' : ''}.
            </Typography>
          )}
        </AccordionDetails>
      </Accordion>

      {filteredShifts.map((shift) => (
        <Accordion
          key={shift.id}
          defaultExpanded={shift.people_count > 0}
          disableGutters
          elevation={0}
          sx={{ border: 1, borderColor: 'divider', borderRadius: 1, mb: 1, '&:before': { display: 'none' } }}
        >
          <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
              <Typography sx={{ fontWeight: 700 }}>
                {shift.name}
                {shift.code ? ` (${shift.code})` : ''}
              </Typography>
              <Chip size="small" label={`${shift.people_count} people`} />
              {shift.shortage_count > 0 ? (
                <Chip size="small" color="warning" label={`${shift.shortage_count} shortage`} />
              ) : null}
            </Stack>
          </AccordionSummary>
          <AccordionDetails>
            {shift.teams.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No people on this shift{queryText ? ' match this search' : ''}.
              </Typography>
            ) : (
              shift.teams.map((team) => (
                <Accordion
                  key={`${shift.id}-${team.id}`}
                  defaultExpanded
                  disableGutters
                  elevation={0}
                  sx={{ mb: 1, '&:before': { display: 'none' } }}
                >
                  <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
                    <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                      <Typography sx={{ fontWeight: 600 }}>{team.name}</Typography>
                      <Chip size="small" variant="outlined" label={`${team.people.length}`} />
                    </Stack>
                  </AccordionSummary>
                  <AccordionDetails sx={{ pt: 0 }}>
                    {team.people.map((person) => (
                      <PersonNode key={person.user_id} person={person} />
                    ))}
                  </AccordionDetails>
                </Accordion>
              ))
            )}
          </AccordionDetails>
        </Accordion>
      ))}
    </DashboardPanel>
  );
}
