import { useState, type FormEvent } from 'react';
import { FormControlLabel, Stack, Switch } from '@mui/material';
import Inventory2RoundedIcon from '@mui/icons-material/Inventory2Rounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createStockItem,
  fetchInventoryReference,
  itInventoryKeys,
  updateStockItem,
  type StockItemPayload,
} from '../../../api/itInventory';
import { fetchMasterSuppliers } from '../../../api/itOperations';
import { getErrorMessage } from '../../../api/client';
import { useToast } from '../../../context/ToastContext';
import type { StockItemRow } from '../../../types/itInventory';
import { FormDrawer, FormField, FormSection, FormSelect } from '../../ui/design-system';

type Props = { open: boolean; item: StockItemRow | null; onClose: () => void };

const NUMERIC = ['min_stock', 'reorder_point', 'target_stock', 'reorder_qty', 'lead_time_days'] as const;

function initialState(item: StockItemRow | null): Record<string, string> {
  const s = (v: unknown) => (v === null || v === undefined ? '' : String(v));
  return {
    name: s(item?.name),
    description: s(item?.description),
    item_kind: s(item?.item_kind),
    sku: s(item?.sku),
    supplier_id: s(item?.supplier_id),
    supplier_sku: s(item?.supplier_sku),
    unit_cost: s(item?.unit_cost),
    min_stock: item ? s(item.min_stock) : '2',
    reorder_point: s(item?.reorder_point),
    target_stock: s(item?.target_stock),
    reorder_qty: s(item?.reorder_qty),
    lead_time_days: s(item?.lead_time_days),
    location_id: s(item?.location_id),
    notes: s(item?.notes),
    opening_qty: '0',
  };
}

export function StockItemFormDrawer({ open, item, onClose }: Props) {
  return open ? <StockItemForm key={item?.id ?? 'new'} item={item} onClose={onClose} /> : null;
}

function StockItemForm({ item, onClose }: { item: StockItemRow | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [form, setForm] = useState(() => initialState(item));
  const [returnable, setReturnable] = useState(item?.is_returnable ?? true);
  const set = (key: string) => (value: string) => setForm((prev) => ({ ...prev, [key]: value }));

  const referenceQuery = useQuery({ queryKey: itInventoryKeys.reference(), queryFn: fetchInventoryReference });
  const suppliersQuery = useQuery({
    queryKey: ['it-master', 'suppliers', 'active'],
    queryFn: () => fetchMasterSuppliers({ active_only: true }),
  });

  const mutation = useMutation({
    mutationFn: (body: StockItemPayload) => (item ? updateStockItem(item.id, body) : createStockItem(body)),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: itInventoryKeys.all });
      showSuccess(item ? 'Stock item updated.' : 'Stock item created.');
      onClose();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const text = (key: string) => (form[key].trim() ? form[key].trim() : null);
    const body: StockItemPayload = {
      name: form.name.trim(),
      description: text('description'),
      item_kind: text('item_kind'),
      sku: text('sku'),
      supplier_id: text('supplier_id'),
      supplier_sku: text('supplier_sku'),
      unit_cost: form.unit_cost ? Number(form.unit_cost) : null,
      location_id: text('location_id'),
      notes: text('notes'),
      is_returnable: returnable,
    };
    for (const key of NUMERIC) body[key] = form[key] === '' ? null : Number(form[key]);
    if (!item) body.opening_qty = Number(form.opening_qty || 0);
    mutation.mutate(body);
  }

  const kindOptions = (referenceQuery.data?.stock_kinds ?? []).map((k) => ({ value: k.code, label: k.label }));

  return (
    <FormDrawer
      open
      onClose={onClose}
      title={item ? `Edit ${item.name}` : 'New stock item'}
      subtitle="Quantity-tracked consumable (not a serialized asset)"
      icon={Inventory2RoundedIcon}
      formId="stock-item-form"
      loading={mutation.isPending}
      submitDisabled={!form.name.trim()}
    >
      <form id="stock-item-form" onSubmit={submit}>
        <Stack spacing={3}>
          <FormSection title="Item">
            <Stack spacing={2}>
              <FormField label="Name" required value={form.name} onChange={(e) => set('name')(e.target.value)} />
              <FormSelect
                label="Kind"
                value={form.item_kind}
                onChange={(e) => set('item_kind')(String(e.target.value))}
                options={[{ value: '', label: 'Detect from name' }, ...kindOptions]}
              />
              <Stack direction="row" spacing={2}>
                <FormField label="Internal SKU" value={form.sku} onChange={(e) => set('sku')(e.target.value)} />
                <FormSelect
                  label="Location"
                  value={form.location_id}
                  onChange={(e) => set('location_id')(String(e.target.value))}
                  options={[
                    { value: '', label: 'Not set' },
                    ...(referenceQuery.data?.locations ?? []).map((loc) => ({ value: loc.id, label: loc.name })),
                  ]}
                />
              </Stack>
              <FormField
                label="Description"
                value={form.description}
                onChange={(e) => set('description')(e.target.value)}
              />
              <FormControlLabel
                control={<Switch checked={returnable} onChange={(e) => setReturnable(e.target.checked)} />}
                label="Returnable (employees can return issued units to stock)"
              />
              {!item ? (
                <FormField
                  label="Opening quantity on hand"
                  type="number"
                  value={form.opening_qty}
                  onChange={(e) => set('opening_qty')(e.target.value)}
                  slotProps={{ htmlInput: { min: 0 } }}
                  helper="Recorded as an opening-balance movement."
                />
              ) : null}
            </Stack>
          </FormSection>
          <FormSection title="Stock thresholds">
            <Stack spacing={2}>
              <Stack direction="row" spacing={2}>
                <FormField
                  label="Minimum stock"
                  type="number"
                  value={form.min_stock}
                  onChange={(e) => set('min_stock')(e.target.value)}
                  slotProps={{ htmlInput: { min: 0 } }}
                  helper="Low stock when available falls below this."
                />
                <FormField
                  label="Reorder point"
                  type="number"
                  value={form.reorder_point}
                  onChange={(e) => set('reorder_point')(e.target.value)}
                  slotProps={{ htmlInput: { min: 0 } }}
                />
              </Stack>
              <Stack direction="row" spacing={2}>
                <FormField
                  label="Target stock"
                  type="number"
                  value={form.target_stock}
                  onChange={(e) => set('target_stock')(e.target.value)}
                  slotProps={{ htmlInput: { min: 0 } }}
                />
                <FormField
                  label="Reorder quantity"
                  type="number"
                  value={form.reorder_qty}
                  onChange={(e) => set('reorder_qty')(e.target.value)}
                  slotProps={{ htmlInput: { min: 0 } }}
                />
              </Stack>
            </Stack>
          </FormSection>
          <FormSection title="Purchasing">
            <Stack spacing={2}>
              <FormSelect
                label="Preferred supplier"
                searchable
                value={form.supplier_id}
                onChange={(e) => set('supplier_id')(String(e.target.value))}
                options={(suppliersQuery.data ?? []).map((s) => ({ value: s.id, label: s.name }))}
              />
              <Stack direction="row" spacing={2}>
                <FormField
                  label="Supplier SKU"
                  value={form.supplier_sku}
                  onChange={(e) => set('supplier_sku')(e.target.value)}
                />
                <FormField
                  label="Lead time (days)"
                  type="number"
                  value={form.lead_time_days}
                  onChange={(e) => set('lead_time_days')(e.target.value)}
                  slotProps={{ htmlInput: { min: 0 } }}
                />
              </Stack>
              <FormField
                label="Unit cost"
                type="number"
                value={form.unit_cost}
                onChange={(e) => set('unit_cost')(e.target.value)}
                slotProps={{ htmlInput: { min: 0, step: '0.01' } }}
              />
              <FormField
                label="Notes"
                multiline
                minRows={2}
                value={form.notes}
                onChange={(e) => set('notes')(e.target.value)}
              />
            </Stack>
          </FormSection>
        </Stack>
      </form>
    </FormDrawer>
  );
}
