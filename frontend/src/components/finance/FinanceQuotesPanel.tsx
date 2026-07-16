import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  Checkbox,
  FormControl,
  FormControlLabel,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import CalendarMonthOutlinedIcon from '@mui/icons-material/CalendarMonthOutlined';
import LinkOutlinedIcon from '@mui/icons-material/LinkOutlined';
import RequestQuoteOutlinedIcon from '@mui/icons-material/RequestQuoteOutlined';
import TrendingUpOutlinedIcon from '@mui/icons-material/TrendingUpOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { fetchCustomers, fetchTeams } from '../../api/lookups';
import {
  IMPORT_ACCEPT_WITH_CSV,
  IMPORT_FORMAT_LABEL_WITH_CSV,
} from '../../config/importFormats';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { useToast } from '../../context/ToastContext';
import { apiErrorMessage } from '../../utils/apiErrorMessage';
import { toFiniteNumber } from '../../utils/format';
import { designTokens } from '../../theme/designTokens';
import { KpiMetricCard } from '../ui/design-system/KpiMetricCard';
import { teamQueryParam } from './FinanceTeamFilter';
import {
  FinanceHeroBanner,
  FinanceSection,
  financeMoney,
} from './FinanceCockpitPrimitives';

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
};

const emptyManual: ManualQuoteForm = {
  customerId: '',
  quoteNumber: '',
  projectNumber: '',
  cost: '',
  currencyCode: '',
  quotedDate: new Date().toISOString().slice(0, 10),
};

const listRowSx = {
  p: 1.5,
  borderRadius: `${designTokens.radius.md}px`,
  border: '1px solid',
  borderColor: 'divider',
  bgcolor: 'background.paper',
  display: 'flex',
  justifyContent: 'space-between',
  gap: 2,
  flexWrap: 'wrap' as const,
  alignItems: 'flex-start',
};

export function FinanceQuotesPanel({ teamId }: { teamId: string }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [importTeamId, setImportTeamId] = useState(teamId);
  const [createProject, setCreateProject] = useState(true);
  const [manual, setManual] = useState<ManualQuoteForm>(emptyManual);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<QuoteRow | null>(null);
  const [lastImport, setLastImport] = useState<QuoteImportItem[]>([]);

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
  const quotes = quotesQuery.data ?? [];
  const quoteStats = useMemo(() => {
    // Always sum FX-snapshotted base INR — never mix USD/EUR source amounts as "INR".
    const revenue = quotes.reduce((s, q) => s + toFiniteNumber(q.base_quoted_revenue_inr), 0);
    const linked = quotes.filter((q) => q.project_linked).length;
    const missingDate = quotes.filter((q) => !q.quoted_date).length;
    const currencies = new Set(
      quotes.map((q) => (q.currency_code || 'INR').toUpperCase()).filter(Boolean),
    );
    return {
      count: quotes.length,
      revenue,
      linked,
      missingDate,
      mixedFx: currencies.size > 1,
      currencyCount: currencies.size,
    };
  }, [quotes]);

  const canSaveManual =
    Boolean(importTeamId) &&
    Boolean(manual.customerId) &&
    Boolean(manual.projectNumber.trim()) &&
    Boolean(manual.cost.trim()) &&
    !saveMutation.isPending;
  const canUpload = Boolean(importTeamId) && !importMutation.isPending && !editingId;

  return (
    <Stack spacing={2.5}>
      <FinanceHeroBanner
        title="Revenue / awarded quotes"
        subtitle="Booked quote revenue for planning — set Quoted date so Annual Plan can place revenue in the correct FY quarter."
        chips={
          <>
            <Chip size="small" label={teamId ? 'Team scope' : 'All teams'} sx={{ fontWeight: 700 }} />
            <Chip size="small" variant="outlined" label={`${quoteStats.count} quotes`} />
            {quoteStats.mixedFx ? (
              <Chip size="small" color="info" label="Mixed FX → base INR" />
            ) : null}
            {quoteStats.missingDate > 0 ? (
              <Chip size="small" color="warning" label={`${quoteStats.missingDate} missing date`} />
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
            subtitle="Listed in scope"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="success"
            icon={TrendingUpOutlinedIcon}
            title="Booked revenue Σ"
            value={financeMoney(quoteStats.revenue, 'INR')}
            subtitle={
              quoteStats.mixedFx
                ? `Base INR · ${quoteStats.currencyCount} currencies FX-converted`
                : 'Base INR · FX at quote date'
            }
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="info"
            icon={LinkOutlinedIcon}
            title="Project-linked"
            value={String(quoteStats.linked)}
            subtitle="Of listed quotes"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="warning"
            icon={CalendarMonthOutlinedIcon}
            title="Missing quoted date"
            value={String(quoteStats.missingDate)}
            subtitle="Needed for Annual Plan FY"
          />
        </Grid>
      </Grid>

      <FinanceSection
        title={editingId ? 'Edit awarded quote' : 'Add awarded quote'}
        subtitle={
          editingId
            ? 'Update Quote #, Project #, Cost, Customer, Team, and Quoted date, then Save changes.'
            : 'Enter Quote #, Project # (Customer Project #), Cost, Customer, Team, and Quoted date for Annual Plan sales sync.'
        }
      >
        <Stack spacing={1.5} sx={{ maxWidth: 900 }}>
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
            <TextField
              size="small"
              label="Currency"
              placeholder="USD / INR"
              value={manual.currencyCode}
              onChange={(e) =>
                setManual({ ...manual, currencyCode: e.target.value.toUpperCase() })
              }
              sx={{ minWidth: 110, maxWidth: 140 }}
            />
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
        <FinanceSection title="Last save / import" subtitle="Result of the most recent manual save or file upload.">
          <Stack spacing={1.25}>
            {lastImport.map((item) => (
              <Box key={item.quote_id} sx={listRowSx}>
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
        subtitle="Edit or delete booked quotes. Quoted date drives Annual Plan sales-from-quotes placement."
      >
        <Stack spacing={1.25}>
          {quotes.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No awarded quotes yet — save or import the first one above.
            </Typography>
          ) : (
            quotes.map((quote) => (
              <Box key={quote.id} sx={listRowSx}>
                <Box sx={{ minWidth: 0, flex: 1 }}>
                  <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap', alignItems: 'center', mb: 0.5 }}>
                    <Typography sx={{ fontWeight: 600 }}>
                      {quote.external_quote_number
                        ? `${quote.external_quote_number} · ${quote.tool_number}`
                        : quote.tool_number}
                    </Typography>
                    {quote.project_linked ? (
                      <Chip size="small" color="success" variant="outlined" label="Linked" />
                    ) : (
                      <Chip size="small" variant="outlined" label="Unlinked" />
                    )}
                    {!quote.quoted_date ? (
                      <Chip size="small" color="warning" label="No quoted date" />
                    ) : null}
                  </Stack>
                  <Typography variant="body2" color="text.secondary">
                    {quote.customer_name ?? 'Customer'} · {quote.team_name ?? 'No team'} ·{' '}
                    {financeMoney(quote.quoted_revenue, quote.currency_code || 'INR')}
                    {quote.base_quoted_revenue_inr != null &&
                    (quote.currency_code || 'INR').toUpperCase() !== 'INR'
                      ? ` ≈ ${financeMoney(quote.base_quoted_revenue_inr, 'INR')}`
                      : ''}{' '}
                    · rev {quote.current_revision}
                    {quote.quoted_date ? ` · quoted ${quote.quoted_date}` : ''}
                  </Typography>
                </Box>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                  <Button size="small" variant="contained" onClick={() => startEdit(quote)}>
                    Edit
                  </Button>
                  <Button
                    size="small"
                    color="error"
                    variant="outlined"
                    onClick={() => setDeleteTarget(quote)}
                  >
                    Delete
                  </Button>
                </Stack>
              </Box>
            ))
          )}
        </Stack>
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
