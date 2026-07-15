import { useEffect, useState } from 'react';
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
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { fetchTeams } from '../../api/lookups';
import {
  IMPORT_ACCEPT_WITH_CSV,
  IMPORT_FORMAT_LABEL_WITH_CSV,
} from '../../config/importFormats';
import { useToast } from '../../context/ToastContext';
import { apiErrorMessage } from '../../utils/apiErrorMessage';
import { teamQueryParam } from './FinanceTeamFilter';

type QuoteRow = {
  id: string;
  tool_number: string;
  external_quote_number?: string | null;
  currency_code: string;
  current_revision: string;
  team_id?: string | null;
  team_name?: string | null;
  customer_name?: string | null;
  project_linked?: boolean;
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

export function FinanceQuotesPanel({ teamId }: { teamId: string }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [importTeamId, setImportTeamId] = useState(teamId);
  const [createProject, setCreateProject] = useState(true);
  const [lastImport, setLastImport] = useState<QuoteImportItem[]>([]);

  useEffect(() => {
    if (teamId) setImportTeamId(teamId);
  }, [teamId]);

  const teamsQuery = useQuery({
    queryKey: ['lookup-teams'],
    queryFn: fetchTeams,
  });
  const listQ = teamQueryParam(teamId);
  const quotesQuery = useQuery({
    queryKey: ['finance-quotes', teamId || 'all'],
    queryFn: async () => (await apiClient.get<QuoteRow[]>(`/finance/quotes${listQ}`)).data,
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
      // Leave Content-Type unset so the browser adds multipart boundary (see apiClient).
      return (await apiClient.post<QuoteImportResult>('/finance/quotes/import', form)).data;
    },
    onSuccess: (data) => {
      setLastImport(data.items ?? []);
      const created = (data.items ?? []).filter((item) => item.project_created).length;
      const linked = (data.items ?? []).filter((item) => item.project_linked).length;
      showSuccess(
        `Imported ${data.imported_count} awarded quote(s)` +
          (created ? ` · ${created} project(s) created` : '') +
          (linked && !created ? ` · ${linked} linked` : ''),
      );
      void queryClient.invalidateQueries({ queryKey: ['finance-quotes'] });
      void queryClient.invalidateQueries({ queryKey: ['finance-dashboard'] });
      void queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
    onError: (error: unknown) => {
      showError(apiErrorMessage(error, 'Quote import failed'));
    },
  });

  const teams = teamsQuery.data ?? [];
  const canUpload = Boolean(importTeamId) && !importMutation.isPending;

  return (
    <Stack spacing={2}>
      <Box>
        <Typography variant="h6" sx={{ mb: 1 }}>
          Awarded project quotes
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Import <strong>awarded</strong> (won) project packs only — not bid drafts. AI field
          recognition maps Quote#, Customer Project #, Prepared For, hours and amount from Prosohm QT
          PDFs and Excel/CSV packs. Team is required so Overview can attribute quote revenue. Formats:{' '}
          {IMPORT_FORMAT_LABEL_WITH_CSV}. Legacy .xls is not supported.
        </Typography>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ mb: 1.5, flexWrap: 'wrap' }}>
          <FormControl size="small" sx={{ minWidth: 220 }} required>
            <InputLabel>Team for this upload</InputLabel>
            <Select
              label="Team for this upload"
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
          <Button variant="contained" component="label" disabled={!canUpload}>
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
        </Stack>
        {!importTeamId ? (
          <Typography variant="caption" color="warning.main">
            Select a team (page filter or upload team). All teams is not valid for import.
          </Typography>
        ) : null}
      </Box>

      {lastImport.length > 0 ? (
        <Box>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Last import
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
                    <Typography key={warning} variant="caption" color="warning.main" sx={{ display: 'block' }}>
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
            <CardContent>
              <Typography sx={{ fontWeight: 600 }}>
                {quote.external_quote_number
                  ? `${quote.external_quote_number} · ${quote.tool_number}`
                  : quote.tool_number}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {quote.customer_name ?? 'Customer'} · {quote.team_name ?? 'No team'} ·{' '}
                {quote.currency_code} · rev {quote.current_revision}
                {quote.project_linked ? ' · Linked project' : ' · Unlinked'}
              </Typography>
            </CardContent>
          </Card>
        ))}
      </Stack>
    </Stack>
  );
}
