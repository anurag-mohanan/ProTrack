import { useEffect, useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  FormControl,
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
  currency_code: string;
  current_revision: string;
  team_id?: string | null;
  team_name?: string | null;
  customer_name?: string | null;
  project_linked?: boolean;
};

export function FinanceQuotesPanel({ teamId }: { teamId: string }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [importTeamId, setImportTeamId] = useState(teamId);

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
      const form = new FormData();
      form.append('file', file);
      form.append('team_id', importTeamId);
      return (await apiClient.post('/finance/quotes/import', form)).data;
    },
    onSuccess: (data: { imported_count: number }) => {
      showSuccess(`Imported ${data.imported_count} awarded quote(s)`);
      void queryClient.invalidateQueries({ queryKey: ['finance-quotes'] });
      void queryClient.invalidateQueries({ queryKey: ['finance-dashboard'] });
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
          Import <strong>awarded</strong> (won) project packs only — not bid drafts. Team is required
          so Overview can attribute quote revenue. Formats: {IMPORT_FORMAT_LABEL_WITH_CSV}. PDF must
          be a text table with a header row. Legacy .xls is not supported.
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

      <Typography variant="subtitle2">Imported quotes</Typography>
      <Stack spacing={1}>
        {(quotesQuery.data ?? []).map((quote) => (
          <Card key={quote.id} variant="outlined">
            <CardContent>
              <Typography sx={{ fontWeight: 600 }}>{quote.tool_number}</Typography>
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
