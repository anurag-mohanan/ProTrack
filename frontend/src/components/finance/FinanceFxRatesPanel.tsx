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

type Currency = { code: string; name: string; symbol?: string | null; is_base?: boolean };
type FxRate = {
  id: string;
  from_currency: string;
  to_currency: string;
  rate: number;
  effective_date: string;
  source?: string;
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
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      showError(error.response?.data?.detail ?? 'Could not save FX rate');
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
          Enter a rate with an effective date on or before the expense / commercial term date.
          Overview always uses the INR amount stored when each row was saved — updating FX later
          does not rewrite prior months.
        </Typography>
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
            variant="contained"
            disabled={!form.rate || !form.effective_date || createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            Add rate
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
