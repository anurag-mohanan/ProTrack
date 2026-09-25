import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { Box } from '@mui/material';
import { fetchInventoryOverview, itInventoryKeys } from '../../api/itInventory';
import { useAuth } from '../../context/AuthContext';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingState } from '../../components/common/LoadingState';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ITAreaTabs } from '../../components/it/ITAreaTabs';
import { IT_ASSET_AREA_TABS } from '../../components/it/itAreaTabConfig';
import { ComputerAvailabilityView } from '../../components/it/inventory/ComputerAvailabilityView';
import { InventoryOverviewPanel } from '../../components/it/inventory/InventoryOverviewPanel';
import { RestockView } from '../../components/it/inventory/RestockView';
import { StockItemsView } from '../../components/it/inventory/StockItemsView';
import { StockMovementsView } from '../../components/it/inventory/StockMovementsView';
import { accessContextFromUser, canAssignItAssets, canManageItAssets } from '../../utils/permissions';

const VIEW_TITLES: Record<string, { title: string; subtitle: string }> = {
  '': {
    title: 'Inventory',
    subtitle: 'Serialized assets and quantity-tracked consumable stock',
  },
  'low-stock': {
    title: 'Low stock',
    subtitle: 'Items below minimum stock or needing reorder',
  },
  movements: { title: 'Stock movements', subtitle: 'Every receipt, issue, return, adjustment and transfer' },
  restock: { title: 'Restock & reservations', subtitle: 'Purchase requests, incoming stock and reserved units' },
  availability: {
    title: 'Computer availability',
    subtitle: 'Which computer can be assigned for which shift (same rule as assignment validation)',
  },
};

function OverviewAndStock({ canManage, canAssign }: { canManage: boolean; canAssign: boolean }) {
  const overviewQuery = useQuery({ queryKey: itInventoryKeys.overview(), queryFn: fetchInventoryOverview });
  return (
    <>
      {overviewQuery.isLoading ? <LoadingState message="Loading inventory overview…" /> : null}
      {overviewQuery.isError ? (
        <ErrorState
          error={overviewQuery.error}
          title="Unable to load inventory overview"
          onRetry={() => void overviewQuery.refetch()}
        />
      ) : null}
      {overviewQuery.data ? <InventoryOverviewPanel data={overviewQuery.data} /> : null}
      <Box sx={{ mt: 3 }}>
        <StockItemsView canManage={canManage} canAssign={canAssign} />
      </Box>
    </>
  );
}

export function ITInventoryPage() {
  const { user } = useAuth();
  const access = accessContextFromUser(user);
  const canManage = canManageItAssets(access);
  const canAssign = canAssignItAssets(access) || canManage;
  const [searchParams] = useSearchParams();
  const view = searchParams.get('view') ?? '';
  const heading = VIEW_TITLES[view] ?? VIEW_TITLES[''];

  return (
    <PageContainer>
      <PageHeader title={heading.title} subtitle={heading.subtitle} />
      <ITAreaTabs items={IT_ASSET_AREA_TABS} />
      {view === 'low-stock' ? <StockItemsView lowStockOnly canManage={canManage} canAssign={canAssign} /> : null}
      {view === 'movements' ? <StockMovementsView /> : null}
      {view === 'restock' ? <RestockView canManage={canManage} canAssign={canAssign} /> : null}
      {view === 'availability' ? <ComputerAvailabilityView /> : null}
      {!VIEW_TITLES[view] || view === '' ? <OverviewAndStock canManage={canManage} canAssign={canAssign} /> : null}
    </PageContainer>
  );
}
