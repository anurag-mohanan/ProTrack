import { useMemo, useState } from 'react';
import { Chip, Dialog, DialogActions, DialogContent, DialogTitle, Stack, Typography } from '@mui/material';
import type { GridColDef } from '@mui/x-data-grid';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import {
  createStockLocation,
  fetchInventoryReference,
  fetchStockItems,
  itInventoryKeys,
} from '../../../api/itInventory';
import { getErrorMessage } from '../../../api/client';
import { useToast } from '../../../context/ToastContext';
import type { StockItemRow } from '../../../types/itInventory';
import { formatCellValue, formatDate } from '../../../utils/format';
import { ClientPaginatedDataGrid } from '../../common/ClientPaginatedDataGrid';
import { ErrorState } from '../../common/ErrorState';
import { ContentCard } from '../../ui/cards';
import { FormField, FormSelect, SearchToolbar } from '../../ui/design-system';
import { ProsohmButton } from '../../ui/ProsohmButton';
import { STOCK_STATUS_FILTERS } from './inventoryFormat';
import { StockItemDetailDrawer } from './StockItemDetailDrawer';
import { StockItemFormDrawer } from './StockItemFormDrawer';
import { SearchField } from './SearchField';
import { StockStatusChip } from './StockStatusChip';

type Props = { lowStockOnly?: boolean; canManage: boolean; canAssign: boolean };

export function StockItemsView({ lowStockOnly = false, canManage, canAssign }: Props) {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState('');
  const [kind, setKind] = useState('');
  const [locationId, setLocationId] = useState('');
  const [status, setStatus] = useState(() => searchParams.get('stock_status') ?? '');
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<StockItemRow | null>(null);
  const [locationOpen, setLocationOpen] = useState(false);
  const [locationName, setLocationName] = useState('');
  const selectedId = searchParams.get('item');

  const filters = {
    search: search || undefined,
    kind: kind || undefined,
    location_id: locationId || undefined,
    stock_status: lowStockOnly ? undefined : status || undefined,
  };
  const itemsQuery = useQuery({
    queryKey: itInventoryKeys.items(filters),
    queryFn: () => fetchStockItems(filters),
  });
  const referenceQuery = useQuery({ queryKey: itInventoryKeys.reference(), queryFn: fetchInventoryReference });

  const locationMutation = useMutation({
    mutationFn: () => createStockLocation({ name: locationName.trim() }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: itInventoryKeys.reference() });
      showSuccess('Location added.');
      setLocationOpen(false);
      setLocationName('');
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const rows = useMemo(() => {
    const data = itemsQuery.data ?? [];
    return lowStockOnly
      ? data.filter((r) => r.stock_status === 'low_stock' || r.stock_status === 'out_of_stock' || r.reorder_needed)
      : data;
  }, [itemsQuery.data, lowStockOnly]);

  const openItem = (id: string | null) => {
    const next = new URLSearchParams(searchParams);
    if (id) next.set('item', id);
    else next.delete('item');
    setSearchParams(next, { replace: true });
  };

  const columns = useMemo<GridColDef<StockItemRow>[]>(() => {
    const base: GridColDef<StockItemRow>[] = [
      { field: 'name', headerName: 'Item', flex: 1.3, minWidth: 180 },
      { field: 'item_kind_label', headerName: 'Kind', width: 120 },
      {
        field: 'location_name',
        headerName: 'Location',
        width: 130,
        valueFormatter: (v) => formatCellValue(v),
      },
      { field: 'on_hand', headerName: 'On hand', type: 'number', width: 90 },
      { field: 'reserved', headerName: 'Reserved', type: 'number', width: 90 },
      { field: 'available', headerName: 'Available', type: 'number', width: 95 },
      {
        field: 'min_stock',
        headerName: 'Min',
        type: 'number',
        width: 70,
        valueFormatter: (v) => (v === null || v === undefined ? '—' : String(v)),
      },
      {
        field: 'stock_status',
        headerName: 'Status',
        width: 140,
        renderCell: (p) => <StockStatusChip status={p.row.stock_status} />,
      },
    ];
    if (lowStockOnly) {
      return [
        ...base,
        { field: 'shortfall', headerName: 'Shortfall', type: 'number', width: 90 },
        { field: 'incoming', headerName: 'Incoming', type: 'number', width: 90 },
        { field: 'recommended_order_qty', headerName: 'Recommended', type: 'number', width: 115 },
        {
          field: 'supplier_name',
          headerName: 'Supplier',
          width: 150,
          valueFormatter: (v) => formatCellValue(v),
        },
        {
          field: 'lead_time_days',
          headerName: 'Lead time',
          width: 95,
          valueFormatter: (v) => (v === null || v === undefined ? '—' : `${v} d`),
        },
        {
          field: 'pending_restock_requests',
          headerName: 'Restock',
          width: 120,
          renderCell: (p) =>
            p.row.pending_restock_requests ? (
              <Chip size="small" color="info" label={`${p.row.pending_restock_requests} open`} />
            ) : (
              <Typography variant="caption" color="error.main">
                None requested
              </Typography>
            ),
        },
      ];
    }
    return [
      ...base,
      { field: 'incoming', headerName: 'Incoming', type: 'number', width: 90 },
      {
        field: 'supplier_name',
        headerName: 'Supplier',
        width: 150,
        valueFormatter: (v) => formatCellValue(v),
      },
      {
        field: 'last_movement_on',
        headerName: 'Last movement',
        width: 130,
        valueFormatter: (v) => formatDate(v as string | null) || '—',
      },
    ];
  }, [lowStockOnly]);

  const kindOptions = [
    { value: '', label: 'All kinds' },
    ...(referenceQuery.data?.stock_kinds ?? []).map((k) => ({ value: k.code, label: k.label })),
  ];
  const locationOptions = [
    { value: '', label: 'All locations' },
    ...(referenceQuery.data?.locations ?? []).map((loc) => ({ value: loc.id, label: loc.name })),
  ];

  return (
    <>
      <SearchToolbar sticky>
        <SearchField value={search} onChange={setSearch} placeholder="Search item, SKU, supplier, location…" />
        <FormSelect
          label="Kind"
          value={kind}
          onChange={(e) => setKind(String(e.target.value))}
          options={kindOptions}
          sx={{ minWidth: 160 }}
        />
        <FormSelect
          label="Location"
          value={locationId}
          onChange={(e) => setLocationId(String(e.target.value))}
          options={locationOptions}
          sx={{ minWidth: 160 }}
        />
        {!lowStockOnly ? (
          <FormSelect
            label="Stock status"
            value={status}
            onChange={(e) => setStatus(String(e.target.value))}
            options={STOCK_STATUS_FILTERS}
            sx={{ minWidth: 170 }}
          />
        ) : null}
        {canManage ? (
          <Stack direction="row" spacing={1} sx={{ ml: 'auto' }}>
            <ProsohmButton buttonVariant="outlined" onClick={() => setLocationOpen(true)}>
              Add location
            </ProsohmButton>
            <ProsohmButton
              onClick={() => {
                setEditing(null);
                setFormOpen(true);
              }}
            >
              New stock item
            </ProsohmButton>
          </Stack>
        ) : null}
      </SearchToolbar>
      {itemsQuery.isError ? (
        <ErrorState error={itemsQuery.error} title="Unable to load stock" onRetry={() => void itemsQuery.refetch()} />
      ) : (
        <ContentCard noPadding>
          <ClientPaginatedDataGrid
            rows={rows}
            columns={columns}
            getRowId={(row) => row.id}
            loading={itemsQuery.isLoading}
            autoHeight
            onRowClick={(p) => openItem(String(p.id))}
            filterKey={`${search}|${kind}|${locationId}|${status}|${lowStockOnly}`}
            localeText={{
              noRowsLabel: lowStockOnly
                ? 'No items are below minimum stock.'
                : 'No stock items yet. Create one to start tracking quantities.',
            }}
          />
        </ContentCard>
      )}
      <StockItemDetailDrawer
        itemId={selectedId}
        onClose={() => openItem(null)}
        canManage={canManage}
        canAssign={canAssign}
        onEdit={() => {
          const row = (itemsQuery.data ?? []).find((r) => r.id === selectedId) ?? null;
          setEditing(row);
          setFormOpen(Boolean(row));
        }}
      />
      <StockItemFormDrawer open={formOpen} item={editing} onClose={() => setFormOpen(false)} />
      <Dialog open={locationOpen} onClose={() => setLocationOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>Add stock location</DialogTitle>
        <DialogContent>
          <FormField
            sx={{ mt: 1 }}
            label="Location name"
            required
            value={locationName}
            onChange={(e) => setLocationName(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setLocationOpen(false)}>
            Cancel
          </ProsohmButton>
          <ProsohmButton
            loading={locationMutation.isPending}
            disabled={!locationName.trim() || locationMutation.isPending}
            onClick={() => locationMutation.mutate()}
          >
            Add
          </ProsohmButton>
        </DialogActions>
      </Dialog>
    </>
  );
}
