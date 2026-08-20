import { useMemo, useState } from 'react';
import { Chip } from '@mui/material';
import type { GridColDef } from '@mui/x-data-grid';
import { useQuery } from '@tanstack/react-query';
import { fetchCustomerReturns, itOperationsKeys } from '../../api/itOperations';
import { fetchCustomers } from '../../api/lookups';
import { ClientPaginatedDataGrid } from '../../components/common/ClientPaginatedDataGrid';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingState } from '../../components/common/LoadingState';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ContentCard } from '../../components/ui/cards';
import { FormSelect, SearchToolbar } from '../../components/ui/design-system';
import type { AssetCustomerReturn } from '../../types/itOperations';
import { formatCellValue, formatDate } from '../../utils/format';

export function ITReturnedAssetsPage() {
  const [customerFilter, setCustomerFilter] = useState('');

  const customersQuery = useQuery({
    queryKey: ['lookups', 'customers'],
    queryFn: fetchCustomers,
  });

  const filters = useMemo(
    () => ({
      owner_customer_id: customerFilter || undefined,
    }),
    [customerFilter],
  );

  const returnsQuery = useQuery({
    queryKey: itOperationsKeys.customerReturns(filters),
    queryFn: () => fetchCustomerReturns(filters),
  });

  const customerOptions = useMemo(
    () => [
      { value: '', label: 'All customers' },
      ...(customersQuery.data ?? []).map((customer) => ({
        value: customer.id,
        label: customer.name,
      })),
    ],
    [customersQuery.data],
  );

  const columns: GridColDef<AssetCustomerReturn>[] = [
    {
      field: 'return_date',
      headerName: 'Return date',
      width: 120,
      valueFormatter: (value) => formatDate(value as string | null | undefined) || '—',
    },
    {
      field: 'asset_number',
      headerName: 'Asset #',
      width: 120,
      valueFormatter: (value) => formatCellValue(value),
    },
    {
      field: 'asset_type_name',
      headerName: 'Type',
      flex: 0.8,
      minWidth: 110,
      valueFormatter: (value) => formatCellValue(value),
    },
    {
      field: 'description',
      headerName: 'Description',
      flex: 1.1,
      minWidth: 140,
      valueFormatter: (value) => formatCellValue(value),
    },
    {
      field: 'serial_number',
      headerName: 'Serial',
      width: 130,
      valueFormatter: (value) => formatCellValue(value),
    },
    {
      field: 'owner_customer_name',
      headerName: 'Customer',
      flex: 1,
      minWidth: 140,
      valueFormatter: (value) => formatCellValue(value),
    },
    {
      field: 'original_assignee_name',
      headerName: 'Was assigned to',
      flex: 1,
      minWidth: 140,
      valueFormatter: (value) => formatCellValue(value),
    },
    {
      field: 'condition_at_return',
      headerName: 'Condition',
      width: 120,
      renderCell: (params) => (
        <Chip
          size="small"
          variant="outlined"
          label={String(params.value || '—').replace(/_/g, ' ')}
        />
      ),
    },
    {
      field: 'returned_by_user_name',
      headerName: 'Returned by',
      flex: 0.9,
      minWidth: 120,
      valueFormatter: (value) => formatCellValue(value),
    },
    {
      field: 'received_by_name',
      headerName: 'Received by',
      flex: 0.9,
      minWidth: 120,
      valueFormatter: (value) => formatCellValue(value),
    },
    {
      field: 'return_reason',
      headerName: 'Reason',
      width: 140,
      valueFormatter: (value) =>
        value ? String(value).replace(/_/g, ' ') : '—',
    },
    {
      field: 'notes',
      headerName: 'Notes',
      flex: 1,
      minWidth: 140,
      valueFormatter: (value) => formatCellValue(value),
    },
  ];

  if (returnsQuery.isLoading) {
    return <LoadingState message="Loading returned assets…" />;
  }

  if (returnsQuery.isError) {
    return (
      <ErrorState
        error={returnsQuery.error}
        title="Unable to load returned assets"
        onRetry={() => void returnsQuery.refetch()}
      />
    );
  }

  const rows = returnsQuery.data ?? [];

  return (
    <PageContainer>
      <PageHeader
        title="Returned Assets"
        subtitle="Customer-owned assets returned from Prosohm custody. Records are kept permanently and excluded from current inventory."
      />

      <SearchToolbar sticky>
        <FormSelect
          label="Customer"
          value={customerFilter}
          onChange={(event) => setCustomerFilter(String(event.target.value))}
          options={customerOptions}
          sx={{ minWidth: 240 }}
        />
      </SearchToolbar>

      <ContentCard noPadding>
        <ClientPaginatedDataGrid
          rows={rows}
          columns={columns}
          getRowId={(row) => row.id}
          autoHeight
          filterKey={customerFilter}
        />
      </ContentCard>
    </PageContainer>
  );
}
