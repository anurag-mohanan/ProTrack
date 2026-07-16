import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
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
import { teamQueryParam } from './FinanceTeamFilter';
import { FinanceHeroBanner } from './FinanceCockpitPrimitives';

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
};

const emptyManual: ManualQuoteForm = {
  customerId: '',
  quoteNumber: '',
  projectNumber: '',
  cost: '',
  currencyCode: '',
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
  const canSaveManual =
    Boolean(importTeamId) &&
    Boolean(manual.customerId) &&
    Boolean(manual.projectNumber.trim()) &&
    Boolean(manual.cost.trim()) &&
    !saveMutation.isPending;
  const canUpload = Boolean(importTeamId) && !importMutation.isPending && !editingId;

  return (
    <Stack spacing={2}>
      <FinanceHeroBanner
        title="Revenue / awarded quotes"
        subtitle="Booked quote revenue signals for planning — manual entry, edit/delete, and optional file import."
      />
      <Box>
        <Typography variant="h6" sx={{ mb: 1 }}>
          Awarded project quotes
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          {editingId ? (
            <>
              <strong>Edit quote</strong> — update Quote #, Project #, Cost, Customer, and Team,
              then Save changes.
            </>
          ) : (
            <>
              <strong>This phase:</strong> type <strong>Quote #</strong>, <strong>Project #</strong>{' '}
              (Customer Project #), and <strong>Cost</strong> (quoted amount). Select Customer +
              Team. Use Edit / Delete on listed quotes (same as Expenses).
            </>
          )}
        </Typography>

        <Stack spacing={1.5} sx={{ mb: 2, maxWidth: 720 }}>
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

        {!editingId ? (
          <>
            <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
              Optional file upload
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Batch Excel/PDF/CSV still available ({IMPORT_FORMAT_LABEL_WITH_CSV}). Prefer manual
              entry above when smart parse fails.
            </Typography>
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
          </>
        ) : null}
      </Box>

      {lastImport.length > 0 && !editingId ? (
        <Box>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Last save / import
          </Typography>
          <Stack spacing={1}>
            {lastImport.map((item) => (
              <Card key={item.quote_id} variant="outlined">
                <CardContent>
                  <Typography sx={{ fontWeight: 600 }}>
                    {item.external_quote_number
                      ? `${item.external_quote_number} · ${item.tool_number}`
                      : item.tool_number}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {item.customer_name ?? 'Customer'} · {item.team_name ?? 'No team'} ·{' '}
                    {item.quoted_hours ?? '—'} hrs · {item.currency_code ?? ''}{' '}
                    {item.quoted_revenue ?? '—'}
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
                </CardContent>
              </Card>
            ))}
          </Stack>
        </Box>
      ) : null}

      <Typography variant="subtitle2">Imported quotes</Typography>
      <Stack spacing={1}>
        {(quotesQuery.data ?? []).map((quote) => (
          <Card key={quote.id} variant="outlined">
            <CardContent
              sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap' }}
            >
              <Box>
                <Typography sx={{ fontWeight: 600 }}>
                  {quote.external_quote_number
                    ? `${quote.external_quote_number} · ${quote.tool_number}`
                    : quote.tool_number}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {quote.customer_name ?? 'Customer'} · {quote.team_name ?? 'No team'} ·{' '}
                  {quote.currency_code}
                  {quote.quoted_revenue != null ? ` ${quote.quoted_revenue}` : ''} · rev{' '}
                  {quote.current_revision}
                  {quote.project_linked ? ' · Linked project' : ' · Unlinked'}
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
            </CardContent>
          </Card>
        ))}
      </Stack>

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
