import { Button, Stack, Tab, Tabs, Typography } from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { fetchPredictionOverview, predictiveQueryKeys, runPredictions } from '../api/predictive';
import { getErrorMessage } from '../api/client';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { PageContainer } from '../components/common/PageContainer';
import { PageHeader } from '../components/common/PageHeader';
import { AccuracyTab } from '../components/predictive/AccuracyTab';
import { FreshnessBanner } from '../components/predictive/PredictionParts';
import { PortfolioTab } from '../components/predictive/PortfolioTab';
import { ProjectForecastTab } from '../components/predictive/ProjectForecastTab';
import { ResourceDemandTab } from '../components/predictive/ResourceDemandTab';
import { ScenariosTab } from '../components/predictive/ScenariosTab';
import { useToast } from '../context/ToastContext';
import { formatDateTime } from '../utils/format';

type PredictiveTab = 'portfolio' | 'project' | 'resources' | 'accuracy' | 'scenarios';
const TABS: PredictiveTab[] = ['portfolio', 'project', 'resources', 'accuracy', 'scenarios'];

export default function PredictivePage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const requested = params.get('tab') as PredictiveTab | null;
  const tab: PredictiveTab = requested && TABS.includes(requested) ? requested : 'portfolio';
  const projectId = params.get('project');

  const overview = useQuery({ queryKey: predictiveQueryKeys.overview, queryFn: fetchPredictionOverview });
  const run = useMutation({
    mutationFn: runPredictions,
    onSuccess: (result) => {
      toast.showSuccess(
        result.status === 'succeeded'
          ? 'Predictions refreshed. No project, timesheet or Finance record was changed.'
          : `Prediction run ${result.status}.`,
      );
      void queryClient.invalidateQueries({ queryKey: predictiveQueryKeys.all });
    },
    onError: (error) => toast.showError(getErrorMessage(error)),
  });

  const navigate = (next: PredictiveTab, project?: string | null) => {
    const search = new URLSearchParams(params);
    search.set('tab', next);
    if (project !== undefined) {
      if (project) search.set('project', project);
      else search.delete('project');
    }
    setParams(search, { replace: next === tab });
  };

  const data = overview.data;
  const lastRun = data?.latest_run;

  return (
    <PageContainer>
      <PageHeader
        subtitle="Forecast completion dates, final hours, milestones, workload and billing from comparable completed work. Forecasts are estimates with stated uncertainty; they never change project, resource or Finance records."
        action={
          data?.can.run ? (
            <Stack spacing={0.5} sx={{ alignItems: { sm: 'flex-end' } }}>
              <Button variant="contained" onClick={() => run.mutate()} disabled={run.isPending}>
                {run.isPending ? 'Running…' : 'Refresh predictions'}
              </Button>
              {lastRun ? (
                <Typography variant="caption" color="text.secondary">
                  Last run {lastRun.status}
                  {lastRun.finished_at ? ` ${formatDateTime(lastRun.finished_at)}` : ''} ({lastRun.trigger})
                </Typography>
              ) : null}
            </Stack>
          ) : null
        }
      />
      {overview.isLoading ? <LoadingState message="Loading forecasts…" /> : null}
      {overview.error ? <ErrorState error={overview.error} onRetry={() => void overview.refetch()} /> : null}
      {data ? (
        <>
          <FreshnessBanner freshness={data.freshness} />
          <Tabs
            value={tab}
            onChange={(_, value: PredictiveTab) => navigate(value)}
            variant="scrollable"
            sx={{ mb: 2, minHeight: 40, borderBottom: 1, borderColor: 'divider' }}
          >
            <Tab value="portfolio" label="Portfolio" sx={{ minHeight: 40 }} />
            <Tab value="project" label="Project" sx={{ minHeight: 40 }} />
            <Tab value="resources" label="Resource demand" sx={{ minHeight: 40 }} />
            <Tab value="accuracy" label="Accuracy" sx={{ minHeight: 40 }} />
            <Tab value="scenarios" label="Scenarios" sx={{ minHeight: 40 }} />
          </Tabs>
          {tab === 'portfolio' ? (
            <PortfolioTab
              overview={data}
              onOpenProject={(id) => navigate('project', id)}
              onOpenResources={() => navigate('resources')}
            />
          ) : null}
          {tab === 'project' ? (
            <ProjectForecastTab
              projectId={projectId}
              onSelectProject={(id) => navigate('project', id)}
              onOpenScenarios={() => navigate('scenarios')}
            />
          ) : null}
          {tab === 'resources' ? <ResourceDemandTab canView={data.can.capacity} /> : null}
          {tab === 'accuracy' ? <AccuracyTab /> : null}
          {tab === 'scenarios' ? (
            <ScenariosTab projectId={projectId} onSelectProject={(id) => navigate('scenarios', id)} canCapacity={data.can.capacity} />
          ) : null}
        </>
      ) : null}
    </PageContainer>
  );
}
