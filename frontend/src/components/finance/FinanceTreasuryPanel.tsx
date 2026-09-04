import { useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  MenuItem,
  Stack,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import { LoadingState } from '../common/LoadingState';
import { KpiMetricCard } from '../ui/design-system/KpiMetricCard';
import AccountBalanceOutlinedIcon from '@mui/icons-material/AccountBalanceOutlined';
import AccountBalanceWalletOutlinedIcon from '@mui/icons-material/AccountBalanceWalletOutlined';
import SavingsOutlinedIcon from '@mui/icons-material/SavingsOutlined';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';
import { FinanceHeroBanner, FinanceSection, financeMoney } from './FinanceCockpitPrimitives';
import { FinanceCashForecastSection } from './FinanceCashForecastSection';
import { toFiniteNumber } from '../../utils/format';

type TreasurySummary = {
  cash: {
    available_cash?: number | string;
    bank_balance?: number | string;
    cash_balance?: number | string;
    as_of_date?: string | null;
    has_manual_position?: boolean;
  };
  debt: {
    loan_outstanding_principal?: number | string;
    loan_count?: number;
    od_sanctioned_limit?: number | string;
    od_utilized?: number | string;
    od_available?: number | string;
    od_utilization_percent?: number | string;
  };
  investments: {
    current_value?: number | string;
    amount_invested?: number | string;
    count?: number;
  };
  notes?: Record<string, string>;
};

type Loan = {
  id: string;
  name: string;
  lender_name: string;
  outstanding_principal: number | string;
  original_principal: number | string;
  currency_code: string;
  status: string;
  interest_paid_total?: number | string;
  repayments?: Array<{
    id: string;
    payment_date: string;
    total_amount: number | string;
    principal_amount: number | string;
    interest_amount: number | string;
  }>;
};

type OdFacility = {
  id: string;
  name: string;
  bank_name: string;
  sanctioned_limit: number | string;
  current_utilization: number | string;
  available_limit: number | string;
  utilization_percent: number | string;
  is_near_limit?: boolean;
  currency_code: string;
};

type Investment = {
  id: string;
  name: string;
  investment_type: string;
  amount_invested: number | string;
  current_value: number | string;
  income_received: number | string;
  currency_code: string;
  accounting_note?: string;
};

export function FinanceTreasuryPanel({ teamId = '' }: { teamId?: string }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [section, setSection] = useState(0);
  const [loanOpen, setLoanOpen] = useState(false);
  const [odOpen, setOdOpen] = useState(false);
  const [investOpen, setInvestOpen] = useState(false);
  const [repayLoanId, setRepayLoanId] = useState<string | null>(null);
  const [cashOpen, setCashOpen] = useState(false);

  const [loanForm, setLoanForm] = useState({
    lender_name: '',
    name: '',
    original_principal: '',
    interest_rate_percent: '',
  });
  const [odForm, setOdForm] = useState({
    bank_name: '',
    name: '',
    sanctioned_limit: '',
    current_utilization: '',
  });
  const [investForm, setInvestForm] = useState({
    name: '',
    investment_type: 'fixed_deposit',
    amount_invested: '',
    institution: '',
  });
  const [repayForm, setRepayForm] = useState({
    total_amount: '',
    interest_amount: '',
    payment_date: new Date().toISOString().slice(0, 10),
  });
  const [cashForm, setCashForm] = useState({
    bank_balance: '',
    cash_balance: '',
    as_of_date: new Date().toISOString().slice(0, 10),
  });

  const summaryQuery = useQuery({
    queryKey: ['finance-treasury-summary'],
    queryFn: async () => (await apiClient.get<TreasurySummary>('/finance/treasury/summary')).data,
  });
  const loansQuery = useQuery({
    queryKey: ['finance-treasury-loans'],
    queryFn: async () => (await apiClient.get<Loan[]>('/finance/treasury/loans')).data,
  });
  const odQuery = useQuery({
    queryKey: ['finance-treasury-od'],
    queryFn: async () => (await apiClient.get<OdFacility[]>('/finance/treasury/od-facilities')).data,
  });
  const investQuery = useQuery({
    queryKey: ['finance-treasury-investments'],
    queryFn: async () => (await apiClient.get<Investment[]>('/finance/treasury/investments')).data,
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['finance-treasury-summary'] });
    void queryClient.invalidateQueries({ queryKey: ['finance-treasury-loans'] });
    void queryClient.invalidateQueries({ queryKey: ['finance-treasury-od'] });
    void queryClient.invalidateQueries({ queryKey: ['finance-treasury-investments'] });
  };

  const createLoan = useMutation({
    mutationFn: async () =>
      (
        await apiClient.post('/finance/treasury/loans', {
          lender_name: loanForm.lender_name,
          name: loanForm.name,
          original_principal: Number(loanForm.original_principal),
          interest_rate_percent: loanForm.interest_rate_percent
            ? Number(loanForm.interest_rate_percent)
            : null,
        })
      ).data,
    onSuccess: () => {
      showSuccess('Loan added');
      setLoanOpen(false);
      setLoanForm({ lender_name: '', name: '', original_principal: '', interest_rate_percent: '' });
      invalidate();
    },
    onError: () => showError('Could not add loan'),
  });

  const createOd = useMutation({
    mutationFn: async () =>
      (
        await apiClient.post('/finance/treasury/od-facilities', {
          bank_name: odForm.bank_name,
          name: odForm.name,
          sanctioned_limit: Number(odForm.sanctioned_limit),
          current_utilization: Number(odForm.current_utilization || 0),
        })
      ).data,
    onSuccess: () => {
      showSuccess('OD facility added');
      setOdOpen(false);
      setOdForm({ bank_name: '', name: '', sanctioned_limit: '', current_utilization: '' });
      invalidate();
    },
    onError: () => showError('Could not add OD facility'),
  });

  const createInvest = useMutation({
    mutationFn: async () =>
      (
        await apiClient.post('/finance/treasury/investments', {
          name: investForm.name,
          investment_type: investForm.investment_type,
          institution: investForm.institution || null,
          amount_invested: Number(investForm.amount_invested),
        })
      ).data,
    onSuccess: () => {
      showSuccess('Investment added');
      setInvestOpen(false);
      setInvestForm({ name: '', investment_type: 'fixed_deposit', amount_invested: '', institution: '' });
      invalidate();
    },
    onError: () => showError('Could not add investment'),
  });

  const repayLoan = useMutation({
    mutationFn: async () => {
      const total = Number(repayForm.total_amount);
      const interest = Number(repayForm.interest_amount || 0);
      return (
        await apiClient.post(`/finance/treasury/loans/${repayLoanId}/repayments`, {
          payment_date: repayForm.payment_date,
          total_amount: total,
          interest_amount: interest,
          principal_amount: total - interest,
        })
      ).data;
    },
    onSuccess: () => {
      showSuccess('Repayment recorded (principal reduces debt; interest is finance cost)');
      setRepayLoanId(null);
      invalidate();
    },
    onError: () => showError('Could not record repayment'),
  });

  const saveCash = useMutation({
    mutationFn: async () =>
      (
        await apiClient.put('/finance/treasury/cash-position', {
          as_of_date: cashForm.as_of_date,
          bank_balance: Number(cashForm.bank_balance || 0),
          cash_balance: Number(cashForm.cash_balance || 0),
        })
      ).data,
    onSuccess: () => {
      showSuccess('Cash position saved');
      setCashOpen(false);
      invalidate();
    },
    onError: () => showError('Could not save cash position'),
  });

  const summary = summaryQuery.data;
  const currency = 'INR';

  const loading =
    summaryQuery.isLoading || loansQuery.isLoading || odQuery.isLoading || investQuery.isLoading;

  const repayPreview = useMemo(() => {
    const total = toFiniteNumber(repayForm.total_amount);
    const interest = toFiniteNumber(repayForm.interest_amount);
    return { principal: Math.max(0, total - interest), interest, total };
  }, [repayForm.total_amount, repayForm.interest_amount]);

  if (loading || !summary) {
    return <LoadingState message="Loading treasury…" />;
  }

  return (
    <Stack spacing={2.5}>
      <FinanceHeroBanner
        title="Treasury — cash, debt & investments"
        subtitle="Manual registers for loans, OD, investments, and cash. Loan/OD principal is financing position — not revenue or operating expense. Interest is finance cost. Investment purchases are cash + asset."
        chips={
          <>
            <Chip size="small" label="Manual entry" sx={{ fontWeight: 700 }} />
            <Chip size="small" variant="outlined" label="P&L ≠ cash ≠ debt" />
          </>
        }
      />

      <Grid container spacing={1.5}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Tooltip title="Bank + cash balances from the latest manual cash position.">
            <Box sx={{ height: '100%' }}>
              <KpiMetricCard
                title="Available cash"
                value={financeMoney(summary.cash.available_cash, currency)}
                subtitle={
                  summary.cash.has_manual_position
                    ? `As of ${summary.cash.as_of_date ?? '—'}`
                    : 'Set a cash position to track runway'
                }
                icon={AccountBalanceWalletOutlinedIcon}
                accent="primary"
                compact
                onClick={() => setCashOpen(true)}
              />
            </Box>
          </Tooltip>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Tooltip title={summary.notes?.loan_principal}>
            <Box sx={{ height: '100%' }}>
              <KpiMetricCard
                title="Loan principal outstanding"
                value={financeMoney(summary.debt.loan_outstanding_principal, currency)}
                subtitle={`${summary.debt.loan_count ?? 0} loan(s)`}
                icon={AccountBalanceOutlinedIcon}
                accent="warning"
                compact
              />
            </Box>
          </Tooltip>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Tooltip title={summary.notes?.od_utilization}>
            <Box sx={{ height: '100%' }}>
              <KpiMetricCard
                title="OD utilized"
                value={financeMoney(summary.debt.od_utilized, currency)}
                subtitle={`Available ${financeMoney(summary.debt.od_available, currency)} · ${toFiniteNumber(summary.debt.od_utilization_percent).toFixed(1)}%`}
                icon={WarningAmberOutlinedIcon}
                accent="error"
                compact
              />
            </Box>
          </Tooltip>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Tooltip title={summary.notes?.investments}>
            <Box sx={{ height: '100%' }}>
              <KpiMetricCard
                title="Investments (value)"
                value={financeMoney(summary.investments.current_value, currency)}
                subtitle={`Invested ${financeMoney(summary.investments.amount_invested, currency)}`}
                icon={SavingsOutlinedIcon}
                accent="success"
                compact
              />
            </Box>
          </Tooltip>
        </Grid>
      </Grid>

      <FinanceCashForecastSection teamId={teamId} currency={currency} />

      <Tabs value={section} onChange={(_, v) => setSection(v)} sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tab label="Loans" />
        <Tab label="Overdraft (OD)" />
        <Tab label="Investments" />
      </Tabs>

      {section === 0 && (
        <FinanceSection
          title="Loans"
          subtitle="Record repayments with principal + interest split. Cash outflow = total; P&L expense = interest only; debt reduction = principal."
          action={
            <Button variant="contained" size="small" onClick={() => setLoanOpen(true)}>
              + Add loan
            </Button>
          }
        >
          <Stack spacing={1.5}>
            {(loansQuery.data ?? []).map((loan) => (
              <Box key={loan.id} sx={{ p: 1.5, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                <Box
                  sx={{
                    display: 'flex',
                    flexDirection: { xs: 'column', sm: 'row' },
                    justifyContent: 'space-between',
                    gap: 1,
                  }}
                >
                  <Box>
                    <Typography sx={{ fontWeight: 700 }}>{loan.name}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {loan.lender_name} · Outstanding {financeMoney(loan.outstanding_principal, loan.currency_code)} · Interest paid{' '}
                      {financeMoney(loan.interest_paid_total, loan.currency_code)}
                    </Typography>
                  </Box>
                  <Button size="small" variant="outlined" onClick={() => setRepayLoanId(loan.id)}>
                    Record repayment
                  </Button>
                </Box>
              </Box>
            ))}
            {(loansQuery.data ?? []).length === 0 ? (
              <Typography color="text.secondary">No loans yet. Add a loan manually to track principal and interest.</Typography>
            ) : null}
          </Stack>
        </FinanceSection>
      )}

      {section === 1 && (
        <FinanceSection
          title="Overdraft facilities"
          subtitle="OD drawdown is financing/cash position — not revenue. Record OD interest separately as finance cost."
          action={
            <Button variant="contained" size="small" onClick={() => setOdOpen(true)}>
              + Add OD facility
            </Button>
          }
        >
          <Stack spacing={1.5}>
            {(odQuery.data ?? []).map((od) => (
              <Box key={od.id} sx={{ p: 1.5, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                <Typography sx={{ fontWeight: 700 }}>
                  {od.name} {od.is_near_limit ? <Chip size="small" color="warning" label="Near limit" sx={{ ml: 1 }} /> : null}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {od.bank_name} · Limit {financeMoney(od.sanctioned_limit, od.currency_code)} · Used{' '}
                  {financeMoney(od.current_utilization, od.currency_code)} · Available{' '}
                  {financeMoney(od.available_limit, od.currency_code)} ({toFiniteNumber(od.utilization_percent).toFixed(1)}%)
                </Typography>
              </Box>
            ))}
            {(odQuery.data ?? []).length === 0 ? (
              <Typography color="text.secondary">No OD facilities yet.</Typography>
            ) : null}
          </Stack>
        </FinanceSection>
      )}

      {section === 2 && (
        <FinanceSection
          title="Investments"
          subtitle="Purchase reduces cash and increases investment value — not automatic OpEx."
          action={
            <Button variant="contained" size="small" onClick={() => setInvestOpen(true)}>
              + Add investment
            </Button>
          }
        >
          <Stack spacing={1.5}>
            {(investQuery.data ?? []).map((inv) => (
              <Box key={inv.id} sx={{ p: 1.5, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                <Typography sx={{ fontWeight: 700 }}>{inv.name}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {inv.investment_type} · Invested {financeMoney(inv.amount_invested, inv.currency_code)} · Value{' '}
                  {financeMoney(inv.current_value, inv.currency_code)} · Income {financeMoney(inv.income_received, inv.currency_code)}
                </Typography>
              </Box>
            ))}
            {(investQuery.data ?? []).length === 0 ? (
              <Typography color="text.secondary">No investments yet.</Typography>
            ) : null}
          </Stack>
        </FinanceSection>
      )}

      <Dialog open={loanOpen} onClose={() => setLoanOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Add loan</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="Lender" value={loanForm.lender_name} onChange={(e) => setLoanForm({ ...loanForm, lender_name: e.target.value })} required />
            <TextField label="Loan name" value={loanForm.name} onChange={(e) => setLoanForm({ ...loanForm, name: e.target.value })} required />
            <TextField label="Original principal" type="number" value={loanForm.original_principal} onChange={(e) => setLoanForm({ ...loanForm, original_principal: e.target.value })} required />
            <TextField label="Interest rate %" type="number" value={loanForm.interest_rate_percent} onChange={(e) => setLoanForm({ ...loanForm, interest_rate_percent: e.target.value })} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setLoanOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={() => createLoan.mutate()} disabled={!loanForm.lender_name || !loanForm.name || !loanForm.original_principal}>
            Save
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={odOpen} onClose={() => setOdOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Add OD facility</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="Bank" value={odForm.bank_name} onChange={(e) => setOdForm({ ...odForm, bank_name: e.target.value })} required />
            <TextField label="Facility name" value={odForm.name} onChange={(e) => setOdForm({ ...odForm, name: e.target.value })} required />
            <TextField label="Sanctioned limit" type="number" value={odForm.sanctioned_limit} onChange={(e) => setOdForm({ ...odForm, sanctioned_limit: e.target.value })} required />
            <TextField label="Current utilization" type="number" value={odForm.current_utilization} onChange={(e) => setOdForm({ ...odForm, current_utilization: e.target.value })} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOdOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={() => createOd.mutate()} disabled={!odForm.bank_name || !odForm.name || !odForm.sanctioned_limit}>
            Save
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={investOpen} onClose={() => setInvestOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Add investment</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="Name" value={investForm.name} onChange={(e) => setInvestForm({ ...investForm, name: e.target.value })} required />
            <TextField select label="Type" value={investForm.investment_type} onChange={(e) => setInvestForm({ ...investForm, investment_type: e.target.value })}>
              <MenuItem value="fixed_deposit">Fixed deposit</MenuItem>
              <MenuItem value="mutual_fund">Mutual fund</MenuItem>
              <MenuItem value="bond">Bond</MenuItem>
              <MenuItem value="other">Other</MenuItem>
            </TextField>
            <TextField label="Institution" value={investForm.institution} onChange={(e) => setInvestForm({ ...investForm, institution: e.target.value })} />
            <TextField label="Amount invested" type="number" value={investForm.amount_invested} onChange={(e) => setInvestForm({ ...investForm, amount_invested: e.target.value })} required />
            <Typography variant="caption" color="text.secondary">
              This is recorded as an investment asset, not an operating expense.
            </Typography>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setInvestOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={() => createInvest.mutate()} disabled={!investForm.name || !investForm.amount_invested}>
            Save
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(repayLoanId)} onClose={() => setRepayLoanId(null)} fullWidth maxWidth="sm">
        <DialogTitle>Record loan repayment</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Payment date"
              type="date"
              slotProps={{ inputLabel: { shrink: true } }}
              value={repayForm.payment_date}
              onChange={(e) => setRepayForm({ ...repayForm, payment_date: e.target.value })}
            />
            <TextField label="Total payment (cash outflow)" type="number" value={repayForm.total_amount} onChange={(e) => setRepayForm({ ...repayForm, total_amount: e.target.value })} />
            <TextField label="Interest portion (P&L finance cost)" type="number" value={repayForm.interest_amount} onChange={(e) => setRepayForm({ ...repayForm, interest_amount: e.target.value })} />
            <Typography variant="body2">
              Principal (debt reduction): {financeMoney(repayPreview.principal, currency)}
            </Typography>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRepayLoanId(null)}>Cancel</Button>
          <Button variant="contained" onClick={() => repayLoan.mutate()} disabled={!repayForm.total_amount}>
            Save repayment
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={cashOpen} onClose={() => setCashOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Set cash position</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="As of date"
              type="date"
              slotProps={{ inputLabel: { shrink: true } }}
              value={cashForm.as_of_date}
              onChange={(e) => setCashForm({ ...cashForm, as_of_date: e.target.value })}
            />
            <TextField label="Bank balance" type="number" value={cashForm.bank_balance} onChange={(e) => setCashForm({ ...cashForm, bank_balance: e.target.value })} />
            <TextField label="Cash balance" type="number" value={cashForm.cash_balance} onChange={(e) => setCashForm({ ...cashForm, cash_balance: e.target.value })} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCashOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={() => saveCash.mutate()}>
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
