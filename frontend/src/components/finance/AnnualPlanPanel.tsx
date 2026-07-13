import { useMemo, useState } from 'react';
import {
  Button,
  Card,
  CardContent,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import { formatIndianNumber } from '../../utils/format';
import { LoadingState } from '../common/LoadingState';

const MONTH_KEYS = [
  'month_01',
  'month_02',
  'month_03',
  'month_04',
  'month_05',
  'month_06',
  'month_07',
  'month_08',
  'month_09',
  'month_10',
  'month_11',
  'month_12',
] as const;

const MONTH_LABELS = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar'];

/** Indian FY starts in April — return the calendar year of the current FY's April. */
export function currentFyStartYear(now = new Date()): number {
  const year = now.getFullYear();
  const month = now.getMonth() + 1;
  return month >= 4 ? year : year - 1;
}

function fyLabelFromStartYear(startYear: number): string {
  return `${startYear}-${String(startYear + 1).slice(-2)}`;
}

type PlanListItem = {
  id: string;
  name: string;
  fiscal_year_label: string;
  currency_code: string;
  tax_percent: number;
  provision_percent: number;
  status: string;
};

type PlanLine = {
  id: string;
  section: 'sales' | 'expenses' | 'resources' | 'capex';
  code: string;
  label: string;
  month_01: number;
  month_02: number;
  month_03: number;
  month_04: number;
  month_05: number;
  month_06: number;
  month_07: number;
  month_08: number;
  month_09: number;
  month_10: number;
  month_11: number;
  month_12: number;
};

type PlanDetail = PlanListItem & {
  lines: PlanLine[];
  summary: {
    sales_fy: string;
    expenses_fy: string;
    gain_loss: string;
    after_tax: string;
    provision_amount: string;
    gain_loss_after_provision: string;
    tax_percent: string;
    provision_percent: string;
  };
  line_totals: Record<string, string>;
};

function lineTotal(line: PlanLine): number {
  return MONTH_KEYS.reduce((sum, key) => sum + Number(line[key] || 0), 0);
}

function PlanSectionGrid({
  title,
  lines,
  onCellBlur,
}: {
  title: string;
  lines: PlanLine[];
  onCellBlur: (lineId: string, field: (typeof MONTH_KEYS)[number], value: string) => void;
}) {
  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="h6" sx={{ mb: 1.5 }}>
          {title}
        </Typography>
        <TableContainer sx={{ overflowX: 'auto' }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ minWidth: 140 }}>Line</TableCell>
                {MONTH_LABELS.map((label) => (
                  <TableCell key={label} align="right" sx={{ minWidth: 88 }}>
                    {label}
                  </TableCell>
                ))}
                <TableCell align="right" sx={{ minWidth: 100, fontWeight: 700 }}>
                  Total
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {lines.map((line) => (
                <TableRow key={line.id}>
                  <TableCell>{line.label}</TableCell>
                  {MONTH_KEYS.map((key) => (
                    <TableCell key={key} align="right" sx={{ p: 0.5 }}>
                      <TextField
                        size="small"
                        defaultValue={Number(line[key] || 0)}
                        slotProps={{
                          htmlInput: { style: { textAlign: 'right' } },
                        }}
                        onBlur={(event) => onCellBlur(line.id, key, event.target.value)}
                      />
                    </TableCell>
                  ))}
                  <TableCell align="right" sx={{ fontWeight: 600 }}>
                    {formatIndianNumber(lineTotal(line))}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </CardContent>
    </Card>
  );
}

export function AnnualPlanPanel() {
  const { showError, showSuccess } = useToast();
  const queryClient = useQueryClient();
  const [selectedPlanId, setSelectedPlanId] = useState<string>('');
  const [createOpen, setCreateOpen] = useState(false);
  const defaultFyStart = currentFyStartYear();
  const [newName, setNewName] = useState(`FY ${fyLabelFromStartYear(defaultFyStart)}`);
  const [newYear, setNewYear] = useState(defaultFyStart);
  const [taxPercent, setTaxPercent] = useState('30');
  const [provisionPercent, setProvisionPercent] = useState('20');

  const plansQuery = useQuery({
    queryKey: ['finance-plans'],
    queryFn: async () => (await apiClient.get<PlanListItem[]>('/finance/plans')).data,
  });

  const activePlanId = selectedPlanId || plansQuery.data?.[0]?.id || '';

  const detailQuery = useQuery({
    queryKey: ['finance-plan', activePlanId],
    enabled: Boolean(activePlanId),
    queryFn: async () => (await apiClient.get<PlanDetail>(`/finance/plans/${activePlanId}`)).data,
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['finance-plans'] });
    void queryClient.invalidateQueries({ queryKey: ['finance-plan', activePlanId] });
  };

  const createMutation = useMutation({
    mutationFn: async () =>
      (
        await apiClient.post<PlanDetail>('/finance/plans', {
          name: newName,
          fiscal_year_start_year: newYear,
          fy_start_month: 4,
          tax_percent: Number(taxPercent),
          provision_percent: Number(provisionPercent),
        })
      ).data,
    onSuccess: (plan) => {
      showSuccess(`Created plan FY ${plan.fiscal_year_label}`);
      setSelectedPlanId(plan.id);
      setCreateOpen(false);
      invalidate();
    },
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      showError(error.response?.data?.detail ?? 'Could not create plan');
    },
  });

  const settingsMutation = useMutation({
    mutationFn: async () =>
      (
        await apiClient.patch(`/finance/plans/${activePlanId}`, {
          tax_percent: Number(taxPercent),
          provision_percent: Number(provisionPercent),
        })
      ).data,
    onSuccess: () => {
      showSuccess('Plan settings saved');
      invalidate();
    },
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      showError(error.response?.data?.detail ?? 'Could not save settings');
    },
  });

  const cellMutation = useMutation({
    mutationFn: async (payload: {
      lineId: string;
      field: (typeof MONTH_KEYS)[number];
      value: number;
    }) =>
      apiClient.put(`/finance/plans/${activePlanId}/lines/${payload.lineId}`, {
        [payload.field]: payload.value,
      }),
    onSuccess: () => invalidate(),
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      showError(error.response?.data?.detail ?? 'Could not update cell');
    },
  });

  const salesLines = useMemo(
    () => (detailQuery.data?.lines ?? []).filter((line: PlanLine) => line.section === 'sales'),
    [detailQuery.data],
  );
  const expenseLines = useMemo(
    () => (detailQuery.data?.lines ?? []).filter((line: PlanLine) => line.section === 'expenses'),
    [detailQuery.data],
  );

  if (plansQuery.isLoading) return <LoadingState message="Loading annual plans…" />;

  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        Enter Sales and Expenses manually for the Apr–Mar fiscal year. There is no file import on
        this tab — type monthly amounts into the grids (defaults to the FY that started this April).
      </Typography>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        spacing={1.5}
        sx={{ alignItems: { sm: 'center' } }}
      >
        <FormControl size="small" sx={{ minWidth: 220 }}>
          <InputLabel id="plan-select">Fiscal year plan</InputLabel>
          <Select
            labelId="plan-select"
            label="Fiscal year plan"
            value={activePlanId}
            onChange={(event) => {
              setSelectedPlanId(event.target.value);
              const plan = plansQuery.data?.find((row: PlanListItem) => row.id === event.target.value);
              if (plan) {
                setTaxPercent(String(plan.tax_percent));
                setProvisionPercent(String(plan.provision_percent));
              }
            }}
          >
            {(plansQuery.data ?? []).map((plan: PlanListItem) => (
              <MenuItem key={plan.id} value={plan.id}>
                FY {plan.fiscal_year_label} — {plan.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Button
          variant="contained"
          onClick={() => {
            const fy = currentFyStartYear();
            setNewYear(fy);
            setNewName(`FY ${fyLabelFromStartYear(fy)}`);
            setCreateOpen(true);
          }}
        >
          Create Plan
        </Button>
      </Stack>

      {!activePlanId ? (
        <Typography color="text.secondary">
          No plan yet for this year. Click <strong>Create Plan</strong> for FY{' '}
          {fyLabelFromStartYear(currentFyStartYear())} (April {currentFyStartYear()} – March{' '}
          {currentFyStartYear() + 1}), then type monthly Sales and Expenses by hand.
        </Typography>
      ) : detailQuery.isLoading ? (
        <LoadingState message="Loading plan…" />
      ) : detailQuery.data ? (
        <>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle1" sx={{ mb: 1.5, fontWeight: 600 }}>
                Settings (FY {detailQuery.data.fiscal_year_label})
              </Typography>
              <Stack
                direction={{ xs: 'column', sm: 'row' }}
                spacing={1.5}
                sx={{ alignItems: { sm: 'center' } }}
              >
                <TextField
                  size="small"
                  label="Tax %"
                  value={taxPercent}
                  onChange={(event) => setTaxPercent(event.target.value)}
                  sx={{ width: 120 }}
                />
                <TextField
                  size="small"
                  label="Provision %"
                  value={provisionPercent}
                  onChange={(event) => setProvisionPercent(event.target.value)}
                  sx={{ width: 140 }}
                />
                <Button
                  variant="outlined"
                  onClick={() => settingsMutation.mutate()}
                  disabled={settingsMutation.isPending}
                >
                  Save settings
                </Button>
              </Stack>
            </CardContent>
          </Card>

          <PlanSectionGrid
            title="Sales"
            lines={salesLines}
            onCellBlur={(lineId, field, value) => {
              const numeric = Number(String(value).replace(/,/g, ''));
              if (Number.isNaN(numeric)) {
                showError('Enter a valid number');
                return;
              }
              cellMutation.mutate({ lineId, field, value: numeric });
            }}
          />
          <PlanSectionGrid
            title="Expenses"
            lines={expenseLines}
            onCellBlur={(lineId, field, value) => {
              const numeric = Number(String(value).replace(/,/g, ''));
              if (Number.isNaN(numeric)) {
                showError('Enter a valid number');
                return;
              }
              cellMutation.mutate({ lineId, field, value: numeric });
            }}
          />

          <Card variant="outlined">
            <CardContent>
              <Typography variant="h6" sx={{ mb: 1.5 }}>
                Summary (computed)
              </Typography>
              <Grid container spacing={1.5}>
                {[
                  ['Sales (FY)', detailQuery.data.summary.sales_fy],
                  ['Expenses (FY)', detailQuery.data.summary.expenses_fy],
                  ['GAIN/LOSS', detailQuery.data.summary.gain_loss],
                  [`After ${detailQuery.data.summary.tax_percent}% tax`, detailQuery.data.summary.after_tax],
                  [
                    `${detailQuery.data.summary.provision_percent}% provision`,
                    detailQuery.data.summary.provision_amount,
                  ],
                  ['GAIN/LOSS after provision', detailQuery.data.summary.gain_loss_after_provision],
                ].map(([label, value]) => (
                  <Grid key={label} size={{ xs: 12, sm: 6, md: 4 }}>
                    <Typography variant="body2" color="text.secondary">
                      {label}
                    </Typography>
                    <Typography variant="h6">{formatIndianNumber(value)}</Typography>
                  </Grid>
                ))}
              </Grid>
            </CardContent>
          </Card>
        </>
      ) : null}

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>Create annual plan</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Name"
              value={newName}
              onChange={(event) => setNewName(event.target.value)}
              fullWidth
            />
            <TextField
              label="FY start year (April)"
              type="number"
              value={newYear}
              onChange={(event) => {
                const year = Number(event.target.value);
                setNewYear(year);
                setNewName(`FY ${fyLabelFromStartYear(year)}`);
              }}
              helperText={`Creates FY ${fyLabelFromStartYear(newYear)} — months Apr ${newYear} through Mar ${newYear + 1}. Enter figures manually after create.`}
              fullWidth
            />
            <TextField
              label="Tax %"
              value={taxPercent}
              onChange={(event) => setTaxPercent(event.target.value)}
            />
            <TextField
              label="Provision %"
              value={provisionPercent}
              onChange={(event) => setProvisionPercent(event.target.value)}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending}
          >
            Create
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
