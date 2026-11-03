import { useState } from 'react';
import { Tab, Tabs, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { fetchCockpit, fetchManagementFilters, managementQueryKeys } from '../api/management';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { PageContainer } from '../components/common/PageContainer';
import { PageHeader } from '../components/common/PageHeader';
import { ActionsTab } from '../components/management/ActionsTab';
import { CockpitTab } from '../components/management/CockpitTab';
import { CustomersTab } from '../components/management/CustomersTab';
import { EfficiencyTab } from '../components/management/EfficiencyTab';
import { FilterBar } from '../components/management/ManagementParts';
import { PRINCIPLE } from '../components/management/managementFormat';
import { ObjectivesTab } from '../components/management/ObjectivesTab';
import { ReviewsTab } from '../components/management/ReviewsTab';
import type { CockpitFilterValues } from '../types/Management';
import { formatDateTime } from '../utils/format';

type ManagementTab = 'cockpit' | 'customers' | 'efficiency' | 'objectives' | 'reviews' | 'actions';
const TABS: ManagementTab[] = ['cockpit', 'customers', 'efficiency', 'objectives', 'reviews', 'actions'];

export default function ManagementPage() {
  const [params, setParams] = useSearchParams();
  const requested = params.get('tab') as ManagementTab | null;
  const tab: ManagementTab = requested && TABS.includes(requested) ? requested : 'cockpit';
  const customerId = params.get('customer');
  const [chosen, setChosen] = useState<CockpitFilterValues | null>(null);

  const options = useQuery({ queryKey: managementQueryKeys.filters, queryFn: fetchManagementFilters });
  const currentFy = options.data?.financial_years.find((y) => y.is_current)?.start_year;
  const selected: CockpitFilterValues = chosen ?? { fy_start_year: currentFy };
  const filters: CockpitFilterValues =
    selected.start_date && selected.end_date ? selected : { ...selected, start_date: undefined, end_date: undefined };
  const fy = filters.fy_start_year ?? currentFy ?? new Date().getFullYear();

  const cockpit = useQuery({
    queryKey: managementQueryKeys.cockpit(filters),
    queryFn: () => fetchCockpit(filters),
    enabled: tab === 'cockpit' && currentFy !== undefined,
  });

  const navigate = (next: ManagementTab, customer?: string | null) => {
    const search = new URLSearchParams(params);
    search.set('tab', next);
    if (customer) search.set('customer', customer);
    else search.delete('customer');
    setParams(search, { replace: next === tab });
  };

  const can = options.data?.can;
  return (
    <PageContainer>
      <PageHeader subtitle="Financial-year business, delivery, workforce and customer performance from the existing Finance, delivery and capacity records, with objectives, reviews and follow-up actions." />
      {options.isLoading ? <LoadingState message="Loading management cockpit…" /> : null}
      {options.error ? <ErrorState error={options.error} onRetry={() => void options.refetch()} /> : null}
      {options.data && can ? (
        <>
          <FilterBar options={options.data} value={selected} onChange={setChosen} />
          <Tabs
            value={tab}
            onChange={(_, value: ManagementTab) => navigate(value)}
            variant="scrollable"
            sx={{ mb: 2, minHeight: 40, borderBottom: 1, borderColor: 'divider' }}
          >
            <Tab value="cockpit" label="Cockpit" sx={{ minHeight: 40 }} />
            <Tab value="customers" label="Customers" sx={{ minHeight: 40 }} />
            <Tab value="efficiency" label="Efficiency" sx={{ minHeight: 40 }} />
            <Tab value="objectives" label="Objectives" sx={{ minHeight: 40 }} />
            <Tab value="reviews" label="Reviews" sx={{ minHeight: 40 }} />
            <Tab value="actions" label="Actions" sx={{ minHeight: 40 }} />
          </Tabs>
          {tab === 'cockpit' ? (
            <>
              {cockpit.isLoading ? <LoadingState message="Calculating…" /> : null}
              {cockpit.error ? <ErrorState error={cockpit.error} onRetry={() => void cockpit.refetch()} /> : null}
              {cockpit.data ? (
                <>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                    Calculated {formatDateTime(cockpit.data.generated_at)} from live records. {PRINCIPLE}
                  </Typography>
                  <CockpitTab data={cockpit.data} filters={filters} onOpenCustomer={(id) => navigate('customers', id)} />
                </>
              ) : null}
            </>
          ) : null}
          {tab === 'customers' ? (
            <CustomersTab filters={filters} can={can} customerId={customerId} onSelect={(id) => navigate('customers', id)} />
          ) : null}
          {tab === 'efficiency' ? <EfficiencyTab filters={filters} can={can} /> : null}
          {tab === 'objectives' ? <ObjectivesTab filters={filters} can={can} fy={fy} /> : null}
          {tab === 'reviews' ? <ReviewsTab filters={filters} can={can} fy={fy} /> : null}
          {tab === 'actions' ? <ActionsTab filters={filters} can={can} /> : null}
        </>
      ) : null}
    </PageContainer>
  );
}
