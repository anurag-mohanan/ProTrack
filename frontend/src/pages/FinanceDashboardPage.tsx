import { useState } from 'react';
import { Box, Tab, Tabs } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../api/client';
import { AnnualPlanPanel } from '../components/finance/AnnualPlanPanel';
import { FinanceBudgetsReportsPanel } from '../components/finance/FinanceBudgetsReportsPanel';
import { FinanceExpensesPanel } from '../components/finance/FinanceExpensesPanel';
import { FinanceOverheadsPanel } from '../components/finance/FinanceOverheadsPanel';
import { FinanceOverviewPanel } from '../components/finance/FinanceOverviewPanel';
import { FinancePeopleCostsPanel } from '../components/finance/FinancePeopleCostsPanel';
import { FinanceQuotesPanel } from '../components/finance/FinanceQuotesPanel';
import { FinanceTeamCommercialPanel } from '../components/finance/FinanceTeamCommercialPanel';
import {
  FinanceTeamFilter,
  readStoredFinanceTeamId,
  teamQueryParam,
} from '../components/finance/FinanceTeamFilter';
import { PageHeader } from '../components/common/PageHeader';
import { LoadingState } from '../components/common/LoadingState';

type FinanceDashboard = {
  base_currency: string;
};

export function FinanceDashboardPage() {
  const [tab, setTab] = useState(0);
  const [teamId, setTeamId] = useState(readStoredFinanceTeamId);

  const dashboardQuery = useQuery({
    queryKey: ['finance-dashboard', teamId || 'all'],
    queryFn: async () =>
      (await apiClient.get<FinanceDashboard>(`/finance/dashboard${teamQueryParam(teamId)}`)).data,
  });

  if (dashboardQuery.isLoading && tab === 0) {
    return <LoadingState message="Loading financial dashboard…" />;
  }

  return (
    <Box>
      <PageHeader
        title="Financial Planning"
        subtitle={`Modern FP&A cockpit (base ${
          dashboardQuery.data?.base_currency ?? 'INR'
        }) — chart-led Overview, Annual Plan AI Assist, Budgets portfolio. Grant Financial Planning in Admin → Users.`}
      />

      <FinanceTeamFilter value={teamId} onChange={setTeamId} />

      <Tabs
        value={tab}
        onChange={(_, value) => setTab(value)}
        sx={{
          mb: 2.5,
          minHeight: 44,
          '& .MuiTab-root': { textTransform: 'none', fontWeight: 600, minHeight: 44 },
        }}
        variant="scrollable"
      >
        <Tab label="Overview" />
        <Tab label="People costs" />
        <Tab label="Expenses & subscriptions" />
        <Tab label="Overheads" />
        <Tab label="Team commercial" />
        <Tab label="Annual Plan" />
        <Tab label="Revenue / quotes" />
        <Tab label="Budgets & reports" />
      </Tabs>

      {tab === 0 && <FinanceOverviewPanel teamId={teamId} />}
      {tab === 1 && <FinancePeopleCostsPanel teamId={teamId} />}
      {tab === 2 && <FinanceExpensesPanel teamId={teamId} />}
      {tab === 3 && <FinanceOverheadsPanel teamId={teamId} />}
      {tab === 4 && <FinanceTeamCommercialPanel teamId={teamId} />}
      {tab === 5 && <AnnualPlanPanel />}
      {tab === 6 && <FinanceQuotesPanel teamId={teamId} />}
      {tab === 7 && <FinanceBudgetsReportsPanel teamId={teamId} />}
    </Box>
  );
}

export default FinanceDashboardPage;
