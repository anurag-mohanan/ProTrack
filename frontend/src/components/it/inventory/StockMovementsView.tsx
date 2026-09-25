import { useMemo, useState } from 'react';
import { Typography } from '@mui/material';
import type { GridColDef } from '@mui/x-data-grid';
import { useQuery } from '@tanstack/react-query';
import { fetchStockMovements, itInventoryKeys } from '../../../api/itInventory';
import type { StockMovementRow } from '../../../types/itInventory';
import { formatCellValue, formatDate } from '../../../utils/format';
import { ClientPaginatedDataGrid } from '../../common/ClientPaginatedDataGrid';
import { ErrorState } from '../../common/ErrorState';
import { ContentCard } from '../../ui/cards';
import { FormField, FormSelect, SearchToolbar } from '../../ui/design-system';
import { MOVEMENT_TYPE_LABELS } from './inventoryFormat';

const LIMIT = 500;

export function StockMovementsView() {
  const [movementType, setMovementType] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const filters = {
    movement_type: movementType || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    limit: LIMIT,
  };
  const query = useQuery({
    queryKey: itInventoryKeys.movements(filters),
    queryFn: () => fetchStockMovements(filters),
  });

  const columns = useMemo<GridColDef<StockMovementRow>[]>(
    () => [
      {
        field: 'occurred_on',
        headerName: 'Date',
        width: 110,
        valueFormatter: (v) => formatDate(v as string),
      },
      { field: 'item_name', headerName: 'Item', flex: 1, minWidth: 160 },
      {
        field: 'movement_type',
        headerName: 'Type',
        width: 130,
        valueFormatter: (v) => MOVEMENT_TYPE_LABELS[String(v)] ?? String(v),
      },
      {
        field: 'quantity',
        headerName: 'Qty',
        type: 'number',
        width: 80,
        valueFormatter: (v) => (Number(v) > 0 ? `+${v}` : String(v)),
      },
      {
        field: 'new_qty',
        headerName: 'Balance',
        width: 110,
        valueGetter: (_v, row) => `${row.previous_qty} → ${row.new_qty}`,
      },
      {
        field: 'employee_name',
        headerName: 'Employee',
        width: 150,
        valueFormatter: (v) => formatCellValue(v),
      },
      {
        field: 'performed_by_name',
        headerName: 'Performed by',
        width: 150,
        valueFormatter: (v) => formatCellValue(v),
      },
      {
        field: 'reason',
        headerName: 'Reason / reference',
        flex: 1,
        minWidth: 180,
        valueGetter: (_v, row) =>
          [
            row.reason,
            row.reference,
            row.purchase_order && `PO ${row.purchase_order}`,
            row.invoice_number && `Inv ${row.invoice_number}`,
            row.counterpart_location,
          ]
            .filter(Boolean)
            .join(' · ') || '—',
      },
    ],
    [],
  );

  return (
    <>
      <SearchToolbar sticky>
        <FormSelect
          label="Movement type"
          value={movementType}
          onChange={(e) => setMovementType(String(e.target.value))}
          options={[
            { value: '', label: 'All types' },
            ...Object.entries(MOVEMENT_TYPE_LABELS).map(([value, label]) => ({ value, label })),
          ]}
          sx={{ minWidth: 170 }}
        />
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
        {query.data && query.data.total > LIMIT ? (
          <Typography variant="caption" color="text.secondary">
            Showing latest {LIMIT} of {query.data.total}. Narrow the date range to see older movements.
          </Typography>
        ) : null}
      </SearchToolbar>
      {query.isError ? (
        <ErrorState error={query.error} title="Unable to load stock movements" onRetry={() => void query.refetch()} />
      ) : (
        <ContentCard noPadding>
          <ClientPaginatedDataGrid
            rows={query.data?.items ?? []}
            columns={columns}
            getRowId={(row) => row.id}
            loading={query.isLoading}
            autoHeight
            filterKey={`${movementType}|${dateFrom}|${dateTo}`}
            localeText={{ noRowsLabel: 'No stock movements recorded.' }}
          />
        </ContentCard>
      )}
    </>
  );
}
