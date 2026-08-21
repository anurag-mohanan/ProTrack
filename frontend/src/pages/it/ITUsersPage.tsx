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
import { useQuery } from '@tanstack/react-query';
import {
  fetchItPeoplePaginated,
  fetchItPerson,
  itOperationsKeys,
} from '../../api/itOperations';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ServerPaginatedDataGrid } from '../../components/common/ServerPaginatedDataGrid';
import { ContentCard } from '../../components/ui/cards';
import { FormSelect, SearchToolbar, FormField } from '../../components/ui/design-system';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { formatCellValue } from '../../utils/format';
import type { ITPersonListItem } from '../../types/itOperations';

const STATUS_OPTIONS = [
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
  { value: 'former', label: 'Former' },
  { value: 'all', label: 'All' },
];

export function ITUsersPage() {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('active');
  const [selectedId, setSelectedId] = useState<string | null>(null);

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
      <PageHeader subtitle="IT Users reflect ProTrack employees/resources — not a separate employee database." />

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
          <ProsohmButton buttonVariant="outlined" onClick={() => setSelectedId(null)}>
            Close
          </ProsohmButton>
        </DialogActions>
      </Dialog>
    </PageContainer>
  );
}
