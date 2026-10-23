import { useMemo, useState } from 'react';
import {
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  Typography,
  Box,
} from '@mui/material';
import type { GridColDef } from '@mui/x-data-grid';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import {
  fetchItPeoplePaginated,
  fetchItPerson,
  itOperationsKeys,
  returnAssetsForPerson,
} from '../../api/itOperations';
import { getErrorMessage } from '../../api/client';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ITAreaTabs } from '../../components/it/ITAreaTabs';
import { IT_ASSET_AREA_TABS } from '../../components/it/itAreaTabConfig';
import { ServerPaginatedDataGrid } from '../../components/common/ServerPaginatedDataGrid';
import { ContentCard } from '../../components/ui/cards';
import { FormSelect, SearchToolbar, FormField } from '../../components/ui/design-system';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { useToast } from '../../context/ToastContext';
import { formatCellValue } from '../../utils/format';
import type { ITPersonListItem } from '../../types/itOperations';

const STATUS_OPTIONS = [
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
  { value: 'former', label: 'Former' },
  { value: 'all', label: 'All' },
];

export function ITUsersPage() {
  const [searchParams] = useSearchParams();
  const [search, setSearch] = useState(() => searchParams.get('search') ?? '');
  const [status, setStatus] = useState(() => searchParams.get('status') ?? 'active');
  const [selectedId, setSelectedId] = useState<string | null>(() => searchParams.get('user'));
  const [confirmReturn, setConfirmReturn] = useState(false);
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();

  const listFilters = useMemo(
    () => ({
      search: search.trim() || undefined,
      status,
    }),
    [search, status],
  );

  const detailQuery = useQuery({
    queryKey: itOperationsKeys.person(selectedId ?? ''),
    queryFn: () => fetchItPerson(selectedId!),
    enabled: Boolean(selectedId),
  });

  const returnMutation = useMutation({
    mutationFn: () =>
      returnAssetsForPerson(selectedId!, {
        notes: 'Returned on employee exit',
      }),
    onSuccess: (rows) => {
      showSuccess(
        rows.length
          ? `Returned ${rows.length} asset assignment(s).`
          : 'No open asset assignments to return.',
      );
      setConfirmReturn(false);
      void queryClient.invalidateQueries({ queryKey: itOperationsKeys.person(selectedId ?? '') });
      void queryClient.invalidateQueries({ queryKey: itOperationsKeys.people() });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const columns: GridColDef<ITPersonListItem>[] = [
    {
      field: 'full_name',
      headerName: 'Employee',
      flex: 1.2,
      minWidth: 160,
    },
    {
      field: 'department',
      headerName: 'Department',
      flex: 1,
      minWidth: 120,
      valueFormatter: (value) => formatCellValue(value),
    },
    {
      field: 'team',
      headerName: 'Team',
      flex: 1,
      minWidth: 110,
      valueFormatter: (value) => formatCellValue(value),
    },
    {
      field: 'designation',
      headerName: 'Designation',
      flex: 1,
      minWidth: 120,
      valueFormatter: (value) => formatCellValue(value),
    },
    {
      field: 'employment_status',
      headerName: 'Status',
      width: 110,
      renderCell: ({ row }) => (
        <Chip
          size="small"
          label={row.employment_status}
          color={row.employment_status === 'active' ? 'success' : 'default'}
        />
      ),
    },
    {
      field: 'assigned_computer_name',
      headerName: 'Computer',
      flex: 1,
      minWidth: 130,
      valueFormatter: (value) => formatCellValue(value) || '—',
    },
    {
      field: 'computer_status',
      headerName: 'PC status',
      width: 110,
      valueFormatter: (value) => formatCellValue(value) || '—',
    },
    {
      field: 'it_account_count',
      headerName: 'IT accounts',
      width: 110,
    },
  ];

  const detail = detailQuery.data;

  return (
    <PageContainer>
      <PageHeader
        title="People"
        subtitle="ProTrack employees and their assigned computers. This is the User master — not a separate employee database, and not a top-level IT hub."
      />
      <ITAreaTabs items={IT_ASSET_AREA_TABS} />

      <SearchToolbar sticky>
        <FormSelect
          label="Status"
          value={status}
          onChange={(e) => setStatus(String(e.target.value))}
          options={STATUS_OPTIONS}
          sx={{ minWidth: 140 }}
        />
        <FormField
          label="Search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Name, email, team, computer…"
          sx={{ minWidth: 240, flex: 1, maxWidth: 420 }}
        />
      </SearchToolbar>

      <ContentCard title="Users & Accounts" noPadding>
        <ServerPaginatedDataGrid<ITPersonListItem, ITPersonListItem>
          queryKey={itOperationsKeys.people(listFilters)}
          fetcher={fetchItPeoplePaginated}
          filters={listFilters}
          columns={columns}
          getRowId={(row) => row.user_id}
          onRowClick={(params) => setSelectedId(String(params.id))}
          autoHeight
        />
      </ContentCard>

      <Dialog open={Boolean(selectedId)} onClose={() => setSelectedId(null)} maxWidth="sm" fullWidth>
        <DialogTitle>{detail?.full_name ?? 'Employee IT profile'}</DialogTitle>
        <DialogContent>
          {detailQuery.isLoading && <Typography>Loading…</Typography>}
          {detail && (
            <Stack spacing={2} sx={{ pt: 1 }}>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  Department / Team / Designation
                </Typography>
                <Typography>
                  {formatCellValue(detail.department)} · {formatCellValue(detail.team)} ·{' '}
                  {formatCellValue(detail.designation)}
                </Typography>
              </Box>
              <Box>
                <Typography sx={{ fontWeight: 600 }}>Computer</Typography>
                {detail.assigned_computer ? (
                  <Typography>
                    {String(detail.assigned_computer.computer_name ?? '')} (
                    {String(detail.assigned_computer.asset_number ?? '')}) —{' '}
                    {String(detail.assigned_computer.status ?? '')}
                  </Typography>
                ) : (
                  <Typography color="text.secondary">No computer assigned</Typography>
                )}
              </Box>
              <Box>
                <Typography sx={{ fontWeight: 600 }}>Other assets</Typography>
                {detail.assigned_assets.filter((a) => !a.is_computer).length === 0 ? (
                  <Typography color="text.secondary">None</Typography>
                ) : (
                  detail.assigned_assets
                    .filter((a) => !a.is_computer)
                    .map((a) => (
                      <Typography key={String(a.asset_id)}>
                        {String(a.asset_number)} — {String(a.status)}
                      </Typography>
                    ))
                )}
              </Box>
              <Box>
                <Typography sx={{ fontWeight: 600 }}>IT accounts</Typography>
                {detail.accounts.length === 0 ? (
                  <Typography color="text.secondary">No IT account metadata yet</Typography>
                ) : (
                  detail.accounts.map((a) => (
                    <Typography key={String(a.id)}>
                      {String(a.account_type)}: {String(a.username ?? '—')} (
                      {String(a.credential_status)})
                    </Typography>
                  ))
                )}
              </Box>
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          {detail && (detail.assigned_assets?.length ?? 0) > 0 ? (
            <ProsohmButton
              buttonVariant="secondary"
              onClick={() => setConfirmReturn(true)}
              disabled={returnMutation.isPending}
            >
              Return all assets
            </ProsohmButton>
          ) : null}
          <ProsohmButton buttonVariant="outlined" onClick={() => setSelectedId(null)}>
            Close
          </ProsohmButton>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={confirmReturn}
        title="Return all assets?"
        message={
          detail
            ? `Return every open assignment for ${detail.full_name}? Use this when completing an employee exit.`
            : 'Return every open assignment for this employee?'
        }
        confirmLabel="Return assets"
        onClose={() => setConfirmReturn(false)}
        onConfirm={() => returnMutation.mutate()}
        loading={returnMutation.isPending}
      />
    </PageContainer>
  );
}
