import { useState } from 'react';
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
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import { apiErrorMessage } from '../../utils/apiErrorMessage';

type Currency = { code: string; name: string; symbol?: string | null; is_base?: boolean };
type FxRate = {
  id: string;
  from_currency: string;
  to_currency: string;
  rate: number;
  effective_date: string;
  source?: string;
};

type FxRefreshResult = {
  effective_date: string;
  base_currency: string;
  created: number;
  updated: number;
  skipped_manual: number;
  failed: string[];
  message?: string | null;
};

export function FinanceFxRatesPanel() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    from_currency: 'USD',
    to_currency: 'INR',
    rate: '',
    effective_date: new Date().toISOString().slice(0, 10),
  });

  const currenciesQuery = useQuery({
    queryKey: ['finance-currencies'],
    queryFn: async () => (await apiClient.get<Currency[]>('/finance/currencies')).data,
  });
  const ratesQuery = useQuery({
    queryKey: ['finance-fx-rates'],
    queryFn: async () => (await apiClient.get<FxRate[]>('/finance/fx-rates')).data,
  });

  const createMutation = useMutation({
    mutationFn: async () =>
      (
        await apiClient.post('/finance/fx-rates', {
          from_currency: form.from_currency,
          to_currency: form.to_currency,
          rate: form.rate,
          effective_date: form.effective_date,
          source: 'manual',
        })
      ).data,
    onSuccess: () => {
      showSuccess('FX rate saved (new effective date — prior postings unchanged)');
      setForm((prev) => ({ ...prev, rate: '' }));
      void queryClient.invalidateQueries({ queryKey: ['finance-fx-rates'] });
    },
    onError: (error: unknown) => {
      showError(apiErrorMessage(error, 'Could not save FX rate'));
    },
  });

  const refreshMutation = useMutation({
    mutationFn: async () => {
      const q = form.effective_date
        ? `?on_date=${encodeURIComponent(form.effective_date)}`
        : '';
      return (await apiClient.post<FxRefreshResult>(`/finance/fx-rates/refresh${q}`)).data;
    },
    onSuccess: (data) => {
      showSuccess(data.message || `Live FX refreshed for ${data.effective_date}`);
      void queryClient.invalidateQueries({ queryKey: ['finance-fx-rates'] });
    },
    onError: (error: unknown) => {
      showError(apiErrorMessage(error, 'Could not refresh live FX rates'));
    },
  });

  const currencies = currenciesQuery.data ?? [];

  return (
    <Stack spacing={2}>
      <Box>
        <Typography variant="h6" sx={{ mb: 1 }}>
          FX rates
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Live rates are pulled automatically when you save a quote, expense, or commercial term —
          locked to that posting date. Refresh below to store today&apos;s market rates without
          rewriting prior months. Manual rows always win for the same date.
        </Typography>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} useFlexGap sx={{ flexWrap: 'wrap', mb: 2 }}>
          <Button
            variant="contained"
            color="secondary"
            disabled={refreshMutation.isPending}
            onClick={() => refreshMutation.mutate()}
          >
            {refreshMutation.isPending ? 'Refreshing…' : 'Refresh live rates'}
          </Button>
          <Typography variant="caption" color="text.secondary" sx={{ alignSelf: 'center' }}>
            Uses the effective date in the form (default today). Past dates use historical feed when available.
          </Typography>
        </Stack>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} useFlexGap sx={{ flexWrap: 'wrap' }}>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>From</InputLabel>
            <Select
              label="From"
              value={form.from_currency}
              onChange={(e) => setForm((p) => ({ ...p, from_currency: e.target.value }))}
            >
              {currencies.map((c) => (
                <MenuItem key={c.code} value={c.code}>
                  {c.code}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>To</InputLabel>
            <Select
              label="To"
              value={form.to_currency}
              onChange={(e) => setForm((p) => ({ ...p, to_currency: e.target.value }))}
            >
              {currencies.map((c) => (
                <MenuItem key={c.code} value={c.code}>
                  {c.code}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            size="small"
            label="Rate"
            value={form.rate}
            onChange={(e) => setForm((p) => ({ ...p, rate: e.target.value }))}
          />
          <TextField
            size="small"
            type="date"
            label="Effective date"
            value={form.effective_date}
            onChange={(e) => setForm((p) => ({ ...p, effective_date: e.target.value }))}
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <Button
            variant="outlined"
            disabled={!form.rate || !form.effective_date || createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            Add manual rate
          </Button>
        </Stack>
      </Box>
      <Stack spacing={1}>
        {(ratesQuery.data ?? []).slice(0, 20).map((row) => (
          <Card key={row.id} variant="outlined">
            <CardContent>
              <Typography sx={{ fontWeight: 600 }}>
                {row.from_currency} → {row.to_currency} = {row.rate}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Effective {row.effective_date}
                {row.source ? ` · ${row.source}` : ''}
              </Typography>
            </CardContent>
          </Card>
        ))}
      </Stack>
    </Stack>
  );
}
