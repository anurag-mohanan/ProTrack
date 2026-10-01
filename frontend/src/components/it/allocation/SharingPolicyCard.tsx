import { Chip, Switch, Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchSharingPolicy, itAllocationKeys, updateSharingPolicy } from '../../../api/itAllocation';
import { getErrorMessage } from '../../../api/client';
import { itInventoryKeys } from '../../../api/itInventory';
import { useToast } from '../../../context/ToastContext';
import type { SharingPolicyRow } from '../../../types/itAllocation';
import { ErrorState } from '../../common/ErrorState';
import { LoadingState } from '../../common/LoadingState';
import { ContentCard } from '../../ui/cards';

/** Per asset type: may it be shared across non-overlapping shifts, and must assignments name a shift? */
export function SharingPolicyCard({ canEdit }: { canEdit: boolean }) {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const query = useQuery({ queryKey: itAllocationKeys.sharingPolicy(), queryFn: fetchSharingPolicy });

  const mutation = useMutation({
    mutationFn: ({ row, patch }: { row: SharingPolicyRow; patch: { is_shareable?: boolean; requires_shift?: boolean } }) =>
      updateSharingPolicy(row.asset_type_id, patch),
    onSuccess: (row) => {
      showSuccess(`Sharing policy for ${row.name} saved.`);
      void queryClient.invalidateQueries({ queryKey: itAllocationKeys.all });
      void queryClient.invalidateQueries({ queryKey: itInventoryKeys.all });
    },
    onError: (err) => showError(getErrorMessage(err)),
  });

  return (
    <ContentCard
      title="Resource sharing policy"
      subtitle="Shareable resources can be assigned to several employees whose shifts or time windows do not overlap. Exclusive resources hold one user at a time."
    >
      {query.isLoading ? (
        <LoadingState message="Loading sharing policy…" />
      ) : query.isError ? (
        <ErrorState error={query.error} title="Unable to load the sharing policy" onRetry={() => void query.refetch()} />
      ) : (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Asset type</TableCell>
              <TableCell>Role</TableCell>
              <TableCell>Shareable by shift</TableCell>
              <TableCell>Shift required</TableCell>
              <TableCell>Source</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(query.data ?? [])
              .filter((row) => row.is_active)
              .map((row) => (
                <TableRow key={row.asset_type_id}>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {row.name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {row.code}
                    </Typography>
                  </TableCell>
                  <TableCell>{row.role_label}</TableCell>
                  <TableCell>
                    <Switch
                      size="small"
                      checked={row.shareable}
                      disabled={!canEdit || mutation.isPending}
                      onChange={(e) => mutation.mutate({ row, patch: { is_shareable: e.target.checked } })}
                      slotProps={{ input: { 'aria-label': `${row.name} shareable` } }}
                    />
                  </TableCell>
                  <TableCell>
                    <Switch
                      size="small"
                      checked={row.requires_shift}
                      disabled={!canEdit || mutation.isPending}
                      onChange={(e) => mutation.mutate({ row, patch: { requires_shift: e.target.checked } })}
                      slotProps={{ input: { 'aria-label': `${row.name} requires shift` } }}
                    />
                  </TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      variant="outlined"
                      label={row.configured ? 'Configured' : 'Default for role'}
                      color={row.configured ? 'primary' : 'default'}
                    />
                  </TableCell>
                </TableRow>
              ))}
          </TableBody>
        </Table>
      )}
    </ContentCard>
  );
}
