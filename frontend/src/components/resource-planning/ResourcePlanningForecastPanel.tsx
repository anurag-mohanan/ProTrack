import { useMemo, useState } from 'react';
import { Alert, Stack, TextField, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { fetchHireImpact } from '../../api/resourcePlanning';
import { QUERY_STALE_TIMES } from '../../config/queryConfig';
import { DashboardPanel } from '../ui/design-system';
import { LoadingState } from '../common/LoadingState';
import { ErrorState } from '../common/ErrorState';
import { formatCellValue } from '../../utils/format';

type Props = {
  teamId?: string;
  avgCapacityHours: number;
  totalCapacity: number;
  totalPlanned: number;
  liveUtil: number;
};

export function ResourcePlanningForecastPanel({
  teamId,
  avgCapacityHours,
  totalCapacity,
  totalPlanned,
  liveUtil,
}: Props) {
  const [extraDesigners, setExtraDesigners] = useState(0);
  const [hoursDelta, setHoursDelta] = useState(0);
  const [hireHeadcount, setHireHeadcount] = useState(1);

  const scenarioCapacity = totalCapacity + extraDesigners * avgCapacityHours + hoursDelta;
  const scenarioUtil =
    scenarioCapacity > 0 ? Math.round((totalPlanned / scenarioCapacity) * 100) : liveUtil;
  const active = extraDesigners !== 0 || hoursDelta !== 0;

  const hireQuery = useQuery({
    queryKey: ['finance', 'hire-impact', hireHeadcount, teamId ?? null],
    queryFn: () => fetchHireImpact({ headcount: hireHeadcount, team_id: teamId }),
    staleTime: QUERY_STALE_TIMES.dashboard,
    enabled: hireHeadcount > 0,
  });

  const hire = hireQuery.data;
  const licenseCost = useMemo(() => {
    if (!hire) return null;
    return hire.estimated_license_cost ?? hire.estimated_monthly_license_cost;
  }, [hire]);

  return (
    <Stack spacing={2.5}>
      <DashboardPanel
        title="Capacity what-if"
        subtitle="Scenario overlay on live capacity — does not change assignments"
      >
        <Alert severity={active ? 'info' : 'success'} sx={{ mb: 2 }}>
          Scenario util {scenarioUtil}%
          {active ? ` (live ${liveUtil}%)` : ' — adjust designers or hours to model a change'}
        </Alert>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
          <TextField
            size="small"
            type="number"
            label="+/− designers"
            value={extraDesigners}
            onChange={(event) => setExtraDesigners(Number(event.target.value) || 0)}
            slotProps={{ htmlInput: { step: 1 } }}
          />
          <TextField
            size="small"
            type="number"
            label="+/− capacity hours"
            value={hoursDelta}
            onChange={(event) => setHoursDelta(Number(event.target.value) || 0)}
            slotProps={{ htmlInput: { step: 1 } }}
          />
        </Stack>
      </DashboardPanel>

      <DashboardPanel
        title="Hire impact forecast"
        subtitle="Computers and license seats needed for planned hires (Finance hire-impact)"
      >
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ mb: 2 }}>
          <TextField
            size="small"
            type="number"
            label="Hire headcount"
            value={hireHeadcount}
            onChange={(event) => setHireHeadcount(Math.max(0, Number(event.target.value) || 0))}
            slotProps={{ htmlInput: { min: 0, step: 1 } }}
          />
        </Stack>
        {hireQuery.isLoading ? (
          <LoadingState message="Estimating hire impact…" />
        ) : hireQuery.error ? (
          <ErrorState error={hireQuery.error} />
        ) : hire ? (
          <Stack spacing={1}>
            <Typography variant="body2">
              Computers to procure: <strong>{hire.computers_to_procure}</strong> (need{' '}
              {hire.required_computers}, spare {hire.spare_computers})
            </Typography>
            <Typography variant="body2">
              License seats required: <strong>{hire.required_license_seats}</strong>
              {licenseCost != null ? ` · est. cost ${formatCellValue(licenseCost)}` : ''}
            </Typography>
            {(hire.warnings ?? []).slice(0, 3).map((warning) => (
              <Alert key={warning} severity="warning">
                {warning}
              </Alert>
            ))}
            {(hire.assumptions ?? []).slice(0, 2).map((row) => (
              <Typography key={row} variant="caption" color="text.secondary">
                {row}
              </Typography>
            ))}
          </Stack>
        ) : null}
      </DashboardPanel>
    </Stack>
  );
}
