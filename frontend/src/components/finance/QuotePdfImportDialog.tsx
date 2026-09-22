import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { fetchCustomers, fetchTeams } from '../../api/lookups';
import { useToast } from '../../context/ToastContext';
import { apiErrorMessage } from '../../utils/apiErrorMessage';

type FieldCandidate = {
  value?: string | null;
  confidence?: number;
  needs_review?: boolean;
};

type StageHour = {
  label: string;
  hours: number;
  source_line?: string;
};

type ExtractResult = {
  text_extractable: boolean;
  ocr_used: boolean;
  warnings: string[];
  content_sha256?: string | null;
  filename?: string | null;
  document_type?: string;
  document_type_confidence?: number;
  fields: Record<string, FieldCandidate>;
  stage_hours?: StageHour[];
  customer_matches: Array<{ customer_id: string; name: string; code?: string; confidence: number }>;
  project_matches: Array<{
    project_id: string;
    tool_number: string;
    name?: string | null;
    confidence: number;
  }>;
  duplicates: Array<{
    quote_id: string;
    tool_number?: string;
    external_quote_number?: string | null;
    reason: string;
  }>;
  suggested_customer_id?: string | null;
  suggested_project_id?: string | null;
};

type QuoteImportResult = {
  imported_count: number;
  items?: Array<Record<string, unknown>>;
};

type TeamOption = { id: string; name: string };

type Props = {
  open: boolean;
  onClose: () => void;
  /** Optional pre-selected team from the Finance filter. Not required to start extract. */
  teamId?: string;
  teams?: TeamOption[];
  createProject?: boolean;
  onImported: (result: { imported_count: number; items?: Array<Record<string, unknown>> }) => void;
  onTeamSelected?: (teamId: string) => void;
};

function fieldValue(fields: Record<string, FieldCandidate>, key: string): string {
  return fields[key]?.value ?? '';
}

export function QuotePdfImportDialog({
  open,
  onClose,
  teamId,
  teams: teamsProp,
  createProject = true,
  onImported,
  onTeamSelected,
}: Props) {
  const { showSuccess, showError } = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [extract, setExtract] = useState<ExtractResult | null>(null);
  const [selectedTeamId, setSelectedTeamId] = useState(teamId || '');
  const [customerId, setCustomerId] = useState('');
  const [quoteNumber, setQuoteNumber] = useState('');
  const [projectNumber, setProjectNumber] = useState('');
  const [cost, setCost] = useState('');
  const [quotedHours, setQuotedHours] = useState('');
  const [currencyCode, setCurrencyCode] = useState('USD');
  const [quotedDate, setQuotedDate] = useState('');
  const [notes, setNotes] = useState('');
  const [importAnyway, setImportAnyway] = useState(false);
  const [createProjectLocal, setCreateProjectLocal] = useState(createProject);
  const [documentType, setDocumentType] = useState('quote');
  const [hoursResolved, setHoursResolved] = useState(false);

  const customersQuery = useQuery({
    queryKey: ['lookup-customers'],
    queryFn: fetchCustomers,
    enabled: open,
  });
  const teamsQuery = useQuery({
    queryKey: ['lookup-teams'],
    queryFn: fetchTeams,
    enabled: open && !(teamsProp && teamsProp.length > 0),
  });

  const teams = useMemo(() => {
    if (teamsProp && teamsProp.length > 0) return teamsProp;
    return (teamsQuery.data ?? []).map((t) => ({ id: t.id, name: t.name }));
  }, [teamsProp, teamsQuery.data]);

  useEffect(() => {
    if (open) setSelectedTeamId(teamId || '');
  }, [open, teamId]);

  const reset = () => {
    setFile(null);
    setExtract(null);
    setSelectedTeamId(teamId || '');
    setCustomerId('');
    setQuoteNumber('');
    setProjectNumber('');
    setCost('');
    setQuotedHours('');
    setCurrencyCode('USD');
    setQuotedDate('');
    setNotes('');
    setImportAnyway(false);
    setCreateProjectLocal(createProject);
    setDocumentType('quote');
    setHoursResolved(false);
    if (fileRef.current) fileRef.current.value = '';
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const extractMutation = useMutation({
    mutationFn: async (pdf: File) => {
      const form = new FormData();
      form.append('file', pdf);
      if (selectedTeamId) form.append('team_id', selectedTeamId);
      return (await apiClient.post<ExtractResult>('/finance/quotes/pdf/extract', form)).data;
    },
    onSuccess: (data) => {
      setExtract(data);
      setQuoteNumber(fieldValue(data.fields, 'external_quote_number'));
      setProjectNumber(fieldValue(data.fields, 'tool_number'));
      setCost(fieldValue(data.fields, 'quoted_revenue'));
      setQuotedHours(fieldValue(data.fields, 'quoted_hours'));
      setCurrencyCode(fieldValue(data.fields, 'currency_code') || 'USD');
      setQuotedDate(fieldValue(data.fields, 'quoted_date'));
      setNotes(fieldValue(data.fields, 'notes'));
      setCustomerId(data.suggested_customer_id || '');
      setDocumentType(data.document_type || 'quote');
      setHoursResolved(false);
      if (!data.text_extractable) {
        showError(data.warnings[0] || 'Unable to extract the document reliably.');
      }
    },
    onError: (error: unknown) =>
      showError(apiErrorMessage(error, 'Unable to extract the document reliably.')),
  });

  const confirmMutation = useMutation({
    mutationFn: async () => {
      if (!selectedTeamId) throw new Error('Select a specific team before saving this quote.');
      if (!customerId) throw new Error('Select a customer.');
      if (!projectNumber.trim()) throw new Error('Project # is required.');
      if (!cost.trim()) throw new Error('Cost (quoted amount) is required.');
      const form = new FormData();
      form.append('team_id', selectedTeamId);
      form.append('customer_id', customerId);
      form.append('tool_number', projectNumber.trim());
      form.append('quoted_revenue', String(cost).replace(/,/g, ''));
      if (quoteNumber.trim()) form.append('external_quote_number', quoteNumber.trim());
      if (currencyCode.trim()) form.append('currency_code', currencyCode.trim().toUpperCase());
      if (quotedHours.trim()) form.append('quoted_hours', String(quotedHours).replace(/,/g, ''));
      if (quotedDate.trim()) form.append('quoted_date', quotedDate.trim());
      if (notes.trim()) form.append('notes', notes.trim());
      form.append('create_project', createProjectLocal ? 'true' : 'false');
      form.append('import_anyway', importAnyway ? 'true' : 'false');
      if (extract?.content_sha256) form.append('content_sha256', extract.content_sha256);
      if (file) form.append('file', file);
      return (await apiClient.post<QuoteImportResult>('/finance/quotes/pdf/confirm', form)).data;
    },
    onSuccess: (data) => {
      if (selectedTeamId) onTeamSelected?.(selectedTeamId);
      showSuccess('Quote imported from PDF');
      handleClose();
      onImported(data);
    },
    onError: (error: unknown) =>
      showError(apiErrorMessage(error, 'Could not confirm quote import')),
  });

  const needsReview = useMemo(() => {
    if (!extract) return [];
    return Object.entries(extract.fields)
      .filter(([, field]) => field.needs_review)
      .map(([key]) => key);
  }, [extract]);

  const hourDiscrepancy = useMemo(() => {
    if (!extract) return false;
    return (extract.warnings ?? []).some((w) => w.includes('DATA REVIEW REQUIRED'));
  }, [extract]);

  const tableQty = fieldValue(extract?.fields ?? {}, 'raw_table_quantity');
  const stageSum = fieldValue(extract?.fields ?? {}, 'stage_hours_sum');
  const descTotal = fieldValue(extract?.fields ?? {}, 'raw_description_total_hours');

  const customers = useMemo(() => {
    const active = (customersQuery.data ?? []).filter((c) => c.is_active);
    const matchIds = new Set((extract?.customer_matches ?? []).map((m) => m.customer_id));
    if (matchIds.size === 0) return active;
    return [
      ...active.filter((c) => matchIds.has(c.id)),
      ...active.filter((c) => !matchIds.has(c.id)),
    ];
  }, [customersQuery.data, extract?.customer_matches]);

  const canConfirm =
    Boolean(selectedTeamId) &&
    Boolean(customerId) &&
    Boolean(projectNumber.trim()) &&
    Boolean(cost.trim()) &&
    (!hourDiscrepancy || hoursResolved) &&
    !confirmMutation.isPending;

  const confirmBlockReason = !selectedTeamId
    ? 'Select a specific team before this quote can be saved.'
    : !customerId
      ? 'Select a customer before saving.'
      : !projectNumber.trim()
        ? 'Project # is required before saving.'
        : !cost.trim()
          ? 'Quoted amount is required before saving.'
          : hourDiscrepancy && !hoursResolved
            ? 'Resolve the hour discrepancy before saving.'
            : null;

  const topProject = extract?.project_matches?.[0];

  return (
    <Dialog open={open} onClose={handleClose} fullWidth maxWidth="md">
      <DialogTitle>Quote import review</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Extract first, then review and confirm. Nothing is saved until you confirm. Team is required
          only at confirm — not to start extraction.
        </Typography>

        {!extract ? (
          <Stack spacing={2}>
            <Button variant="outlined" component="label">
              Choose PDF
              <input
                ref={fileRef}
                hidden
                type="file"
                accept="application/pdf,.pdf"
                onChange={(e) => {
                  const next = e.target.files?.[0] ?? null;
                  setFile(next);
                }}
              />
            </Button>
            {file ? (
              <Typography variant="body2">Selected: {file.name}</Typography>
            ) : null}
            <Button
              variant="contained"
              disabled={!file || extractMutation.isPending}
              onClick={() => file && extractMutation.mutate(file)}
            >
              {extractMutation.isPending ? 'Extracting…' : 'Extract for review'}
            </Button>
          </Stack>
        ) : (
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Alert severity="info">
              Document detected: <strong>{(documentType || 'unknown').toUpperCase()}</strong>
              {extract.document_type_confidence != null
                ? ` · Confidence: ${Math.round(extract.document_type_confidence)}%`
                : null}
            </Alert>
            <TextField
              select
              label="Document type"
              value={documentType}
              onChange={(e) => setDocumentType(e.target.value)}
              helperText="Change if classification is wrong before confirming."
            >
              <MenuItem value="quote">QUOTE</MenuItem>
              <MenuItem value="invoice">INVOICE</MenuItem>
              <MenuItem value="unknown">UNKNOWN</MenuItem>
            </TextField>

            {(extract.warnings ?? []).map((warning) => (
              <Alert key={warning} severity="warning">
                {warning}
              </Alert>
            ))}
            {needsReview.length > 0 ? (
              <Alert severity="info">
                Needs review: {needsReview.join(', ')}. Confirm or correct before import.
              </Alert>
            ) : null}
            {(extract.duplicates ?? []).length > 0 ? (
              <Alert severity="error">
                Possible duplicate quote detected. Review existing records or check “Import anyway”.
              </Alert>
            ) : null}

            {topProject || projectNumber ? (
              <Box sx={{ p: 1.5, bgcolor: 'action.hover', borderRadius: 1 }}>
                <Typography variant="subtitle2">Match</Typography>
                <Typography variant="body2">
                  Project: {projectNumber || topProject?.tool_number || '—'}
                  {topProject?.name ? ` — ${topProject.name}` : ''}
                </Typography>
                <Typography variant="body2">
                  Customer:{' '}
                  {customers.find((c) => c.id === customerId)?.name ||
                    fieldValue(extract.fields, 'customer_name') ||
                    '—'}
                </Typography>
              </Box>
            ) : (
              <Alert severity="warning">
                Project not found for Customer Project #. Create a project, select an existing one, or
                continue only after confirming project #.
              </Alert>
            )}

            {hourDiscrepancy ? (
              <Alert severity="error">
                <Typography variant="subtitle2" gutterBottom>
                  Hour discrepancy — DATA REVIEW REQUIRED
                </Typography>
                <Typography variant="body2">Table quantity: {tableQty || '—'} Hrs</Typography>
                <Typography variant="body2">Stage breakdown sum: {stageSum || '—'} Hrs</Typography>
                <Typography variant="body2">
                  Description stated total: {descTotal || '—'} Hrs
                </Typography>
                <Typography variant="body2" sx={{ mt: 1, mb: 1 }}>
                  Confirm commercial quoted hours (original extracted values are preserved):
                </Typography>
                <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
                  {tableQty ? (
                    <Button
                      size="small"
                      variant={quotedHours === tableQty ? 'contained' : 'outlined'}
                      onClick={() => {
                        setQuotedHours(tableQty);
                        setHoursResolved(true);
                      }}
                    >
                      Use {tableQty}
                    </Button>
                  ) : null}
                  {descTotal && descTotal !== tableQty ? (
                    <Button
                      size="small"
                      variant={quotedHours === descTotal ? 'contained' : 'outlined'}
                      onClick={() => {
                        setQuotedHours(descTotal);
                        setHoursResolved(true);
                      }}
                    >
                      Use {descTotal}
                    </Button>
                  ) : null}
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={() => setHoursResolved(true)}
                  >
                    Keep edited value
                  </Button>
                </Stack>
              </Alert>
            ) : null}

            {(extract.stage_hours ?? []).length > 0 ? (
              <Box>
                <Typography variant="subtitle2" gutterBottom>
                  Work breakdown
                </Typography>
                {(extract.stage_hours ?? []).map((s) => (
                  <Typography key={`${s.label}-${s.hours}`} variant="body2">
                    {s.label}: {s.hours}
                  </Typography>
                ))}
              </Box>
            ) : null}

            <TextField
              select
              label="Team"
              value={selectedTeamId}
              onChange={(e) => setSelectedTeamId(e.target.value)}
              required
              helperText={
                !selectedTeamId
                  ? 'Required before save — All teams is not valid for quote import.'
                  : undefined
              }
            >
              <MenuItem value="">Select team</MenuItem>
              {teams.map((t) => (
                <MenuItem key={t.id} value={t.id}>
                  {t.name}
                </MenuItem>
              ))}
            </TextField>

            <TextField
              select
              label="Customer"
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
              required
              helperText={
                extract.fields.customer_name?.needs_review
                  ? `Extracted: ${fieldValue(extract.fields, 'customer_name') || '—'} (low confidence)`
                  : fieldValue(extract.fields, 'customer_name')
                    ? `Extracted: ${fieldValue(extract.fields, 'customer_name')}`
                    : undefined
              }
            >
              <MenuItem value="">Select customer</MenuItem>
              {customers.map((c) => (
                <MenuItem key={c.id} value={c.id}>
                  {c.name}
                </MenuItem>
              ))}
            </TextField>

            <TextField
              label="Quote #"
              value={quoteNumber}
              onChange={(e) => setQuoteNumber(e.target.value)}
              helperText={
                extract.fields.external_quote_number?.needs_review
                  ? `Low confidence (${extract.fields.external_quote_number.confidence ?? 0}%)`
                  : undefined
              }
            />
            <TextField
              label="Customer Project # (ProTrack project number)"
              value={projectNumber}
              onChange={(e) => setProjectNumber(e.target.value)}
              required
            />
            <TextField
              label="Quoted amount"
              value={cost}
              onChange={(e) => setCost(e.target.value)}
              required
            />
            <TextField
              label="Commercial quoted hours (confirmed)"
              value={quotedHours}
              onChange={(e) => {
                setQuotedHours(e.target.value);
                if (hourDiscrepancy) setHoursResolved(true);
              }}
              helperText={
                hourDiscrepancy
                  ? `Raw table: ${tableQty || '—'} · Stage sum: ${stageSum || '—'} · Desc TOTAL: ${descTotal || '—'}`
                  : undefined
              }
            />
            <TextField
              label="Currency"
              value={currencyCode}
              onChange={(e) => setCurrencyCode(e.target.value.toUpperCase())}
            />
            <TextField
              label="Quoted date"
              type="date"
              value={quotedDate}
              onChange={(e) => setQuotedDate(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <TextField
              label="Notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              multiline
              minRows={2}
            />

            {(extract.project_matches ?? []).length > 0 ? (
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Matching projects
                </Typography>
                {(extract.project_matches ?? []).map((p) => (
                  <Typography key={p.project_id} variant="body2">
                    {p.tool_number}
                    {p.name ? ` · ${p.name}` : ''} ({Math.round(p.confidence)}%)
                  </Typography>
                ))}
              </Box>
            ) : null}

            <FormControlLabel
              control={
                <Checkbox
                  checked={createProjectLocal}
                  onChange={(e) => setCreateProjectLocal(e.target.checked)}
                />
              }
              label="Create project if missing (requires confirmation via this checkbox)"
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={importAnyway}
                  onChange={(e) => setImportAnyway(e.target.checked)}
                />
              }
              label="Import anyway despite duplicate warning"
            />
            {confirmBlockReason ? (
              <Typography variant="caption" color="warning.main">
                {confirmBlockReason}
              </Typography>
            ) : null}
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Cancel</Button>
        {extract ? (
          <>
            <Button
              onClick={() => {
                setExtract(null);
                setImportAnyway(false);
                setHoursResolved(false);
              }}
            >
              Back
            </Button>
            <Button
              variant="contained"
              disabled={!canConfirm}
              onClick={() => confirmMutation.mutate()}
            >
              Confirm & import
            </Button>
          </>
        ) : null}
      </DialogActions>
    </Dialog>
  );
}
