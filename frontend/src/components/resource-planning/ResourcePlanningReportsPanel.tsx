import { Alert, Stack, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import {
  fetchResourceItGaps,
  fetchResourceDataQuality,
  resourcePlanningQueryKeys,
} from '../../api/resourcePlanning';
import { QUERY_STALE_TIMES } from '../../config/queryConfig';
import { DashboardPanel } from '../ui/design-system';
import { LoadingState } from '../common/LoadingState';
import { ErrorState } from '../common/ErrorState';

type Props = {
  teamId?: string;
};

export function ResourcePlanningReportsPanel({ teamId }: Props) {
  const gapsQuery = useQuery({
    queryKey: resourcePlanningQueryKeys.itGaps({ team_id: teamId }),
    queryFn: () => fetchResourceItGaps({ team_id: teamId }),
    staleTime: QUERY_STALE_TIMES.dashboard,
  });

  const qualityQuery = useQuery({
    queryKey: resourcePlanningQueryKeys.dataQuality(),
    queryFn: () => fetchResourceDataQuality(),
    staleTime: QUERY_STALE_TIMES.dashboard,
  });

  const gaps = gapsQuery.data;
  const quality = qualityQuery.data;

  return (
    <Stack spacing={2.5}>
      <DashboardPanel title="IT readiness report" subtitle="Workforce gaps vs computers and licenses">
        {gapsQuery.isLoading ? (
          <LoadingState message="Loading readiness…" />
        ) : gapsQuery.error ? (
          <ErrorState error={gapsQuery.error} />
        ) : gaps ? (
          <Stack spacing={1}>
            <Typography variant="body2">
              People without computer: <strong>{gaps.users_without_computer.length}</strong>
            </Typography>
            <Typography variant="body2">
              People missing licenses: <strong>{gaps.users_missing_licenses.length}</strong>
            </Typography>
            <Typography variant="body2">
              Oversubscribed software: <strong>{gaps.oversubscribed_software.length}</strong>
            </Typography>
            <Typography variant="body2">
              Spare computers: <strong>{gaps.spare_computers}</strong>
            </Typography>
            {(gaps.alerts ?? []).slice(0, 4).map((alert) => (
              <Alert
                key={alert.code}
                severity={
                  alert.severity === 'error'
                    ? 'error'
                    : alert.severity === 'warning'
                      ? 'warning'
                      : 'info'
                }
              >
                {alert.message}
              </Alert>
            ))}
          </Stack>
        ) : null}
      </DashboardPanel>

      <DashboardPanel title="Data quality summary" subtitle="Open IT / RP integrity issues">
        {qualityQuery.isLoading ? (
          <LoadingState message="Loading data quality…" />
        ) : qualityQuery.error ? (
          <ErrorState error={qualityQuery.error} />
        ) : quality ? (
          <Stack spacing={1}>
            <Typography variant="body2">
              Issue types with findings:{' '}
              <strong>{quality.open_issues?.length ?? quality.issues?.length ?? 0}</strong>
              {' · '}
              errors {quality.totals?.error ?? 0}, warnings {quality.totals?.warning ?? 0}
            </Typography>
            {(quality.open_issues ?? quality.issues ?? [])
              .filter((issue) => (issue.count ?? 0) > 0)
              .slice(0, 8)
              .map((issue) => (
                <Alert
                  key={issue.code}
                  severity={
                    issue.severity === 'error'
                      ? 'error'
                      : issue.severity === 'warning'
                        ? 'warning'
                        : 'info'
                  }
                >
                  {issue.title}: {issue.count}
                </Alert>
              ))}
          </Stack>
        ) : null}
      </DashboardPanel>
    </Stack>
  );
}
