import { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  LinearProgress,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  executeAssetBulkAction,
  fetchItPeoplePaginated,
  itOperationsKeys,
  previewAssetBulkAction,
} from '../../api/itOperations';
import { fetchCustomers } from '../../api/lookups';
import { getErrorMessage } from '../../api/client';
import { ProsohmButton } from '../ui/ProsohmButton';
import { FormField, FormSelect } from '../ui/design-system';
import { useToast } from '../../context/ToastContext';
import type {
  AssetBulkAction,
  AssetBulkActionResult,
  AssetBulkPreviewResponse,
} from '../../types/itOperations';

const STATUS_OPTIONS = [
  { value: 'available', label: 'Available' },
  { value: 'maintenance', label: 'Maintenance' },
  { value: 'awaiting_return', label: 'Reserved / Awaiting return' },
  { value: 'retired', label: 'Retired' },
  { value: 'disposed', label: 'Disposed' },
];

const OWNER_OPTIONS = [
  { value: 'organization', label: 'Prosohm / Organization' },
  { value: 'customer', label: 'Customer' },
];

type BulkDialog =
  | 'delete'
  | 'assign_user'
  | 'assign_location'
  | 'change_status'
  | 'change_ownership'
  | 'renumber'
  | 'return_to_customer'
  | 'result'
  | null;

export function AssetBulkActionBar({
  selectedIds,
  matchingTotal,
  pageSelectedCount,
  canManage,
  canAssign,
  canReturnToCustomer,
  onClearSelection,
  onSelectAllMatching,
  onComplete,
}: {
  selectedIds: string[];
  matchingTotal: number;
  pageSelectedCount: number;
  canManage: boolean;
  canAssign: boolean;
  canReturnToCustomer: boolean;
  onClearSelection: () => void;
  onSelectAllMatching: () => Promise<void>;
  onComplete: () => void;
}) {
  const { showSuccess, showError } = useToast();
  const count = selectedIds.length;
  const [dialog, setDialog] = useState<BulkDialog>(null);
  const [preview, setPreview] = useState<AssetBulkPreviewResponse | null>(null);
  const [result, setResult] = useState<AssetBulkActionResult | null>(null);
  const [progressLabel, setProgressLabel] = useState<string | null>(null);

  // Shared form state
  const [userId, setUserId] = useState('');
  const [userSearch, setUserSearch] = useState('');
  const [assignMode, setAssignMode] = useState<'replace' | 'only_unassigned' | ''>('');
  const [location, setLocation] = useState('');
  const [status, setStatus] = useState('available');
  const [forceStatus, setForceStatus] = useState(false);
  const [purchasedBy, setPurchasedBy] = useState('organization');
  const [ownerCustomerId, setOwnerCustomerId] = useState('');
  const [prefix, setPrefix] = useState('IT-');
  const [startingNumber, setStartingNumber] = useState('100');
  const [digits, setDigits] = useState('3');
  const [suffix, setSuffix] = useState('');
  const [returnDate, setReturnDate] = useState(new Date().toISOString().slice(0, 10));
  const [returnNotes, setReturnNotes] = useState('');
  const [returnCustomerId, setReturnCustomerId] = useState('');
  const [selectingMatching, setSelectingMatching] = useState(false);

  const peopleQuery = useQuery({
    queryKey: [...itOperationsKeys.people({ search: userSearch, status: 'active' })],
    queryFn: () =>
      fetchItPeoplePaginated({
        search: userSearch.trim() || undefined,
        status: 'active',
        page_size: 50,
      }),
    enabled: dialog === 'assign_user' && canAssign,
  });

  const customersQuery = useQuery({
    queryKey: ['lookups', 'customers'],
    queryFn: fetchCustomers,
    enabled:
      (dialog === 'change_ownership' || dialog === 'return_to_customer') &&
      (canManage || canReturnToCustomer),
  });

  const customerOptions = useMemo(
    () => (customersQuery.data ?? []).map((c) => ({ value: c.id, label: c.name })),
    [customersQuery.data],
  );

  const people = peopleQuery.data?.items ?? [];
  const selectedPerson = people.find((p) => p.user_id === userId);

  const openDialog = async (action: Exclude<BulkDialog, 'result' | null>) => {
    setPreview(null);
    setAssignMode('');
    setForceStatus(false);
    setDialog(action);
    if (action === 'delete' || action === 'assign_user' || action === 'return_to_customer') {
      try {
        const body = await previewAssetBulkAction({
          asset_ids: selectedIds,
          action,
          parameters: {},
        });
        setPreview(body);
      } catch (error) {
        showError(getErrorMessage(error));
        setDialog(null);
      }
    }
  };

  const runMutation = useMutation({
    mutationFn: async (payload: {
      action: AssetBulkAction;
      parameters?: Record<string, unknown>;
      options?: Record<string, unknown>;
    }) => {
      setProgressLabel(
        payload.action === 'delete'
          ? `Deleting assets… 0 / ${count}`
          : `Updating… 0 / ${count}`,
      );
      // Single backend call — progress is informational for large batches
      const res = await executeAssetBulkAction({
        asset_ids: selectedIds,
        action: payload.action,
        parameters: payload.parameters,
        options: payload.options,
      });
      setProgressLabel(`Updating… ${res.updated} / ${count}`);
      return res;
    },
    onSuccess: (res) => {
      setProgressLabel(null);
      setResult(res);
      setDialog('result');
      showSuccess(
        `Bulk update complete: ${res.updated} updated` +
          (res.skipped ? `, ${res.skipped} skipped` : ''),
      );
      onComplete();
    },
    onError: (error) => {
      setProgressLabel(null);
      showError(getErrorMessage(error));
    },
  });

  const refreshRenumberPreview = async () => {
    try {
      const body = await previewAssetBulkAction({
        asset_ids: selectedIds,
        action: 'renumber',
        parameters: {
          prefix,
          starting_number: Number(startingNumber),
          digits: Number(digits),
          suffix,
        },
      });
      setPreview(body);
    } catch (error) {
      showError(getErrorMessage(error));
    }
  };

  const refreshStatusPreview = async () => {
    try {
      const body = await previewAssetBulkAction({
        asset_ids: selectedIds,
        action: 'change_status',
        parameters: { status },
      });
      setPreview(body);
    } catch (error) {
      showError(getErrorMessage(error));
    }
  };

  if (count === 0) return null;

  const showSelectAllMatching =
    matchingTotal > pageSelectedCount && count < matchingTotal && pageSelectedCount > 0;

  return (
    <>
      <Box
        sx={{
          mb: 1.5,
          px: 2,
          py: 1.25,
          borderRadius: 2,
          border: '1px solid',
          borderColor: 'divider',
          bgcolor: 'action.hover',
          overflowX: 'auto',
        }}
      >
        <Stack
          direction={{ xs: 'column', md: 'row' }}
          spacing={1.5}
          alignItems={{ md: 'center' }}
          justifyContent="space-between"
        >
          <Stack spacing={0.25}>
            <Typography variant="subtitle2" fontWeight={700}>
              {count} asset{count === 1 ? '' : 's'} selected
            </Typography>
            {showSelectAllMatching ? (
              <Typography variant="caption" color="text.secondary">
                {pageSelectedCount} on this page.{' '}
                <Box
                  component="button"
                  type="button"
                  onClick={async () => {
                    setSelectingMatching(true);
                    try {
                      await onSelectAllMatching();
                    } finally {
                      setSelectingMatching(false);
                    }
                  }}
                  disabled={selectingMatching}
                  sx={{
                    border: 0,
                    background: 'none',
                    color: 'primary.main',
                    cursor: 'pointer',
                    p: 0,
                    font: 'inherit',
                    textDecoration: 'underline',
                  }}
                >
                  Select all {matchingTotal} matching assets
                </Box>
              </Typography>
            ) : null}
            <Typography variant="caption" color="text.secondary">
              Changing filters keeps your current selection.
            </Typography>
          </Stack>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            {canAssign ? (
              <ProsohmButton
                buttonVariant="outlined"
                size="small"
                onClick={() => void openDialog('assign_user')}
              >
                Assign User
              </ProsohmButton>
            ) : null}
            {canManage ? (
              <>
                <ProsohmButton
                  buttonVariant="outlined"
                  size="small"
                  onClick={() => void openDialog('assign_location')}
                >
                  Assign Location
                </ProsohmButton>
                <ProsohmButton
                  buttonVariant="outlined"
                  size="small"
                  onClick={() => {
                    setDialog('change_status');
                    void refreshStatusPreview();
                  }}
                >
                  Change Status
                </ProsohmButton>
                <ProsohmButton
                  buttonVariant="outlined"
                  size="small"
                  onClick={() => void openDialog('change_ownership')}
                >
                  Change Owner
                </ProsohmButton>
                <ProsohmButton
                  buttonVariant="outlined"
                  size="small"
                  onClick={() => {
                    setDialog('renumber');
                    void refreshRenumberPreview();
                  }}
                >
                  Renumber
                </ProsohmButton>
              </>
            ) : null}
            {canReturnToCustomer ? (
              <ProsohmButton
                buttonVariant="outlined"
                size="small"
                onClick={() => void openDialog('return_to_customer')}
              >
                Mark Returned
              </ProsohmButton>
            ) : null}
            {canManage ? (
              <ProsohmButton
                buttonVariant="danger"
                size="small"
                onClick={() => void openDialog('delete')}
              >
                Delete
              </ProsohmButton>
            ) : null}
            <ProsohmButton buttonVariant="outlined" size="small" onClick={onClearSelection}>
              Clear Selection
            </ProsohmButton>
          </Stack>
        </Stack>
        {progressLabel ? (
          <Box sx={{ mt: 1.5 }}>
            <Typography variant="caption" color="text.secondary">
              {progressLabel}
            </Typography>
            <LinearProgress sx={{ mt: 0.5 }} />
          </Box>
        ) : null}
      </Box>

      {/* Delete */}
      <Dialog open={dialog === 'delete'} onClose={() => setDialog(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Delete {count} Assets?</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: 1.5 }}>
            The following assets will be permanently deleted from active inventory (soft-deleted).
            This action cannot be undone.
          </Typography>
          <Box component="ul" sx={{ pl: 2, m: 0, maxHeight: 160, overflow: 'auto' }}>
            {(preview?.asset_numbers ?? []).map((n) => (
              <li key={n}>
                <Typography variant="body2">{n}</Typography>
              </li>
            ))}
          </Box>
          {preview && (preview.blocked_count ?? 0) > 0 ? (
            <Alert severity="warning" sx={{ mt: 2 }}>
              {preview.blocked_count} of {preview.selected} selected assets have active
              relationships and cannot be deleted.
              <Box component="ul" sx={{ pl: 2, mb: 0 }}>
                {(preview.dependencies ?? [])
                  .filter((d) => !d.can_delete)
                  .map((d) => (
                    <li key={d.asset_number}>
                      {d.asset_number} — {d.blockers.join('; ')}
                    </li>
                  ))}
              </Box>
            </Alert>
          ) : null}
          {(preview?.dependencies ?? []).some((d) => d.warnings.length > 0) ? (
            <Alert severity="info" sx={{ mt: 1.5 }}>
              Related records will remain linked (computers / IPs). Review before confirming.
            </Alert>
          ) : null}
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setDialog(null)}>
            Cancel
          </ProsohmButton>
          {(preview?.blocked_count ?? 0) > 0 && (preview?.eligible_count ?? 0) > 0 ? (
            <ProsohmButton
              buttonVariant="danger"
              loading={runMutation.isPending}
              onClick={() =>
                runMutation.mutate({
                  action: 'delete',
                  options: { allow_partial: true },
                })
              }
            >
              Delete {preview?.eligible_count} Eligible
            </ProsohmButton>
          ) : null}
          <ProsohmButton
            buttonVariant="danger"
            loading={runMutation.isPending}
            disabled={(preview?.blocked_count ?? 0) > 0 && (preview?.eligible_count ?? 0) === 0}
            onClick={() =>
              runMutation.mutate({
                action: 'delete',
                options: {
                  allow_partial: (preview?.blocked_count ?? 0) > 0,
                },
              })
            }
          >
            Delete {count} Assets
          </ProsohmButton>
        </DialogActions>
      </Dialog>

      {/* Assign user */}
      <Dialog open={dialog === 'assign_user'} onClose={() => setDialog(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Assign Assets to User</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Selected: {count} assets
          </Typography>
          <FormField
            label="Search employee"
            value={userSearch}
            onChange={(e) => setUserSearch(e.target.value)}
            placeholder="Name, email…"
            sx={{ mb: 1.5 }}
          />
          <TextField
            select
            fullWidth
            label="User"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            size="small"
          >
            {(people ?? []).map((p) => (
              <MenuItem key={p.user_id} value={p.user_id}>
                {p.full_name}
                {p.department ? ` · ${p.department}` : ''}
                {p.team ? ` · ${p.team}` : ''}
                {p.designation ? ` · ${p.designation}` : ''}
              </MenuItem>
            ))}
          </TextField>
          {selectedPerson ? (
            <Alert severity="info" sx={{ mt: 2 }}>
              Assign selected assets to: <strong>{selectedPerson.full_name}</strong>
              {selectedPerson.department ? ` · ${selectedPerson.department}` : ''}
              {selectedPerson.team ? ` · ${selectedPerson.team}` : ''}
            </Alert>
          ) : null}
          {(preview?.already_assigned?.length ?? 0) > 0 ? (
            <Alert severity="warning" sx={{ mt: 2 }}>
              {preview!.already_assigned!.length} assets are currently assigned.
              <FormSelect
                label="Assignment conflict"
                value={assignMode}
                onChange={(e) =>
                  setAssignMode(String(e.target.value) as typeof assignMode)
                }
                options={[
                  { value: '', label: 'Choose how to proceed…' },
                  { value: 'only_unassigned', label: 'Assign only unassigned assets' },
                  { value: 'replace', label: 'Replace current assignment' },
                ]}
                sx={{ mt: 1.5 }}
              />
            </Alert>
          ) : null}
          {(preview?.ineligible?.length ?? 0) > 0 ? (
            <Alert severity="info" sx={{ mt: 1.5 }}>
              Some selected assets cannot use this action.
              <Box component="ul" sx={{ pl: 2, mb: 0 }}>
                {preview!.ineligible!.map((row) => (
                  <li key={row.asset_number}>
                    {row.asset_number} — {row.reason}
                  </li>
                ))}
              </Box>
            </Alert>
          ) : null}
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setDialog(null)}>
            Cancel
          </ProsohmButton>
          <ProsohmButton
            buttonVariant="primary"
            loading={runMutation.isPending}
            disabled={
              !userId ||
              ((preview?.already_assigned?.length ?? 0) > 0 && !assignMode)
            }
            onClick={() =>
              runMutation.mutate({
                action: 'assign_user',
                parameters: { user_id: userId },
                options: {
                  replace_assignments: assignMode === 'replace',
                  only_unassigned: assignMode === 'only_unassigned',
                },
              })
            }
          >
            Assign
          </ProsohmButton>
        </DialogActions>
      </Dialog>

      {/* Location */}
      <Dialog
        open={dialog === 'assign_location'}
        onClose={() => setDialog(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Assign Location</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Selected: {count} assets
          </Typography>
          <FormField
            label="Location"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="e.g. Ground Floor"
          />
          {location.trim() ? (
            <Alert severity="info" sx={{ mt: 2 }}>
              {count} assets will be moved to: <strong>{location.trim()}</strong>
            </Alert>
          ) : null}
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setDialog(null)}>
            Cancel
          </ProsohmButton>
          <ProsohmButton
            buttonVariant="primary"
            loading={runMutation.isPending}
            disabled={!location.trim()}
            onClick={() =>
              runMutation.mutate({
                action: 'assign_location',
                parameters: { location: location.trim() },
              })
            }
          >
            Assign Location
          </ProsohmButton>
        </DialogActions>
      </Dialog>

      {/* Status */}
      <Dialog
        open={dialog === 'change_status'}
        onClose={() => setDialog(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Change Status</DialogTitle>
        <DialogContent>
          <FormSelect
            label="Status"
            value={status}
            onChange={(e) => {
              setStatus(String(e.target.value));
              setTimeout(() => void refreshStatusPreview(), 0);
            }}
            options={STATUS_OPTIONS}
          />
          {(preview?.transitions ?? []).some((t) => t.rule === 'force' || t.rule === 'block') ? (
            <Alert severity="warning" sx={{ mt: 2 }}>
              Some transitions need confirmation or are blocked.
              <Box component="ul" sx={{ pl: 2, mb: 0 }}>
                {(preview?.transitions ?? [])
                  .filter((t) => t.rule !== 'ok')
                  .map((t) => (
                    <li key={t.asset_number}>
                      {t.asset_number}: {t.reason}
                    </li>
                  ))}
              </Box>
              {(preview?.transitions ?? []).some((t) => t.rule === 'force') ? (
                <FormSelect
                  label="Administrator confirmation"
                  value={forceStatus ? 'yes' : ''}
                  onChange={(e) => setForceStatus(String(e.target.value) === 'yes')}
                  options={[
                    { value: '', label: 'Do not force restricted transitions' },
                    { value: 'yes', label: 'Confirm restricted transitions' },
                  ]}
                  sx={{ mt: 1.5 }}
                />
              ) : null}
            </Alert>
          ) : null}
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setDialog(null)}>
            Cancel
          </ProsohmButton>
          <ProsohmButton
            buttonVariant="primary"
            loading={runMutation.isPending}
            onClick={() =>
              runMutation.mutate({
                action: 'change_status',
                parameters: { status },
                options: { force_status: forceStatus, allow_partial: true },
              })
            }
          >
            Change Status
          </ProsohmButton>
        </DialogActions>
      </Dialog>

      {/* Ownership */}
      <Dialog
        open={dialog === 'change_ownership'}
        onClose={() => setDialog(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Change Ownership</DialogTitle>
        <DialogContent>
          <Alert severity="info" sx={{ mb: 2 }}>
            Ownership is separate from Customer Used For. This action does not change Customer Used
            For unless you edit assets individually.
          </Alert>
          <FormSelect
            label="Owner"
            value={purchasedBy}
            onChange={(e) => {
              setPurchasedBy(String(e.target.value));
              if (String(e.target.value) !== 'customer') setOwnerCustomerId('');
            }}
            options={OWNER_OPTIONS}
          />
          {purchasedBy === 'customer' ? (
            <FormSelect
              label="Select Customer"
              value={ownerCustomerId}
              onChange={(e) => setOwnerCustomerId(String(e.target.value))}
              options={[{ value: '', label: 'Select customer…' }, ...customerOptions]}
              sx={{ mt: 1.5 }}
            />
          ) : null}
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setDialog(null)}>
            Cancel
          </ProsohmButton>
          <ProsohmButton
            buttonVariant="primary"
            loading={runMutation.isPending}
            disabled={purchasedBy === 'customer' && !ownerCustomerId}
            onClick={() =>
              runMutation.mutate({
                action: 'change_ownership',
                parameters: {
                  purchased_by: purchasedBy,
                  owner_customer_id:
                    purchasedBy === 'customer' ? ownerCustomerId : null,
                },
              })
            }
          >
            Update Ownership
          </ProsohmButton>
        </DialogActions>
      </Dialog>

      {/* Renumber */}
      <Dialog open={dialog === 'renumber'} onClose={() => setDialog(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Assign Asset Numbers</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            Changing asset numbers may affect references to these assets. Previous numbers are kept
            as legacy identifiers.
          </Alert>
          <Stack direction="row" spacing={1.5} sx={{ mb: 1.5 }}>
            <FormField
              label="Prefix"
              value={prefix}
              onChange={(e) => setPrefix(e.target.value)}
              sx={{ flex: 1 }}
            />
            <FormField
              label="Starting"
              value={startingNumber}
              onChange={(e) => setStartingNumber(e.target.value)}
              sx={{ width: 100 }}
            />
            <FormField
              label="Digits"
              value={digits}
              onChange={(e) => setDigits(e.target.value)}
              sx={{ width: 90 }}
            />
            <FormField
              label="Suffix"
              value={suffix}
              onChange={(e) => setSuffix(e.target.value)}
              sx={{ flex: 1 }}
            />
          </Stack>
          <ProsohmButton
            buttonVariant="outlined"
            size="small"
            onClick={() => void refreshRenumberPreview()}
            sx={{ mb: 1.5 }}
          >
            Refresh preview
          </ProsohmButton>
          {(preview?.existing_conflicts?.length || preview?.batch_duplicates?.length) ? (
            <Alert severity="error" sx={{ mb: 1.5 }}>
              Generated asset number{' '}
              {(preview.existing_conflicts?.[0] || preview.batch_duplicates?.[0]) ?? ''} already
              exists. The operation will not partially rename the selection.
            </Alert>
          ) : null}
          <Box sx={{ maxHeight: 220, overflow: 'auto' }}>
            <Typography variant="caption" color="text.secondary">
              Current → New
            </Typography>
            {(preview?.preview ?? []).map((row) => (
              <Typography key={row.asset_id} variant="body2">
                {row.current} → {row.new}
              </Typography>
            ))}
          </Box>
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setDialog(null)}>
            Cancel
          </ProsohmButton>
          <ProsohmButton
            buttonVariant="primary"
            loading={runMutation.isPending}
            disabled={preview?.can_apply === false}
            onClick={() =>
              runMutation.mutate({
                action: 'renumber',
                parameters: {
                  prefix,
                  starting_number: Number(startingNumber),
                  digits: Number(digits),
                  suffix,
                },
              })
            }
          >
            Apply Numbers
          </ProsohmButton>
        </DialogActions>
      </Dialog>

      {/* Return to customer */}
      <Dialog
        open={dialog === 'return_to_customer'}
        onClose={() => setDialog(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Return Assets</DialogTitle>
        <DialogContent>
          {(preview?.ineligible?.length ?? 0) > 0 ? (
            <Alert severity="info" sx={{ mb: 2 }}>
              Some selected assets cannot use this action (not customer-owned or already returned).
            </Alert>
          ) : null}
          <FormSelect
            label="Customer"
            value={returnCustomerId}
            onChange={(e) => setReturnCustomerId(String(e.target.value))}
            options={[
              { value: '', label: 'Use each asset’s owner customer' },
              ...customerOptions,
            ]}
          />
          <FormField
            label="Return date"
            type="date"
            value={returnDate}
            onChange={(e) => setReturnDate(e.target.value)}
            sx={{ mt: 1.5 }}
          />
          <FormField
            label="Return notes"
            value={returnNotes}
            onChange={(e) => setReturnNotes(e.target.value)}
            multiline
            minRows={2}
            sx={{ mt: 1.5 }}
          />
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setDialog(null)}>
            Cancel
          </ProsohmButton>
          <ProsohmButton
            buttonVariant="primary"
            loading={runMutation.isPending}
            onClick={() =>
              runMutation.mutate({
                action: 'return_to_customer',
                parameters: {
                  return_date: returnDate,
                  owner_customer_id: returnCustomerId || null,
                  notes: returnNotes || null,
                },
                options: { allow_partial: true },
              })
            }
          >
            Mark as Returned
          </ProsohmButton>
        </DialogActions>
      </Dialog>

      {/* Result */}
      <Dialog open={dialog === 'result'} onClose={() => setDialog(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Bulk Update Complete</DialogTitle>
        <DialogContent>
          {result ? (
            <Stack spacing={1}>
              <Typography variant="body2">Selected: {result.selected}</Typography>
              <Typography variant="body2">Updated: {result.updated}</Typography>
              <Typography variant="body2">Skipped: {result.skipped}</Typography>
              {result.skipped_details.length > 0 ? (
                <Alert severity="warning">
                  <Box component="ul" sx={{ pl: 2, mb: 0 }}>
                    {result.skipped_details.map((row) => (
                      <li key={row.asset_number}>
                        {row.asset_number} — {row.reason}
                      </li>
                    ))}
                  </Box>
                </Alert>
              ) : null}
            </Stack>
          ) : null}
        </DialogContent>
        <DialogActions>
          <ProsohmButton
            buttonVariant="primary"
            onClick={() => {
              setDialog(null);
              setResult(null);
              onClearSelection();
            }}
          >
            Done
          </ProsohmButton>
        </DialogActions>
      </Dialog>
    </>
  );
}
