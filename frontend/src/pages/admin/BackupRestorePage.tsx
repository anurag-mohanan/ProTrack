import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Box, List, ListItem, ListItemText, Stack, Typography } from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { LoadingState } from '../../components/common/LoadingState';
import { createBackup, fetchBackups, restoreBackup } from '../../api/system';
import { useToast } from '../../context/ToastContext';

export default function BackupRestorePage() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ['system', 'backups'], queryFn: fetchBackups });

  const backupMutation = useMutation({
    mutationFn: createBackup,
    onSuccess: () => {
      showSuccess('Backup created');
      void queryClient.invalidateQueries({ queryKey: ['system', 'backups'] });
    },
    onError: (error: Error) => showError(error.message),
  });

  const restoreMutation = useMutation({
    mutationFn: restoreBackup,
    onSuccess: () => showSuccess('Database restored. Restart the application if needed.'),
    onError: (error: Error) => showError(error.message),
  });

  if (query.isLoading) return <LoadingState message="Loading backups…" />;

  return (
    <Box>
      <PageHeader title="Backup & Restore" subtitle="Create and restore SQLite database backups" />
      <Stack spacing={2}>
        <ContentCard title="Create backup">
          <ProsohmButton onClick={() => backupMutation.mutate()} loading={backupMutation.isPending}>
            Create Backup Now
          </ProsohmButton>
        </ContentCard>
        <ContentCard title="Available backups">
          <List dense>
            {(query.data ?? []).map((backup) => (
              <ListItem
                key={backup.filename}
                secondaryAction={
                  <ProsohmButton
                size="small"
                buttonVariant="outlined"
                onClick={() => restoreMutation.mutate(backup.filename)}
                loading={restoreMutation.isPending}
              >
                    Restore
                  </ProsohmButton>
                }
              >
                <ListItemText
                  primary={backup.filename}
                  secondary={`${backup.modified_at} · ${Number(backup.size_bytes).toLocaleString()} bytes`}
                />
              </ListItem>
            ))}
            {(query.data ?? []).length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
                No backups yet.
              </Typography>
            ) : null}
          </List>
        </ContentCard>
      </Stack>
    </Box>
  );
}
