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
import { InvoicePdfImportDialog } from './InvoicePdfImportDialog';
import { QuotePdfImportDialog } from './QuotePdfImportDialog';
import { FinanceQuotesTable } from './FinanceQuotesTable';
import { QuoteCashLedgerPanel } from './QuoteCashLedgerPanel';

type QuoteCashLine = {
  id: string;
  amount: number | string;
  line_date: string;
  notes?: string | null;
  reference?: string | null;
};

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
  project_id?: string | null;
  quoted_hours?: number | string | null;
  quoted_revenue?: number | string | null;
  base_quoted_revenue_inr?: number | string | null;
  fx_rate?: number | string | null;
  fx_date?: string | null;
  quoted_date?: string | null;
  invoiced_date?: string | null;
  is_invoiced?: boolean;
  customer_po_number?: string | null;
  is_paid?: boolean;
  paid_date?: string | null;
  payment_follow_up_due?: boolean;
  payment_follow_up_on?: string | null;
  total_invoiced?: number | string | null;
  total_paid?: number | string | null;
  balance_due?: number | string | null;
  remaining_to_invoice?: number | string | null;
  remaining_contract?: number | string | null;
  invoice_status?: string | null;
  payment_status?: string | null;
  is_partially_invoiced?: boolean;
  is_partially_paid?: boolean;
  invoice_lines?: QuoteCashLine[];
  payment_lines?: QuoteCashLine[];
  billing_ready?: boolean;
  billing_gaps?: string[];
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
  customerPoNumber: string;
};

type ListFilter =
  | 'all'
  | 'not_invoiced'
  | 'partially_invoiced'
  | 'missing_date'
  | 'unlinked'
  | 'invoiced'
  | 'awaiting_payment'
  | 'partially_paid'
  | 'follow_up';

const emptyManual: ManualQuoteForm = {
  customerId: '',
  quoteNumber: '',
  projectNumber: '',
  cost: '',
  currencyCode: '',
  quotedDate: new Date().toISOString().slice(0, 10),
  customerPoNumber: '',
};

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
  const [invoicePdfOpen, setInvoicePdfOpen] = useState(false);
  const [quotePdfOpen, setQuotePdfOpen] = useState(false);
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
  const quotesStatsQuery = useQuery({
    queryKey: ['finance-quotes', teamId || 'all', 'stats'],
    queryFn: async () => (await apiClient.get<QuoteRow[]>(`/finance/quotes${listQ}`)).data,
  });
  const quotesQuery = useQuery({
    queryKey: ['finance-quotes', teamId || 'all', listFilter, search.trim()],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (teamId) params.set('team_id', teamId);
      if (listFilter !== 'all') params.set('list_filter', listFilter);
      if (search.trim()) params.set('q', search.trim());
      const qs = params.toString();
      return (await apiClient.get<QuoteRow[]>(`/finance/quotes${qs ? `?${qs}` : ''}`)).data;
    },
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
            customer_po_number: manual.customerPoNumber.trim() || null,
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
      customerPoNumber: quote.customer_po_number ?? '',
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
        void queryClient.setQueryData(
          ['finance-quotes', teamId || 'all'],
          (prev: QuoteRow[] | undefined) =>
            (prev ?? []).map((row) =>
              row.id === (data as QuoteRow).id ? { ...row, ...(data as QuoteRow) } : row,
            ),
        );
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
      const lower = file.name.toLowerCase();
      if (lower.endsWith('.pdf')) {
        throw new Error(
          'Quote PDFs use extract → review → confirm. Use Import Quote PDF instead of batch upload.',
        );
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

  const quotesAll = quotesStatsQuery.data ?? [];
  const filteredQuotes = quotesQuery.data ?? [];
  const quoteStats = useMemo(() => {
    const invoicedRevenue = quotesAll
      .filter((q) => q.invoice_status === 'full')
      .reduce((s, q) => s + toFiniteNumber(q.base_quoted_revenue_inr), 0);
    const unpaidReceivable = quotesAll.reduce((s, q) => {
      const balance = toFiniteNumber(q.balance_due);
      if (balance <= 0) return s;
      const quoted = toFiniteNumber(q.quoted_revenue);
      const base = toFiniteNumber(q.base_quoted_revenue_inr);
      if (quoted > 0 && base > 0) return s + (balance / quoted) * base;
      return s + balance;
    }, 0);
    const awaitingPaymentCount = quotesAll.filter(
      (q) => toFiniteNumber(q.balance_due) > 0,
    ).length;
    const followUpDue = quotesAll.filter((q) => q.payment_follow_up_due).length;
    const missingDate = quotesAll.filter((q) => !q.quoted_date).length;
    const notInvoiced = quotesAll.filter((q) => (q.invoice_status || 'none') === 'none').length;
    const partiallyInvoiced = quotesAll.filter((q) => q.invoice_status === 'partial').length;
    const fullyInvoiced = quotesAll.filter((q) => q.invoice_status === 'full').length;
    const currencies = new Set(
      quotesAll.map((q) => (q.currency_code || 'INR').toUpperCase()).filter(Boolean),
    );
    return {
      count: quotesAll.length,
      invoicedRevenue,
      unpaidReceivable,
      awaitingPaymentCount,
      followUpDue,
      missingDate,
      notInvoiced,
      partiallyInvoiced,
      fullyInvoiced,
      mixedFx: currencies.size > 1,
      currencyCount: currencies.size,
    };
  }, [quotesAll]);

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

  if (quotesStatsQuery.isLoading || quotesQuery.isLoading) {
    return <LoadingState message="Loading awarded quotes…" />;
  }

  if (quotesStatsQuery.isError || quotesQuery.isError) {
    return (
      <Typography color="error" variant="body2">
        {apiErrorMessage(
          quotesQuery.error ?? quotesStatsQuery.error,
          "We couldn't load the financial data. Please try again.",
        )}
      </Typography>
    );
  }

  return (
    <Stack spacing={2.5}>
      <FinanceHeroBanner
        title="Projects & revenue"
        subtitle="Book awarded quotes, capture customer PO, and track invoice status (none / partial / full). Filters run on the server. Unpaid invoices get a follow-up at 30 days, then weekly."
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
            {quoteStats.awaitingPaymentCount > 0 ? (
              <Chip
                size="small"
                color="info"
                label={`${quoteStats.awaitingPaymentCount} awaiting payment`}
                onClick={() => setListFilter('awaiting_payment')}
              />
            ) : null}
            {quoteStats.followUpDue > 0 ? (
              <Chip
                size="small"
                color="error"
                label={`${quoteStats.followUpDue} payment follow-up`}
                onClick={() => setListFilter('follow_up')}
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
            title="Fully invoiced Σ"
            value={financeMoney(quoteStats.invoicedRevenue, 'INR')}
            subtitle={
              quoteStats.mixedFx
                ? `Fully invoiced · ${quoteStats.fullyInvoiced} quotes · ${quoteStats.currencyCount} FX`
                : `Fully invoiced · ${quoteStats.fullyInvoiced} quotes`
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
            title="Awaiting payment Σ"
            value={financeMoney(quoteStats.unpaidReceivable, 'INR')}
            subtitle={`${quoteStats.awaitingPaymentCount} invoiced · unpaid`}
            selected={listFilter === 'awaiting_payment'}
            onClick={() => toggleFilter('awaiting_payment')}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="info"
            icon={CalendarMonthOutlinedIcon}
            title="Payment follow-up"
            value={String(quoteStats.followUpDue)}
            subtitle="30+ days unpaid (then weekly)"
            selected={listFilter === 'follow_up'}
            onClick={() => toggleFilter('follow_up')}
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
                <TextField
                  size="small"
                  label="Customer PO #"
                  placeholder="PO number"
                  value={manual.customerPoNumber}
                  onChange={(e) =>
                    setManual({ ...manual, customerPoNumber: e.target.value })
                  }
                  sx={{ minWidth: 160, flex: 1 }}
                  helperText="Customer purchase order"
                />
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

            {editingId ? (
              <QuoteCashLedgerPanel
                quote={
                  (quotesAll.find((q) => q.id === editingId) as QuoteRow | undefined) ?? {
                    id: editingId,
                    currency_code: manual.currencyCode || 'INR',
                    quoted_revenue: manual.cost,
                    total_invoiced: 0,
                    total_paid: 0,
                    balance_due: 0,
                    remaining_to_invoice: 0,
                    invoice_lines: [],
                    payment_lines: [],
                  }
                }
                onChanged={(updated) => {
                  void queryClient.setQueryData(
                    ['finance-quotes', teamId || 'all'],
                    (prev: QuoteRow[] | undefined) =>
                      (prev ?? []).map((row) =>
                        row.id === updated.id ? { ...row, ...updated } : row,
                      ),
                  );
                  invalidateFinance();
                }}
              />
            ) : null}

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
          subtitle="Batch Excel/CSV for quotes. Quote and invoice PDFs use extract → review → confirm (never auto-save)."
        >
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <Button variant="outlined" component="label" disabled={!canUpload}>
              Upload Quote File
              <input
                hidden
                type="file"
                accept=".xlsx,.xlsm,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel.sheet.macroEnabled.12,text/csv"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) importMutation.mutate(file);
                  event.target.value = '';
                }}
              />
            </Button>
            <Button
              variant="outlined"
              disabled={!importTeamId}
              onClick={() => setQuotePdfOpen(true)}
            >
              Import Quote PDF
            </Button>
            <Button
              variant="outlined"
              disabled={!importTeamId}
              onClick={() => setInvoicePdfOpen(true)}
            >
              Import Invoice PDF
            </Button>
          </Box>
        </FinanceSection>
      ) : null}

      <QuotePdfImportDialog
        open={quotePdfOpen}
        onClose={() => setQuotePdfOpen(false)}
        teamId={importTeamId}
        createProject={createProject}
        onImported={(data) => {
          applyImportResult(data as QuoteImportResult, 'Imported quote from PDF');
        }}
      />

      <InvoicePdfImportDialog
        open={invoicePdfOpen}
        onClose={() => setInvoicePdfOpen(false)}
        teamId={importTeamId || undefined}
        onImported={() => {
          void queryClient.invalidateQueries({ queryKey: ['finance-quotes'] });
          void queryClient.invalidateQueries({ queryKey: ['finance-dashboard'] });
        }}
      />

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
            : `Showing ${filteredQuotes.length} of ${quoteStats.count} quotes (server filter)`
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
                  { key: 'partially_invoiced' as const, label: 'Partially invoiced' },
                  { key: 'invoiced' as const, label: 'Invoiced' },
                  { key: 'partially_paid' as const, label: 'Partially paid' },
                  { key: 'awaiting_payment' as const, label: 'Awaiting payment' },
                  { key: 'follow_up' as const, label: 'Follow-up due' },
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
            quoteStats.count === 0
              ? 'No awarded quotes yet — save or import the first one above.'
              : 'No quotes match the selected filters.'
          }
          onEdit={startEdit}
          onDelete={setDeleteTarget}
        />
      </FinanceSection>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete quote?"
        message="This removes the quote from Finance lists and Overview team revenue (soft-delete)."
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
