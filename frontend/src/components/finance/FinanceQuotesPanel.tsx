import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  Checkbox,
  FormControl,
  FormControlLabel,
  Grid,
  InputAdornment,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import CalendarMonthOutlinedIcon from '@mui/icons-material/CalendarMonthOutlined';
import ReceiptLongOutlinedIcon from '@mui/icons-material/ReceiptLongOutlined';
import RequestQuoteOutlinedIcon from '@mui/icons-material/RequestQuoteOutlined';
import SearchOutlinedIcon from '@mui/icons-material/SearchOutlined';
import TrendingUpOutlinedIcon from '@mui/icons-material/TrendingUpOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { fetchCustomers, fetchTeams } from '../../api/lookups';
import {
  IMPORT_ACCEPT_WITH_CSV,
  IMPORT_FORMAT_LABEL_WITH_CSV,
} from '../../config/importFormats';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { LoadingState } from '../common/LoadingState';
import { useToast } from '../../context/ToastContext';
import { apiErrorMessage } from '../../utils/apiErrorMessage';
import { toFiniteNumber } from '../../utils/format';
import { KpiMetricCard } from '../ui/design-system/KpiMetricCard';
import { teamQueryParam } from './FinanceTeamFilter';
import {
  FinanceHeroBanner,
  FinanceSection,
  financeListRowSx,
  financeMoney,
} from './FinanceCockpitPrimitives';
import { FinanceQuotesTable } from './FinanceQuotesTable';

type QuoteRow = {
  id: string;
  customer_id: string;
  tool_number: string;
  external_quote_number?: string | null;
  currency_code: string;
  current_revision: string;
  team_id?: string | null;
  team_name?: string | null;
  customer_name?: string | null;
  project_linked?: boolean;
  quoted_hours?: number | string | null;
  quoted_revenue?: number | string | null;
  base_quoted_revenue_inr?: number | string | null;
  fx_rate?: number | string | null;
  fx_date?: string | null;
  quoted_date?: string | null;
  invoiced_date?: string | null;
  is_invoiced?: boolean;
};

type QuoteImportItem = {
  quote_id: string;
  tool_number: string;
  external_quote_number?: string | null;
  customer_name?: string | null;
  team_name?: string | null;
  quoted_hours?: number | string | null;
  quoted_revenue?: number | string | null;
  currency_code?: string | null;
  project_linked?: boolean;
  project_created?: boolean;
  warnings?: string[];
};

type QuoteImportResult = {
  imported_count: number;
  items?: QuoteImportItem[];
};

type ManualQuoteForm = {
  customerId: string;
  quoteNumber: string;
  projectNumber: string;
  cost: string;
  currencyCode: string;
  quotedDate: string;
  isInvoiced: 'yes' | 'no';
  invoicedDate: string;
};

type ListFilter = 'all' | 'not_invoiced' | 'missing_date' | 'unlinked' | 'invoiced';

const emptyManual: ManualQuoteForm = {
  customerId: '',
  quoteNumber: '',
  projectNumber: '',
  cost: '',
  currencyCode: '',
  quotedDate: new Date().toISOString().slice(0, 10),
  isInvoiced: 'no',
  invoicedDate: '',
};

function quoteSearchBlob(quote: QuoteRow): string {
  return [
    quote.external_quote_number,
    quote.tool_number,
    quote.customer_name,
    quote.team_name,
    quote.currency_code,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
}

export function FinanceQuotesPanel({ teamId }: { teamId: string }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const formRef = useRef<HTMLDivElement | null>(null);
  const [importTeamId, setImportTeamId] = useState(teamId);
  const [createProject, setCreateProject] = useState(true);
  const [manual, setManual] = useState<ManualQuoteForm>(emptyManual);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<QuoteRow | null>(null);
  const [lastImport, setLastImport] = useState<QuoteImportItem[]>([]);
  const [listFilter, setListFilter] = useState<ListFilter>('all');
  const [search, setSearch] = useState('');

  useEffect(() => {
    if (teamId && !editingId) setImportTeamId(teamId);
  }, [teamId, editingId]);

  const teamsQuery = useQuery({
    queryKey: ['lookup-teams'],
    queryFn: fetchTeams,
  });
  const customersQuery = useQuery({
    queryKey: ['lookup-customers'],
    queryFn: fetchCustomers,
  });
  const currenciesQuery = useQuery({
    queryKey: ['finance-currencies'],
    queryFn: async () =>
      (await apiClient.get<Array<{ code: string; name: string }>>('/finance/currencies')).data,
  });
  const listQ = teamQueryParam(teamId);
  const quotesQuery = useQuery({
    queryKey: ['finance-quotes', teamId || 'all'],
    queryFn: async () => (await apiClient.get<QuoteRow[]>(`/finance/quotes${listQ}`)).data,
  });

  const invalidateFinance = () => {
    void queryClient.invalidateQueries({ queryKey: ['finance-quotes'] });
    void queryClient.invalidateQueries({ queryKey: ['finance-dashboard'] });
    void queryClient.invalidateQueries({ queryKey: ['projects'] });
  };

  const applyImportResult = (data: QuoteImportResult, successLabel: string) => {
    setLastImport(data.items ?? []);
    const created = (data.items ?? []).filter((item) => item.project_created).length;
    const linked = (data.items ?? []).filter((item) => item.project_linked).length;
    showSuccess(
      `${successLabel}: ${data.imported_count}` +
        (created ? ` · ${created} project(s) created` : '') +
        (linked && !created ? ` · ${linked} linked` : ''),
    );
    invalidateFinance();
  };

  const buildPayload = () => {
    if (!importTeamId) throw new Error('Select a team.');
    if (!manual.customerId) throw new Error('Select a customer.');
    const projectNumber = manual.projectNumber.trim();
    if (!projectNumber) throw new Error('Project # is required.');
    const costRaw = manual.cost.trim().replace(/,/g, '');
    if (!costRaw) throw new Error('Cost (quoted amount) is required.');
    const cost = Number(costRaw);
    if (!Number.isFinite(cost) || cost < 0) {
      throw new Error('Cost must be a valid number.');
    }
    const currency =
      manual.currencyCode.trim().toUpperCase() ||
      customersQuery.data?.find((c) => c.id === manual.customerId)?.default_currency_code ||
      undefined;
    return {
      team_id: importTeamId,
      customer_id: manual.customerId,
      tool_number: projectNumber,
      quoted_revenue: cost,
      external_quote_number: manual.quoteNumber.trim() || null,
      currency_code: currency || null,
      quoted_date: manual.quotedDate.trim() || null,
      ...(editingId
        ? {
            is_invoiced: manual.isInvoiced === 'yes',
            ...(manual.isInvoiced === 'yes'
              ? { invoiced_date: manual.invoicedDate.trim() || null }
              : {}),
          }
        : {}),
      create_project: createProject,
    };
  };

  const cancelEdit = () => {
    setEditingId(null);
    setManual(emptyManual);
    if (teamId) setImportTeamId(teamId);
  };

  const startEdit = (quote: QuoteRow) => {
    setEditingId(quote.id);
    setImportTeamId(quote.team_id || teamId || '');
    setManual({
      customerId: quote.customer_id,
      quoteNumber: quote.external_quote_number ?? '',
      projectNumber: quote.tool_number ?? '',
      cost:
        quote.quoted_revenue === null || quote.quoted_revenue === undefined
          ? ''
          : String(quote.quoted_revenue),
      currencyCode: (quote.currency_code || '').toUpperCase(),
      quotedDate: quote.quoted_date ?? new Date().toISOString().slice(0, 10),
      isInvoiced: quote.is_invoiced ? 'yes' : 'no',
      invoicedDate: quote.invoiced_date ?? '',
    });
    window.requestAnimationFrame(() => {
      formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  };

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = buildPayload();
      if (editingId) {
        return (await apiClient.patch<QuoteRow>(`/finance/quotes/${editingId}`, payload)).data;
      }
      return (
        await apiClient.post<QuoteImportResult>('/finance/quotes/manual', payload)
      ).data;
    },
    onSuccess: (data) => {
      if (editingId) {
        showSuccess('Quote updated');
        cancelEdit();
        invalidateFinance();
        return;
      }
      applyImportResult(data as QuoteImportResult, 'Saved awarded quote');
      setManual((prev) => ({
        ...emptyManual,
        customerId: prev.customerId,
        currencyCode: prev.currencyCode,
      }));
    },
    onError: (error: unknown) => {
      showError(apiErrorMessage(error, editingId ? 'Could not update quote' : 'Could not save quote'));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/finance/quotes/${id}`);
    },
    onSuccess: () => {
      showSuccess('Quote deleted');
      setDeleteTarget(null);
      if (editingId && deleteTarget?.id === editingId) {
        cancelEdit();
      }
      invalidateFinance();
    },
    onError: (error: unknown) => {
      showError(apiErrorMessage(error, 'Could not delete quote'));
    },
  });

  const importMutation = useMutation({
    mutationFn: async (file: File) => {
      if (!importTeamId) {
        throw new Error('Select a team for this upload.');
      }
      const form = new FormData();
      form.append('file', file);
      form.append('team_id', importTeamId);
      form.append('create_project', createProject ? 'true' : 'false');
      return (await apiClient.post<QuoteImportResult>('/finance/quotes/import', form)).data;
    },
    onSuccess: (data) => {
      applyImportResult(data, 'Imported awarded quote(s)');
    },
    onError: (error: unknown) => {
      showError(apiErrorMessage(error, 'Quote import failed'));
    },
  });

  const teams = teamsQuery.data ?? [];
  const customers = useMemo(
    () => (customersQuery.data ?? []).filter((c) => c.is_active),
    [customersQuery.data],
  );
  const currencyOptions = useMemo(() => {
    const rows = currenciesQuery.data ?? [];
    if (rows.length > 0) return rows;
    return [
      { code: 'INR', name: 'Indian Rupee' },
      { code: 'USD', name: 'US Dollar' },
      { code: 'EUR', name: 'Euro' },
    ];
  }, [currenciesQuery.data]);

  const quotes = quotesQuery.data ?? [];
  const quoteStats = useMemo(() => {
    const invoicedRevenue = quotes
      .filter((q) => q.is_invoiced)
      .reduce((s, q) => s + toFiniteNumber(q.base_quoted_revenue_inr), 0);
    const missingDate = quotes.filter((q) => !q.quoted_date).length;
    const notInvoiced = quotes.filter((q) => !q.is_invoiced).length;
    const currencies = new Set(
      quotes.map((q) => (q.currency_code || 'INR').toUpperCase()).filter(Boolean),
    );
    return {
      count: quotes.length,
      invoicedRevenue,
      missingDate,
      notInvoiced,
      mixedFx: currencies.size > 1,
      currencyCount: currencies.size,
    };
  }, [quotes]);

  const filteredQuotes = useMemo(() => {
    const q = search.trim().toLowerCase();
    return quotes.filter((quote) => {
      if (listFilter === 'not_invoiced' && quote.is_invoiced) return false;
      if (listFilter === 'invoiced' && !quote.is_invoiced) return false;
      if (listFilter === 'missing_date' && quote.quoted_date) return false;
      if (listFilter === 'unlinked' && quote.project_linked) return false;
      if (q && !quoteSearchBlob(quote).includes(q)) return false;
      return true;
    });
  }, [quotes, listFilter, search]);

  const canSaveManual =
    Boolean(importTeamId) &&
    Boolean(manual.customerId) &&
    Boolean(manual.projectNumber.trim()) &&
    Boolean(manual.cost.trim()) &&
    !saveMutation.isPending;
  const canUpload = Boolean(importTeamId) && !importMutation.isPending && !editingId;

  const toggleFilter = (next: ListFilter) => {
    setListFilter((prev) => (prev === next ? 'all' : next));
  };

  if (quotesQuery.isLoading) {
    return <LoadingState message="Loading awarded quotes…" />;
  }

  if (quotesQuery.isError) {
    return (
      <Typography color="error" variant="body2">
        {apiErrorMessage(quotesQuery.error, 'Unable to load awarded quotes.')}
      </Typography>
    );
  }

  return (
    <Stack spacing={2.5}>
      <FinanceHeroBanner
        title="Revenue / awarded quotes"
        subtitle="Book awarded quotes for planning. Quoted date places Annual Plan sales; mark Invoiced with invoiced date when revenue is recognized."
        chips={
          <>
            <Chip size="small" label={teamId ? 'Team scope' : 'All teams'} sx={{ fontWeight: 700 }} />
            <Chip size="small" variant="outlined" label={`${quoteStats.count} quotes`} />
            {quoteStats.notInvoiced > 0 ? (
              <Chip
                size="small"
                color="warning"
                label={`${quoteStats.notInvoiced} not invoiced`}
                onClick={() => setListFilter('not_invoiced')}
              />
            ) : null}
            {quoteStats.mixedFx ? (
              <Chip size="small" color="info" label="Mixed FX → base INR" />
            ) : null}
            {quoteStats.missingDate > 0 ? (
              <Chip
                size="small"
                color="warning"
                variant="outlined"
                label={`${quoteStats.missingDate} missing date`}
                onClick={() => setListFilter('missing_date')}
              />
            ) : null}
          </>
        }
      />

      <Grid container spacing={1.5}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="primary"
            icon={RequestQuoteOutlinedIcon}
            title="Awarded quotes"
            value={String(quoteStats.count)}
            subtitle="Click to show all"
            selected={listFilter === 'all'}
            onClick={() => setListFilter('all')}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="success"
            icon={TrendingUpOutlinedIcon}
            title="Invoiced revenue Σ"
            value={financeMoney(quoteStats.invoicedRevenue, 'INR')}
            subtitle={
              quoteStats.mixedFx
                ? `Recognized · ${quoteStats.currencyCount} FX currencies`
                : 'Recognized on invoiced date'
            }
            selected={listFilter === 'invoiced'}
            onClick={() => toggleFilter('invoiced')}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="warning"
            icon={ReceiptLongOutlinedIcon}
            title="Not invoiced"
            value={String(quoteStats.notInvoiced)}
            subtitle="Awaiting billing"
            selected={listFilter === 'not_invoiced'}
            onClick={() => toggleFilter('not_invoiced')}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="info"
            icon={CalendarMonthOutlinedIcon}
            title="Missing quoted date"
            value={String(quoteStats.missingDate)}
            subtitle="Needed for Annual Plan FY"
            selected={listFilter === 'missing_date'}
            onClick={() => toggleFilter('missing_date')}
          />
        </Grid>
      </Grid>

      <Box ref={formRef}>
        <FinanceSection
          title={editingId ? 'Edit awarded quote' : 'Add awarded quote'}
          subtitle={
            editingId
              ? 'Update Quote #, Project #, Cost, Customer, Team, Quoted date, and Invoiced status, then Save changes.'
              : 'Enter Quote #, Project # (Customer Project #), Cost, Customer, Team, and Quoted date for Annual Plan sales sync.'
          }
        >
          <Stack spacing={1.5} sx={{ maxWidth: 960 }}>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ flexWrap: 'wrap' }}>
              <FormControl size="small" sx={{ minWidth: 220 }} required>
                <InputLabel>Team</InputLabel>
                <Select
                  label="Team"
                  value={importTeamId}
                  onChange={(e) => setImportTeamId(e.target.value)}
                >
                  {teams.map((team) => (
                    <MenuItem key={team.id} value={team.id}>
                      {team.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl size="small" sx={{ minWidth: 260 }} required>
                <InputLabel>Customer</InputLabel>
                <Select
                  label="Customer"
                  value={manual.customerId}
                  onChange={(e) => {
                    const id = e.target.value;
                    const customer = customers.find((c) => c.id === id);
                    setManual((prev) => ({
                      ...prev,
                      customerId: id,
                      currencyCode:
                        prev.currencyCode ||
                        customer?.default_currency_code?.toUpperCase() ||
                        '',
                    }));
                  }}
                >
                  {customers.map((customer) => (
                    <MenuItem key={customer.id} value={customer.id}>
                      {customer.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Stack>

            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ flexWrap: 'wrap' }}>
              <TextField
                size="small"
                label="Quote #"
                placeholder="e.g. QT-2026-27-005"
                value={manual.quoteNumber}
                onChange={(e) => setManual({ ...manual, quoteNumber: e.target.value })}
                sx={{ minWidth: 200, flex: 1 }}
              />
              <TextField
                size="small"
                required
                label="Project #"
                placeholder="Customer Project #"
                value={manual.projectNumber}
                onChange={(e) => setManual({ ...manual, projectNumber: e.target.value })}
                sx={{ minWidth: 160, flex: 1 }}
              />
              <TextField
                size="small"
                required
                label="Cost"
                placeholder="Quoted amount"
                value={manual.cost}
                onChange={(e) => setManual({ ...manual, cost: e.target.value })}
                sx={{ minWidth: 140, flex: 1 }}
                helperText="Quoted revenue / Total"
              />
              <TextField
                size="small"
                type="date"
                label="Quoted date"
                value={manual.quotedDate}
                onChange={(e) => setManual({ ...manual, quotedDate: e.target.value })}
                slotProps={{ inputLabel: { shrink: true } }}
                sx={{ minWidth: 160 }}
                helperText="FY quarter for Annual Plan sales"
              />
              {editingId ? (
                <>
                  <FormControl size="small" sx={{ minWidth: 140 }}>
                    <InputLabel>Invoiced</InputLabel>
                    <Select
                      label="Invoiced"
                      value={manual.isInvoiced}
                      onChange={(e) =>
                        setManual({
                          ...manual,
                          isInvoiced: e.target.value as 'yes' | 'no',
                          invoicedDate:
                            e.target.value === 'yes' && !manual.invoicedDate
                              ? new Date().toISOString().slice(0, 10)
                              : manual.invoicedDate,
                        })
                      }
                    >
                      <MenuItem value="no">No</MenuItem>
                      <MenuItem value="yes">Yes</MenuItem>
                    </Select>
                  </FormControl>
                  {manual.isInvoiced === 'yes' ? (
                    <TextField
                      size="small"
                      type="date"
                      label="Invoiced date"
                      value={manual.invoicedDate}
                      onChange={(e) => setManual({ ...manual, invoicedDate: e.target.value })}
                      slotProps={{ inputLabel: { shrink: true } }}
                      sx={{ minWidth: 160 }}
                      helperText="Revenue is recognized on this date"
                    />
                  ) : null}
                </>
              ) : null}
              <FormControl size="small" sx={{ minWidth: 130 }}>
                <InputLabel>Currency</InputLabel>
                <Select
                  label="Currency"
                  value={manual.currencyCode || ''}
                  onChange={(e) =>
                    setManual({ ...manual, currencyCode: String(e.target.value).toUpperCase() })
                  }
                >
                  {currencyOptions.map((currency) => (
                    <MenuItem key={currency.code} value={currency.code.toUpperCase()}>
                      {currency.code.toUpperCase()}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Stack>

            <Stack
              direction={{ xs: 'column', sm: 'row' }}
              spacing={1.5}
              sx={{ alignItems: 'center' }}
            >
              <FormControlLabel
                control={
                  <Checkbox
                    checked={createProject}
                    onChange={(e) => setCreateProject(e.target.checked)}
                    size="small"
                  />
                }
                label="Create project if missing"
              />
              <Button
                variant="contained"
                disabled={!canSaveManual}
                onClick={() => saveMutation.mutate()}
              >
                {saveMutation.isPending
                  ? 'Saving…'
                  : editingId
                    ? 'Save changes'
                    : 'Save quote'}
              </Button>
              {editingId ? (
                <Button variant="outlined" onClick={cancelEdit}>
                  Cancel
                </Button>
              ) : null}
            </Stack>
            {!importTeamId ? (
              <Typography variant="caption" color="warning.main">
                Select a team. All teams is not valid for save/import.
              </Typography>
            ) : null}
          </Stack>
        </FinanceSection>
      </Box>

      {!editingId ? (
        <FinanceSection
          title="Optional file upload"
          subtitle={`Batch Excel/PDF/CSV (${IMPORT_FORMAT_LABEL_WITH_CSV}). Prefer manual entry above when smart parse fails.`}
        >
          <Button variant="outlined" component="label" disabled={!canUpload}>
            Upload Quote File
            <input
              hidden
              type="file"
              accept={IMPORT_ACCEPT_WITH_CSV}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) importMutation.mutate(file);
                event.target.value = '';
              }}
            />
          </Button>
        </FinanceSection>
      ) : null}

      {lastImport.length > 0 && !editingId ? (
        <FinanceSection
          title="Last save / import"
          subtitle="Result of the most recent manual save or file upload."
        >
          <Stack spacing={1.25}>
            {lastImport.map((item) => (
              <Box key={item.quote_id} sx={financeListRowSx}>
                <Box>
                  <Typography sx={{ fontWeight: 600 }}>
                    {item.external_quote_number
                      ? `${item.external_quote_number} · ${item.tool_number}`
                      : item.tool_number}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {item.customer_name ?? 'Customer'} · {item.team_name ?? 'No team'} ·{' '}
                    {item.quoted_hours ?? '—'} hrs ·{' '}
                    {financeMoney(item.quoted_revenue, item.currency_code || 'INR')}
                    {item.project_created
                      ? ' · Created project'
                      : item.project_linked
                        ? ' · Linked project'
                        : ' · Unlinked'}
                  </Typography>
                  {(item.warnings ?? []).map((warning) => (
                    <Typography
                      key={warning}
                      variant="caption"
                      color="warning.main"
                      sx={{ display: 'block' }}
                    >
                      {warning}
                    </Typography>
                  ))}
                </Box>
              </Box>
            ))}
          </Stack>
        </FinanceSection>
      ) : null}

      <FinanceSection
        title="Awarded quotes"
        subtitle={
          listFilter === 'all' && !search.trim()
            ? 'Scan booked quotes by amount, invoice status, and project link. Edit opens the form above.'
            : `Showing ${filteredQuotes.length} of ${quotes.length} quotes`
        }
        action={
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            spacing={1}
            sx={{ alignItems: { xs: 'stretch', sm: 'center' }, flexWrap: 'wrap' }}
          >
            <TextField
              size="small"
              placeholder="Search quote, project, customer…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              sx={{ minWidth: { xs: '100%', sm: 240 } }}
              slotProps={{
                input: {
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchOutlinedIcon fontSize="small" color="action" />
                    </InputAdornment>
                  ),
                },
              }}
            />
            <Stack direction="row" spacing={0.75} useFlexGap sx={{ flexWrap: 'wrap' }}>
              {(
                [
                  { key: 'not_invoiced' as const, label: 'Not invoiced' },
                  { key: 'invoiced' as const, label: 'Invoiced' },
                  { key: 'unlinked' as const, label: 'Unlinked' },
                  { key: 'missing_date' as const, label: 'No date' },
                ] as const
              ).map((chip) => (
                <Chip
                  key={chip.key}
                  size="small"
                  label={chip.label}
                  variant={listFilter === chip.key ? 'filled' : 'outlined'}
                  color={listFilter === chip.key ? 'primary' : 'default'}
                  onClick={() => toggleFilter(chip.key)}
                />
              ))}
              {(listFilter !== 'all' || search.trim()) && (
                <Chip
                  size="small"
                  label="Clear"
                  onClick={() => {
                    setListFilter('all');
                    setSearch('');
                  }}
                />
              )}
            </Stack>
          </Stack>
        }
      >
        <FinanceQuotesTable
          rows={filteredQuotes}
          emptyMessage={
            quotes.length === 0
              ? 'No awarded quotes yet — save or import the first one above.'
              : 'No quotes match this filter. Clear search or filters to see all.'
          }
          onEdit={startEdit}
          onDelete={setDeleteTarget}
        />
      </FinanceSection>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete quote?"
        message="This removes the quote from Financial Planning lists and Overview team revenue (soft-delete)."
        recordName={
          deleteTarget
            ? `${deleteTarget.external_quote_number ? `${deleteTarget.external_quote_number} · ` : ''}${deleteTarget.tool_number} · ${deleteTarget.customer_name ?? 'Customer'} · ${deleteTarget.currency_code}${deleteTarget.quoted_revenue != null ? ` ${deleteTarget.quoted_revenue}` : ''}`
            : undefined
        }
        confirmLabel="Delete"
        danger
        loading={deleteMutation.isPending}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget.id);
        }}
      />
    </Stack>
  );
}
