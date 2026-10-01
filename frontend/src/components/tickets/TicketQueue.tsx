import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Box,
  Button,
  Chip,
  Drawer,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import FileDownloadRoundedIcon from '@mui/icons-material/FileDownloadRounded';
import { ticketsApi } from '../../api/tickets';
import { EmptyState } from '../common/EmptyState';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { useToast } from '../../context/ToastContext';
import { formatDate, formatDateTime } from '../../utils/format';
import type { TicketQueueParams } from '../../types/tickets';
import { DUE_FILTERS, PRIORITY_COLOR, STATUS_COLOR, type QueueView } from './ticketConstants';
import { TicketDetailView } from './TicketDetailView';
import { useTicketAssignees, useTicketCapabilities, useTicketCatalog } from './useTicketMeta';

const FILTER_KEYS = [
  'view',
  'status',
  'category',
  'family',
  'priority',
  'assignee',
  'source_module',
  'due',
  'created_from',
  'created_to',
  'q',
  'sort',
] as const;

interface TicketQueueProps {
  views: readonly QueueView[];
  defaultView: string;
  /** Locks the queue to one category (e.g. the IT workspace). */
  category?: string;
  emptyHint?: string;
}

/** Paginated, URL-driven ticket list shared by the Help Desk and the IT workspace. */
export function TicketQueue({ views, defaultView, category, emptyHint }: TicketQueueProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const { showError } = useToast();
  const catalog = useTicketCatalog();
  const capabilities = useTicketCapabilities();
  const isAgent = Boolean(capabilities.data?.is_agent);
  const assignees = useTicketAssignees(category, isAgent);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [searchText, setSearchText] = useState(searchParams.get('q') ?? '');
  const openTicketId = searchParams.get('ticket');

  const params = useMemo<TicketQueueParams>(() => {
    const result: Record<string, string> = {};
    FILTER_KEYS.forEach((key) => {
      const value = searchParams.get(key);
      if (value) result[key] = value;
    });
    const view = result.view ?? defaultView;
    if (view === 'all') delete result.view;
    else result.view = view;
    if (category) result.category = category;
    return result;
  }, [searchParams, defaultView, category]);

  const query = useQuery({
    queryKey: ['tickets', 'queue', params, page, pageSize],
    queryFn: () => ticketsApi.queue({ ...params, page: page + 1, page_size: pageSize }),
    placeholderData: keepPreviousData,
  });

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    next.delete('ticket');
    setSearchParams(next, { replace: true });
    setPage(0);
  };

  const openTicket = (id: string | null) => {
    const next = new URLSearchParams(searchParams);
    if (id) next.set('ticket', id);
    else next.delete('ticket');
    setSearchParams(next, { replace: !id });
  };

  const clearFilters = () => {
    const next = new URLSearchParams();
    setSearchParams(next, { replace: true });
    setSearchText('');
    setPage(0);
  };

  const exportCsv = async () => {
    try {
      const blob = await ticketsApi.exportCsv(params);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'tickets.csv';
      anchor.click();
      URL.revokeObjectURL(url);
    } catch {
      showError('Could not export the tickets.');
    }
  };

  const currentView = searchParams.get('view') ?? defaultView;
  const subcategoryFamilies = catalog.data?.families ?? {};
  const statusOptions: [string, string][] = [
    ['', 'Any status'],
    ['active', 'All active'],
    ['waiting', 'Waiting (any)'],
    ...(catalog.data?.status_order ?? [])
      .filter((value) => value !== 'on_hold')
      .map((value): [string, string] => [value, catalog.data?.statuses[value] ?? value]),
  ];
  const data = query.data;
  const hasFilters = FILTER_KEYS.some((key) => key !== 'view' && searchParams.get(key));

  return (
    <Box>
      <Paper variant="outlined" sx={{ p: 1.5, mb: 2 }}>
        <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1.5, alignItems: 'center' }}>
          <TextField
            select
            size="small"
            label="View"
            value={currentView}
            onChange={(event) => setFilter('view', event.target.value === defaultView ? '' : event.target.value)}
            sx={{ minWidth: 170 }}
          >
            {views.map((view) => (
              <MenuItem key={view.value} value={view.value}>
                {view.label}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            size="small"
            label="Search"
            placeholder="Ticket #, title, employee, email, asset…"
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') setFilter('q', searchText.trim());
            }}
            onBlur={() => {
              if ((searchParams.get('q') ?? '') !== searchText.trim()) setFilter('q', searchText.trim());
            }}
            sx={{ minWidth: 240, flexGrow: 1 }}
          />
          <TextField
            select
            size="small"
            label="Status"
            value={searchParams.get('status') ?? ''}
            onChange={(event) => setFilter('status', event.target.value)}
            sx={{ minWidth: 150 }}
          >
            {statusOptions.map(([value, label]) => (
              <MenuItem key={value || 'any'} value={value}>
                {label}
              </MenuItem>
            ))}
          </TextField>
          {!category ? (
            <TextField
              select
              size="small"
              label="Category"
              value={searchParams.get('category') ?? ''}
              onChange={(event) => setFilter('category', event.target.value)}
              sx={{ minWidth: 160 }}
            >
              <MenuItem value="">All categories</MenuItem>
              {Object.entries(catalog.data?.categories ?? {}).map(([value, label]) => (
                <MenuItem key={value} value={value}>
                  {label}
                </MenuItem>
              ))}
            </TextField>
          ) : (
            <TextField
              select
              size="small"
              label="Type"
              value={searchParams.get('family') ?? ''}
              onChange={(event) => setFilter('family', event.target.value)}
              sx={{ minWidth: 150 }}
            >
              <MenuItem value="">All types</MenuItem>
              {Object.entries(subcategoryFamilies).map(([value, label]) => (
                <MenuItem key={value} value={value}>
                  {label}
                </MenuItem>
              ))}
            </TextField>
          )}
          <TextField
            select
            size="small"
            label="Priority"
            value={searchParams.get('priority') ?? ''}
            onChange={(event) => setFilter('priority', event.target.value)}
            sx={{ minWidth: 130 }}
          >
            <MenuItem value="">Any priority</MenuItem>
            {Object.entries(catalog.data?.priorities ?? {}).map(([value, label]) => (
              <MenuItem key={value} value={value}>
                {label}
              </MenuItem>
            ))}
          </TextField>
          {isAgent ? (
            <TextField
              select
              size="small"
              label="Owner"
              value={searchParams.get('assignee') ?? ''}
              onChange={(event) => setFilter('assignee', event.target.value)}
              sx={{ minWidth: 150 }}
            >
              <MenuItem value="">Anyone</MenuItem>
              <MenuItem value="me">Me</MenuItem>
              <MenuItem value="none">Unassigned</MenuItem>
              {(assignees.data ?? []).map((row) => (
                <MenuItem key={row.id} value={row.id}>
                  {row.name}
                </MenuItem>
              ))}
            </TextField>
          ) : null}
          <TextField
            select
            size="small"
            label="Source"
            value={searchParams.get('source_module') ?? ''}
            onChange={(event) => setFilter('source_module', event.target.value)}
            sx={{ minWidth: 150 }}
          >
            <MenuItem value="">Any source</MenuItem>
            {Object.entries(catalog.data?.sources ?? {}).map(([value, label]) => (
              <MenuItem key={value} value={value}>
                {label}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            select
            size="small"
            label="Due"
            value={searchParams.get('due') ?? ''}
            onChange={(event) => setFilter('due', event.target.value)}
            sx={{ minWidth: 150 }}
          >
            {DUE_FILTERS.map((row) => (
              <MenuItem key={row.value || 'any'} value={row.value}>
                {row.label}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            size="small"
            type="date"
            label="Created from"
            value={searchParams.get('created_from') ?? ''}
            onChange={(event) => setFilter('created_from', event.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <TextField
            size="small"
            type="date"
            label="Created to"
            value={searchParams.get('created_to') ?? ''}
            onChange={(event) => setFilter('created_to', event.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <TextField
            select
            size="small"
            label="Sort"
            value={searchParams.get('sort') ?? ''}
            onChange={(event) => setFilter('sort', event.target.value)}
            sx={{ minWidth: 140 }}
          >
            <MenuItem value="">Newest first</MenuItem>
            <MenuItem value="updated">Recently updated</MenuItem>
            <MenuItem value="due">Due date</MenuItem>
            <MenuItem value="priority">Priority</MenuItem>
          </TextField>
          {hasFilters ? (
            <Button size="small" onClick={clearFilters}>
              Clear filters
            </Button>
          ) : null}
          {isAgent ? (
            <Button size="small" startIcon={<FileDownloadRoundedIcon />} onClick={exportCsv} sx={{ ml: 'auto' }}>
              Export CSV
            </Button>
          ) : null}
        </Stack>
      </Paper>

      {query.isLoading ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => query.refetch()} />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          title="No tickets match"
          description={emptyHint ?? 'Change the view or filters to see other tickets.'}
        />
      ) : (
        <Paper variant="outlined">
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Ticket</TableCell>
                  <TableCell>Request</TableCell>
                  <TableCell>Requester / employee</TableCell>
                  <TableCell>Owner</TableCell>
                  <TableCell>Priority</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Due</TableCell>
                  <TableCell>Updated</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.items.map((ticket) => (
                  <TableRow
                    key={ticket.id}
                    hover
                    selected={ticket.id === openTicketId}
                    onClick={() => openTicket(ticket.id)}
                    sx={{ cursor: 'pointer' }}
                  >
                    <TableCell sx={{ whiteSpace: 'nowrap', fontWeight: 700 }}>{ticket.ticket_number}</TableCell>
                    <TableCell sx={{ maxWidth: 360 }}>
                      <Typography variant="body2" noWrap title={ticket.title} sx={{ fontWeight: 600 }}>
                        {ticket.title}
                      </Typography>
                      <Typography variant="caption" color="text.secondary" noWrap component="div">
                        {category ? '' : `${ticket.category_label} · `}
                        {ticket.subcategory_label ?? 'General'}
                        {ticket.source_label ? ` · ${ticket.source_label}` : ''}
                      </Typography>
                    </TableCell>
                    <TableCell sx={{ maxWidth: 220 }}>
                      <Typography variant="body2" noWrap>
                        {ticket.requester_name ?? '—'}
                      </Typography>
                      {ticket.affected_user_name && ticket.affected_user_name !== ticket.requester_name ? (
                        <Typography variant="caption" color="text.secondary" noWrap component="div">
                          for {ticket.affected_user_name}
                        </Typography>
                      ) : null}
                    </TableCell>
                    <TableCell>
                      {ticket.assignee_name ?? (
                        <Chip
                          label={ticket.needs_owner ? 'Needs owner' : 'Unassigned'}
                          size="small"
                          color="warning"
                          variant="outlined"
                        />
                      )}
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={ticket.priority_label}
                        size="small"
                        color={PRIORITY_COLOR[ticket.priority]}
                        variant={ticket.priority === 'low' ? 'outlined' : 'filled'}
                      />
                    </TableCell>
                    <TableCell>
                      <Stack direction="row" spacing={0.5}>
                        <Chip label={ticket.status_label} size="small" color={STATUS_COLOR[ticket.status]} />
                        {ticket.needs_review ? <Chip label="Review" size="small" variant="outlined" /> : null}
                      </Stack>
                    </TableCell>
                    <TableCell sx={{ whiteSpace: 'nowrap', color: ticket.is_overdue ? 'error.main' : undefined }}>
                      {ticket.due_date
                        ? formatDate(ticket.due_date)
                        : ticket.sla_due_at
                          ? formatDateTime(ticket.sla_due_at)
                          : '—'}
                      {ticket.is_overdue ? ' · overdue' : ''}
                    </TableCell>
                    <TableCell sx={{ whiteSpace: 'nowrap' }}>{formatDateTime(ticket.updated_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          <TablePagination
            component="div"
            count={data.total}
            page={page}
            onPageChange={(_, next) => setPage(next)}
            rowsPerPage={pageSize}
            onRowsPerPageChange={(event) => {
              setPageSize(Number(event.target.value));
              setPage(0);
            }}
            rowsPerPageOptions={[10, 25, 50, 100]}
          />
        </Paper>
      )}

      <Drawer
        anchor="right"
        open={Boolean(openTicketId)}
        onClose={() => openTicket(null)}
        slotProps={{ paper: { sx: { width: { xs: '100%', sm: 640 }, p: 2 } } }}
      >
        {openTicketId ? <TicketDetailView ticketId={openTicketId} onClose={() => openTicket(null)} /> : null}
      </Drawer>
    </Box>
  );
}
