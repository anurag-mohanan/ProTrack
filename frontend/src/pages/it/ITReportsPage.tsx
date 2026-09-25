import { useMemo, useState, type ReactNode } from 'react';
import { Chip, Stack } from '@mui/material';
import type { GridColDef } from '@mui/x-data-grid';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  fetchInventoryReport,
  fetchInventoryReportCatalog,
  itInventoryKeys,
} from '../../api/itInventory';
import { downloadCsv, toCsv } from '../../components/it/inventory/inventoryFormat';
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
import { FormField, FormSelect, SearchToolbar } from '../../components/ui/design-system';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import type { CustomerAssetReturnReportRow } from '../../types/itOperations';
import { formatCellValue, formatDate } from '../../utils/format';

const CUSTOMER_RETURNS = 'customer_returns';

export function ITReportsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const report = searchParams.get('report') ?? CUSTOMER_RETURNS;
  const catalogQuery = useQuery({
    queryKey: itInventoryKeys.reportCatalog(),
    queryFn: fetchInventoryReportCatalog,
  });
  const reportOptions = [
    { value: CUSTOMER_RETURNS, label: 'Customer asset returns' },
    ...(catalogQuery.data ?? []).map((r) => ({ value: r.key, label: r.title })),
  ];
  const selector = (
    <FormSelect
      label="Report"
      value={report}
      onChange={(event) => {
        const next = new URLSearchParams(searchParams);
        next.set('report', String(event.target.value));
        setSearchParams(next, { replace: true });
      }}
      options={reportOptions}
      sx={{ minWidth: 260 }}
    />
  );
  return report === CUSTOMER_RETURNS ? (
    <CustomerReturnsReport selector={selector} />
  ) : (
    <InventoryReportView reportKey={report} selector={selector} />
  );
}

function InventoryReportView({ reportKey, selector }: { reportKey: string; selector: ReactNode }) {
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const dated = reportKey === 'stock_movements';
  const filters = dated ? { date_from: dateFrom || undefined, date_to: dateTo || undefined } : {};
  const query = useQuery({
    queryKey: itInventoryKeys.report(reportKey, filters),
    queryFn: () => fetchInventoryReport(reportKey, filters),
  });
  const columns = useMemo<GridColDef[]>(
    () =>
      (query.data?.columns ?? []).map((c) => ({
        field: c.field,
        headerName: c.header,
        flex: 1,
        minWidth: 120,
        valueFormatter: (value: unknown) =>
          typeof value === 'boolean' ? (value ? 'Yes' : 'No') : formatCellValue(value),
      })),
    [query.data],
  );

  return (
    <PageContainer>
      <PageHeader
        title={query.data?.title ?? 'IT report'}
        action={
          <ProsohmButton
            buttonVariant="outlined"
            disabled={!query.data?.rows.length}
            onClick={() =>
              query.data &&
              downloadCsv(`${reportKey}.csv`, toCsv(query.data.columns, query.data.rows))
            }
          >
            Export CSV
          </ProsohmButton>
        }
      />
      <SearchToolbar sticky>
        {selector}
        {dated ? (
          <>
            <FormField
              label="From"
              type="date"
              size="small"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <FormField
              label="To"
              type="date"
              size="small"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
          </>
        ) : null}
      </SearchToolbar>
      {query.isError ? (
        <ErrorState error={query.error} title="Unable to load report" onRetry={() => void query.refetch()} />
      ) : (
        <ContentCard noPadding>
          <ClientPaginatedDataGrid
            rows={query.data?.rows ?? []}
            columns={columns}
            getRowId={(row) => String(row.id)}
            loading={query.isLoading}
            autoHeight
            filterKey={`${reportKey}|${dateFrom}|${dateTo}`}
          />
        </ContentCard>
      )}
    </PageContainer>
  );
}

function CustomerReturnsReport({ selector }: { selector: ReactNode }) {
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
        {selector}
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
