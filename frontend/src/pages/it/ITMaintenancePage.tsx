import { Chip, Stack, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { fetchAssetsPaginated, fetchOpenItRequests, itOperationsKeys } from '../../api/itOperations';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ITAreaTabs } from '../../components/it/ITAreaTabs';
import { IT_ASSET_AREA_TABS } from '../../components/it/itAreaTabConfig';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { ClientPaginatedDataGrid } from '../../components/common/ClientPaginatedDataGrid';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { EmptyState } from '../../components/common/EmptyState';
import type { GridColDef } from '@mui/x-data-grid';
import type { ITAsset, ITOpenRequest } from '../../types/itOperations';
import { formatCellValue } from '../../utils/format';

export function ITMaintenancePage() {
  const navigate = useNavigate();

  const assetsQuery = useQuery({
    queryKey: itOperationsKeys.assets({ status: 'maintenance', page_size: 200 }),
    queryFn: () => fetchAssetsPaginated({ status: 'maintenance', page_size: 200 }),
  });
  const requestsQuery = useQuery({
    queryKey: itOperationsKeys.openRequests(),
    queryFn: fetchOpenItRequests,
  });

  const columns: GridColDef<ITAsset>[] = [
    { field: 'asset_number', headerName: 'Asset #', flex: 0.8, minWidth: 110 },
    { field: 'computer_name', headerName: 'Computer', flex: 0.9, minWidth: 120 },
    {
      field: 'make_model',
      headerName: 'Make / Model',
      flex: 1,
      minWidth: 140,
      valueGetter: (_value, row) => [row.make, row.model].filter(Boolean).join(' ') || '—',
    },
    { field: 'location', headerName: 'Location', flex: 0.8, minWidth: 110 },
    {
      field: 'status',
      headerName: 'Status',
      width: 130,
      renderCell: (params) => <Chip size="small" label={String(params.value || '—')} variant="outlined" />,
    },
  ];

  return (
    <PageContainer>
      <PageHeader
        title="Maintenance"
        subtitle="Assets currently in maintenance. Status is set from the inventory asset; IT requests capture the work ticket."
        action={
          <ProsohmButton buttonVariant="outlined" onClick={() => navigate('/it/assets?status=maintenance')}>
            Open in inventory
          </ProsohmButton>
        }
      />
      <ITAreaTabs items={IT_ASSET_AREA_TABS} />

      <Stack spacing={2.5}>
        <ContentCard title="Assets in maintenance" noPadding>
          {assetsQuery.isLoading ? (
            <LoadingState message="Loading maintenance assets…" />
          ) : assetsQuery.error ? (
            <ErrorState error={assetsQuery.error} onRetry={() => void assetsQuery.refetch()} />
          ) : (assetsQuery.data?.items ?? []).length === 0 ? (
            <EmptyState
              title="No assets in maintenance"
              description="Mark an asset as Maintenance from Assets & Inventory when it is taken offline."
            />
          ) : (
            <ClientPaginatedDataGrid
              rows={assetsQuery.data?.items ?? []}
              columns={columns}
              getRowId={(row) => row.id}
            />
          )}
        </ContentCard>

        <ContentCard title="Open IT requests">
          {requestsQuery.isLoading ? (
            <LoadingState message="Loading requests…" />
          ) : (requestsQuery.data ?? []).length === 0 ? (
            <Typography color="text.secondary">No open IT requests.</Typography>
          ) : (
            <Stack spacing={0.75}>
              {(requestsQuery.data as ITOpenRequest[]).slice(0, 12).map((row) => (
                <Typography key={row.id} variant="body2">
                  {formatCellValue(row.ticket_number)} · {row.title} · {row.status_label || row.status}
                </Typography>
              ))}
              <ProsohmButton buttonVariant="outlined" onClick={() => navigate('/it/requests')}>
                View all requests
              </ProsohmButton>
            </Stack>
          )}
        </ContentCard>
      </Stack>
    </PageContainer>
  );
}
