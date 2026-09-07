import { useEffect, useMemo, useState } from 'react';
import { Box, Tab, Tabs } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { apiClient } from '../api/client';
import { AnnualPlanPanel } from '../components/finance/AnnualPlanPanel';
import { FinanceBudgetsReportsPanel } from '../components/finance/FinanceBudgetsReportsPanel';
import { FinanceExpensesPanel } from '../components/finance/FinanceExpensesPanel';
import { FinanceOverheadsPanel } from '../components/finance/FinanceOverheadsPanel';
import { FinanceOverviewPanel } from '../components/finance/FinanceOverviewPanel';
import { FinancePeopleCostsPanel } from '../components/finance/FinancePeopleCostsPanel';
import { FinanceQuotesPanel } from '../components/finance/FinanceQuotesPanel';
import { FinanceScenariosPanel } from '../components/finance/FinanceScenariosPanel';
import { FinanceTeamCommercialPanel } from '../components/finance/FinanceTeamCommercialPanel';
import { FinanceTreasuryPanel } from '../components/finance/FinanceTreasuryPanel';
import {
  FinanceTeamFilter,
  financeQueryParam,
  readStoredFinanceFyStartYear,
  readStoredFinanceTeamId,
} from '../components/finance/FinanceTeamFilter';
import { PageHeader } from '../components/common/PageHeader';
import { LoadingState } from '../components/common/LoadingState';

type FinanceDashboard = {
  base_currency: string;
};

/** Stable tab keys for deep links (?tab=) and path aliases (/finance/budgets). */
export const FINANCE_TABS = [
  { key: 'overview', label: 'Overview', aliases: ['', 'overview', 'dashboard'] },
  { key: 'people', label: 'People & cost rates', aliases: ['people', 'people-costs', 'costs'] },
  { key: 'expenses', label: 'Expenses', aliases: ['expenses', 'subscriptions'] },
  { key: 'overheads', label: 'Overheads', aliases: ['overheads', 'overhead'] },
  { key: 'scenarios', label: 'Scenario Planning', aliases: ['scenarios', 'scenario', 'planning'] },
  { key: 'commercial', label: 'Teams / commercial', aliases: ['commercial', 'teams'] },
  { key: 'annual-plan', label: 'Forecasting / Annual Plan', aliases: ['annual-plan', 'forecast', 'forecasting', 'plan'] },
  { key: 'quotes', label: 'Projects & revenue', aliases: ['quotes', 'revenue', 'projects', 'invoicing'] },
  { key: 'treasury', label: 'Treasury', aliases: ['treasury', 'loans', 'od', 'investments', 'cash'] },
  { key: 'budgets', label: 'Reports & budgets', aliases: ['budgets', 'reports', 'report'] },
] as const;

function resolveFinanceTabIndex(pathname: string, tabParam: string | null): number {
  const pathTail = pathname.replace(/^\/finance\/?/, '').split('/')[0]?.toLowerCase() || '';
  const candidates = [tabParam?.toLowerCase() || '', pathTail].filter(Boolean);
  for (const candidate of candidates) {
    const idx = FINANCE_TABS.findIndex((tab) =>
      (tab.aliases as readonly string[]).includes(candidate) || tab.key === candidate,
    );
    if (idx >= 0) return idx;
  }
  return 0;
}

export function FinanceDashboardPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTab = useMemo(
    () => resolveFinanceTabIndex(location.pathname, searchParams.get('tab')),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- hydrate once from URL
    [],
  );
  const [tab, setTab] = useState(initialTab);
  const [teamId, setTeamId] = useState(readStoredFinanceTeamId);
  const [fyStartYear, setFyStartYear] = useState<number | null>(readStoredFinanceFyStartYear);

  useEffect(() => {
    const next = resolveFinanceTabIndex(location.pathname, searchParams.get('tab'));
    setTab(next);
  }, [location.pathname, searchParams]);

  const selectTab = (index: number) => {
    setTab(index);
    const key = FINANCE_TABS[index]?.key ?? 'overview';
    const next = new URLSearchParams(searchParams);
    next.set('tab', key);
    setSearchParams(next, { replace: true });
    if (location.pathname !== '/finance' && !location.pathname.startsWith('/finance?')) {
      navigate({ pathname: '/finance', search: `?${next.toString()}` }, { replace: true });
    }
  };

  const dashboardQuery = useQuery({
    queryKey: ['finance-dashboard', teamId || 'all', fyStartYear ?? 'current'],
    queryFn: async () =>
      (
        await apiClient.get<FinanceDashboard>(
          `/finance/dashboard${financeQueryParam(teamId, fyStartYear)}`,
        )
      ).data,
  });

  if (dashboardQuery.isLoading && tab === 0) {
    return <LoadingState message="Loading financial dashboard…" />;
  }

  return (
    <Box>
      <PageHeader
        title="Finance"
        subtitle={`Financial command center (base ${
          dashboardQuery.data?.base_currency ?? 'INR'
        }) — Overview, revenue, invoicing, profitability, forecasting, and scenario planning. Grant Finance access in Admin → Users.`}
      />

      <FinanceTeamFilter
        value={teamId}
        onChange={setTeamId}
        fyStartYear={fyStartYear}
        onFyStartYearChange={setFyStartYear}
      />

      <Tabs
        value={tab}
        onChange={(_, value) => selectTab(value)}
        sx={{
          mb: 2.5,
          minHeight: 44,
          '& .MuiTab-root': { textTransform: 'none', fontWeight: 600, minHeight: 44 },
        }}
        variant="scrollable"
      >
        {FINANCE_TABS.map((item) => (
          <Tab key={item.key} label={item.label} />
        ))}
      </Tabs>

      {tab === 0 && <FinanceOverviewPanel teamId={teamId} fyStartYear={fyStartYear} />}
      {tab === 1 && <FinancePeopleCostsPanel teamId={teamId} />}
      {tab === 2 && <FinanceExpensesPanel teamId={teamId} />}
      {tab === 3 && <FinanceOverheadsPanel teamId={teamId} />}
      {tab === 4 && <FinanceScenariosPanel teamId={teamId} />}
      {tab === 5 && <FinanceTeamCommercialPanel teamId={teamId} />}
      {tab === 6 && <AnnualPlanPanel />}
      {tab === 7 && <FinanceQuotesPanel teamId={teamId} />}
      {tab === 8 && <FinanceTreasuryPanel teamId={teamId} fyStartYear={fyStartYear} />}
      {tab === 9 && <FinanceBudgetsReportsPanel teamId={teamId} fyStartYear={fyStartYear} />}
    </Box>
  );
}

export default FinanceDashboardPage;
