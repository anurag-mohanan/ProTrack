import { useMemo, useState } from 'react';
import { Chip, Stack } from '@mui/material';
import type { GridColDef } from '@mui/x-data-grid';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  fetchCustomerReturnsReport,
  itOperationsKeys,
} from '../../api/itOperations';
import { fetchCustomers } from '../../api/lookups';
import { ClientPaginatedDataGrid } from '../../components/common/ClientPaginatedDataGrid';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingState } from '../../components/common/LoadingState';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ContentCard } from '../../components/ui/cards';
import { FormSelect, SearchToolbar } from '../../components/ui/design-system';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import type { CustomerAssetReturnReportRow } from '../../types/itOperations';
import { formatCellValue, formatDate } from '../../utils/format';

export function ITReportsPage() {
  const navigate = useNavigate();
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

  const reportQuery = useQuery({
    queryKey: itOperationsKeys.customerReturnsReport(filters),
    queryFn: () => fetchCustomerReturnsReport(filters),
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

  const columns: GridColDef<CustomerAssetReturnReportRow>[] = [
    {
      field: 'customer',
      headerName: 'Customer',
      flex: 1,
      minWidth: 140,
      valueFormatter: (value) => formatCellValue(value),
    },
    {
      field: 'asset_number',
      headerName: 'Asset #',
      width: 120,
      valueFormatter: (value) => formatCellValue(value),
    },
    {
      field: 'asset_type',
      headerName: 'Asset type',
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
      headerName: 'Serial #',
      width: 130,
      valueFormatter: (value) => formatCellValue(value),
    },
    {
      field: 'purchase_owner',
      headerName: 'Purchase owner',
      width: 140,
      valueFormatter: (value) => formatCellValue(value),
    },
    {
      field: 'assigned_employee',
      headerName: 'Assigned employee',
      flex: 1,
      minWidth: 140,
      valueFormatter: (value) => formatCellValue(value),
    },
    {
      field: 'return_date',
      headerName: 'Return date',
      width: 120,
      valueFormatter: (value) => formatDate(value as string | null | undefined) || '—',
    },
    {
      field: 'condition',
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
      field: 'returned_by',
      headerName: 'Returned by',
      flex: 0.9,
      minWidth: 120,
      valueFormatter: (value) => formatCellValue(value),
    },
    {
      field: 'received_by',
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

  if (reportQuery.isLoading) {
    return <LoadingState message="Loading IT reports…" />;
  }

  if (reportQuery.isError) {
    return (
      <ErrorState
        error={reportQuery.error}
        title="Unable to load customer asset returns report"
        onRetry={() => void reportQuery.refetch()}
      />
    );
  }

  const rows = reportQuery.data ?? [];

  return (
    <PageContainer>
      <PageHeader
        title="Customer Asset Returns"
        subtitle="IT report of customer-owned assets returned from Prosohm custody. Rows stay forever and are excluded from current inventory."
        action={
          <Stack direction="row" spacing={1}>
            <ProsohmButton
              buttonVariant="outlined"
              onClick={() => navigate('/it/returned-assets')}
            >
              Returned assets
            </ProsohmButton>
            <ProsohmButton buttonVariant="outlined" onClick={() => navigate('/it/assets')}>
              Current assets
            </ProsohmButton>
          </Stack>
        }
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
