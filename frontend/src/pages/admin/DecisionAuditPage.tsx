import { useState } from 'react';
import {
  Alert,
  Box,
  Chip,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { PageHeader } from '../../components/common/PageHeader';
import { EmptyState } from '../../components/common/EmptyState';
import { ContentCard } from '../../components/ui/cards';
import { getErrorMessage } from '../../api/client';
import { fetchDecisionAudit, type DecisionAuditEntry } from '../../api/automation';

const KIND_LABELS: Record<DecisionAuditEntry['kind'], string> = {
  template_change: 'Template change',
  lifecycle: 'Milestone lifecycle',
  rule_change: 'Rule switch',
  automation: 'Automation',
};

const RESULT_COLORS: Record<string, 'default' | 'success' | 'warning' | 'error'> = {
  applied: 'success',
  success: 'success',
  succeeded: 'success',
  failed: 'error',
  pending_review: 'warning',
};

export default function DecisionAuditPage() {
  const [search, setSearch] = useState('');
  const [kind, setKind] = useState<DecisionAuditEntry['kind'] | ''>('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);

  const filters = {
    search: search.trim(),
    kind: kind || undefined,
    date_from: dateFrom,
    date_to: dateTo,
    page: page + 1,
    page_size: pageSize,
  };
  const query = useQuery({
    queryKey: ['automation', 'decision-audit', filters],
    queryFn: () => fetchDecisionAudit(filters),
    placeholderData: keepPreviousData,
  });
  const rows = query.data?.items ?? [];
  const reset = () => setPage(0);

  return (
    <Box>
      <PageHeader
        title="Decision Audit"
        subtitle="Template reconciliations, milestone lifecycle changes, automation rule switches and automation outcomes"
      />
      <ContentCard title="Decisions">
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1} sx={{ mb: 2 }}>
          <TextField size="small" label="Search" value={search} sx={{ minWidth: 220 }}
            onChange={(e) => { setSearch(e.target.value); reset(); }} />
          <TextField select size="small" label="Type" value={kind} sx={{ minWidth: 200 }}
            onChange={(e) => { setKind(e.target.value as DecisionAuditEntry['kind'] | ''); reset(); }}>
            <MenuItem value="">All</MenuItem>
            {Object.entries(KIND_LABELS).map(([value, text]) => (
              <MenuItem key={value} value={value}>{text}</MenuItem>
            ))}
          </TextField>
          <TextField size="small" type="date" label="From" value={dateFrom}
            slotProps={{ inputLabel: { shrink: true } }}
            onChange={(e) => { setDateFrom(e.target.value); reset(); }} />
          <TextField size="small" type="date" label="To" value={dateTo}
            slotProps={{ inputLabel: { shrink: true } }}
            onChange={(e) => { setDateTo(e.target.value); reset(); }} />
        </Stack>
        {query.isError ? <Alert severity="error">{getErrorMessage(query.error)}</Alert> : null}
        {!query.isLoading && rows.length === 0 ? (
          <EmptyState title="No decisions found" description="Try a wider date range or a different search." />
        ) : (
          <>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>When</TableCell>
                  <TableCell>Who</TableCell>
                  <TableCell>Decision</TableCell>
                  <TableCell>Project</TableCell>
                  <TableCell>Before → after</TableCell>
                  <TableCell>Trigger / reason</TableCell>
                  <TableCell>Result</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={`${row.kind}-${row.id}`} hover>
                    <TableCell sx={{ whiteSpace: 'nowrap' }}>{new Date(row.time).toLocaleString()}</TableCell>
                    <TableCell>{row.actor_name ?? '—'}</TableCell>
                    <TableCell>
                      <Typography variant="body2">{row.action}</Typography>
                      <Typography variant="caption" color="text.secondary">{KIND_LABELS[row.kind]}</Typography>
                    </TableCell>
                    <TableCell>{row.project_label ?? '—'}</TableCell>
                    <TableCell>
                      {row.previous_value ? (
                        <Typography variant="caption" color="text.secondary" component="div">{row.previous_value}</Typography>
                      ) : null}
                      <Typography variant="body2">{row.new_value ?? '—'}</Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption" component="div">{row.trigger ?? '—'}</Typography>
                      {row.reason ? (
                        <Typography variant="caption" color="text.secondary" component="div">{row.reason}</Typography>
                      ) : null}
                      {row.approval_reference ? (
                        <Typography variant="caption" color="text.secondary" component="div">Ref: {row.approval_reference}</Typography>
                      ) : null}
                    </TableCell>
                    <TableCell>
                      <Chip size="small" label={(row.result ?? '—').replace(/_/g, ' ')}
                        color={RESULT_COLORS[row.result ?? ''] ?? 'default'} />
                      {row.error ? (
                        <Typography variant="caption" color="error" component="div">{row.error}</Typography>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <TablePagination
              component="div"
              count={query.data?.total ?? 0}
              page={page}
              rowsPerPage={pageSize}
              rowsPerPageOptions={[25, 50, 100]}
              onPageChange={(_e, next) => setPage(next)}
              onRowsPerPageChange={(e) => { setPageSize(Number(e.target.value)); setPage(0); }}
            />
          </>
        )}
      </ContentCard>
    </Box>
  );
}
