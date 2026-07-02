import { useState } from 'react';
import {
  Box,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
} from '@mui/material';
import DeleteForeverIcon from '@mui/icons-material/DeleteForever';
import RestoreIcon from '@mui/icons-material/Restore';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { DeleteRecordDialog } from '../../components/ui/design-system/DeleteRecordDialog';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { PageHeader } from '../../components/common/PageHeader';
import { TableSkeleton } from '../../components/common/TableSkeleton';
import { ContentCard } from '../../components/ui/cards';
import { QUERY_STALE_TIMES } from '../../config/queryConfig';
import { useToast } from '../../context/ToastContext';
import {
  fetchDeletedUsers,
  fetchUserDeleteCheck,
  permanentDeleteUser,
  restoreDeletedUser,
} from '../../api/deleteCheck';
import type { DeleteCheckResult } from '../../components/ui/design-system/DeleteRecordDialog';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { formatCellValue } from '../../utils/format';

export default function DeletedUsersPage() {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [restoreId, setRestoreId] = useState<string | null>(null);
  const [permanentCheck, setPermanentCheck] = useState<DeleteCheckResult | null>(null);
  const [permanentId, setPermanentId] = useState<string | null>(null);
  const [permanentLoading, setPermanentLoading] = useState(false);

  const deletedQuery = useQuery({
    queryKey: ['users', 'deleted'],
    queryFn: fetchDeletedUsers,
    staleTime: QUERY_STALE_TIMES.projects,
  });

  const restoreMutation = useMutation({
    mutationFn: restoreDeletedUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      showSuccess('User restored');
      setRestoreId(null);
    },
    onError: (error: Error) => showError(error.message),
  });

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['users', 'deleted'] });
  };

  async function openPermanentDelete(userId: string, name: string) {
    setPermanentId(userId);
    setPermanentCheck(null);
    try {
      const check = await fetchUserDeleteCheck(userId);
      setPermanentCheck({ ...check, record_name: name });
    } catch (error) {
      showError(error instanceof Error ? error.message : 'Unable to check delete eligibility');
      setPermanentId(null);
    }
  }

  async function confirmPermanentDelete() {
    if (!permanentId || !permanentCheck?.can_delete) return;
    setPermanentLoading(true);
    try {
      await permanentDeleteUser(permanentId);
      showSuccess('User permanently deleted');
      setPermanentId(null);
      setPermanentCheck(null);
      refresh();
    } catch (error) {
      showError(error instanceof Error ? error.message : 'Delete failed');
    } finally {
      setPermanentLoading(false);
    }
  }

  if (deletedQuery.error) return <ErrorState error={deletedQuery.error} />;

  return (
    <Box>
      <PageHeader
        title="Deleted Users"
        subtitle="Admin-only recovery and permanent deletion for soft-deleted users"
      />

      {deletedQuery.isPending ? (
        <ContentCard noPadding>
          <TableSkeleton rows={6} columns={5} />
        </ContentCard>
      ) : !deletedQuery.data?.length ? (
        <EmptyState title="No deleted users" />
      ) : (
        <ContentCard noPadding>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Email</TableCell>
                  <TableCell>Role</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {deletedQuery.data.map((user) => {
                  const name = `${user.first_name} ${user.last_name}`.trim() || user.email;
                  return (
                    <TableRow key={user.id} hover>
                      <TableCell>{name}</TableCell>
                      <TableCell>{user.email}</TableCell>
                      <TableCell>{formatCellValue(user.role_name)}</TableCell>
                      <TableCell align="right">
                        <Tooltip title="Restore">
                          <IconButton size="small" onClick={() => setRestoreId(user.id)}>
                            <RestoreIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Permanent delete">
                          <IconButton
                            size="small"
                            color="error"
                            onClick={() => void openPermanentDelete(user.id, name)}
                          >
                            <DeleteForeverIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        </ContentCard>
      )}

      <ConfirmDialog
        open={restoreId !== null}
        title="Restore deleted user?"
        message="The user account will be visible again in normal user lists."
        confirmLabel="Restore"
        loading={restoreMutation.isPending}
        onClose={() => setRestoreId(null)}
        onConfirm={() => restoreId && restoreMutation.mutate(restoreId)}
      />

      <DeleteRecordDialog
        open={permanentId !== null}
        check={permanentCheck}
        loading={permanentLoading}
        onClose={() => {
          setPermanentId(null);
          setPermanentCheck(null);
        }}
        onConfirm={() => void confirmPermanentDelete()}
        showDeactivate={false}
      />
    </Box>
  );
}
