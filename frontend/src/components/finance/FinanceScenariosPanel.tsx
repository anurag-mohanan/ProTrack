import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  Grid,
  IconButton,
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
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ContentCopyOutlinedIcon from '@mui/icons-material/ContentCopyOutlined';
import DeleteOutlinedIcon from '@mui/icons-material/DeleteOutlined';
import FolderOpenOutlinedIcon from '@mui/icons-material/FolderOpenOutlined';
import GroupsOutlinedIcon from '@mui/icons-material/GroupsOutlined';
import AccountBalanceWalletOutlinedIcon from '@mui/icons-material/AccountBalanceWalletOutlined';
import PaymentsOutlinedIcon from '@mui/icons-material/PaymentsOutlined';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import SaveOutlinedIcon from '@mui/icons-material/SaveOutlined';
import ScienceOutlinedIcon from '@mui/icons-material/ScienceOutlined';
import ShowChartOutlinedIcon from '@mui/icons-material/ShowChartOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { fetchWorkingModels } from '../../api/lookups';
import { designTokens } from '../../theme/designTokens';
import { toFiniteNumber } from '../../utils/format';
import {
  clearDraft,
  computeScenario,
  draftPayload,
  emptyDraft,
  loadDraft,
  lookupFxRateToBase,
  newId,
  newTeamId,
  newTeamMonthlyRevenue,
  newTeamMonthlyRevenueNative,
  newTeamOpexMonthly,
  normalizeNewTeamOpexLines,
  NEW_TEAM_OPEX_CATEGORIES,
  saveDraft,
  yearlyToMonthly,
  type FacilityLine,
  type HireLine,
  type ManagementHireLine,
  type NewTeamLine,
  type NewTeamOpexCategory,
  type NewTeamOpexLine,
  type ScenarioBaseline,
  type ScenarioDraft,
  type SoftwareLine,
} from '../../utils/financeScenarios';
import { LoadingState } from '../common/LoadingState';
import { KpiMetricCard } from '../ui/design-system/KpiMetricCard';
import {
  FinanceHeroBanner,
  FinanceSection,
  financeMoney,
} from './FinanceCockpitPrimitives';
import { teamQueryParam } from './FinanceTeamFilter';

type DashTeam = {
  team_id: string;
  team_name: string;
  is_overhead_home?: boolean;
  planning_revenue_signal_inr?: number | string;
  monthly_revenue_signal_inr?: number | string;
  direct_operating_cost_inr?: number | string;
  allocated_overhead_inr?: number | string;
  monthly_operating_cost_inr?: number | string;
  net_profit_inr?: number | string;
  billable_resource_count?: number;
  estimated_cost_inr?: number | string;
  month_estimated_cost_inr?: number | string;
};

type FinanceDashboard = {
  base_currency: string;
  cost: Record<string, number | string>;
  profitability: Record<string, number | string>;
  salary_cost_inr?: number;
  overhead?: {
    overhead_pool_monthly_inr?: number | string;
    overhead_cost_per_resource_inr?: number | string;
    billable_resource_count?: number;
    overhead_management_salary_inr?: number | string;
    overhead_salary_inr?: number | string;
    overhead_opex_inr?: number | string;
    overhead_capex_inr?: number | string;
    management_team_name?: string;
    corporate_team_name?: string;
  };
  by_team?: DashTeam[];
};

type SavedScenarioListItem = {
  id: string;
  name: string;
  description?: string | null;
  scenario_type: string;
  status: string;
  baseline_as_of: string;
  updated_at: string;
};

type SavedScenario = SavedScenarioListItem & {
  payload: ScenarioDraft;
};

type CompareSummary = {
  scenario_id: string;
  name: string;
  simulated_pool: number | string;
  simulated_cpr: number | string;
  company_simulated_operating: number | string;
  delta_company_operating: number | string;
  total_simulated_net: number | string;
};

function baselineFromDashboard(data: FinanceDashboard): ScenarioBaseline {
  const teams = (data.by_team ?? []).map((row) => ({
    team_id: row.team_id,
    team_name: row.team_name,
    is_overhead_home: Boolean(row.is_overhead_home),
    revenue:
      toFiniteNumber(row.monthly_revenue_signal_inr) ||
      toFiniteNumber(row.planning_revenue_signal_inr),
    direct_operating: toFiniteNumber(row.direct_operating_cost_inr),
    allocated_overhead: toFiniteNumber(row.allocated_overhead_inr),
    operating: toFiniteNumber(row.monthly_operating_cost_inr),
    net_profit: toFiniteNumber(row.net_profit_inr),
    billable_fte: Number(row.billable_resource_count) || 0,
    estimated_cost:
      toFiniteNumber(row.month_estimated_cost_inr) || toFiniteNumber(row.estimated_cost_inr),
  }));

  return {
    overhead_pool: toFiniteNumber(
      data.overhead?.overhead_pool_monthly_inr ?? data.cost.overhead_pool_monthly_inr,
    ),
    billable_fte: Number(data.overhead?.billable_resource_count) || 0,
    cpr: toFiniteNumber(
      data.overhead?.overhead_cost_per_resource_inr ?? data.cost.overhead_cost_per_resource_inr,
    ),
    company_operating: toFiniteNumber(data.cost.monthly_operating_cost),
    corporate_tax_percent: toFiniteNumber(data.profitability.corporate_tax_percent) || 30,
    teams,
    overhead_breakdown: {
      management_salary:
        toFiniteNumber(data.overhead?.overhead_management_salary_inr) ||
        toFiniteNumber(data.overhead?.overhead_salary_inr),
      shared_opex: toFiniteNumber(data.overhead?.overhead_opex_inr),
      shared_capex: toFiniteNumber(data.overhead?.overhead_capex_inr),
      management_team_name:
        data.overhead?.management_team_name || data.overhead?.corporate_team_name,
    },
  };
}

function numField(
  label: string,
  value: number,
  onChange: (n: number) => void,
  width = 160,
) {
  return (
    <TextField
      size="small"
      label={label}
      value={value === 0 ? '' : String(value)}
      onChange={(event) => {
        const raw = String(event.target.value).replace(/,/g, '');
        if (raw.trim() === '') {
          onChange(0);
          return;
        }
        const next = Number(raw);
        onChange(Number.isFinite(next) ? next : 0);
      }}
      sx={{ width }}
      slotProps={{ htmlInput: { inputMode: 'decimal' } }}
    />
  );
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function FinanceScenariosPanel({ teamId }: { teamId: string }) {
  const q = teamQueryParam(teamId);
  const queryClient = useQueryClient();
  const [panelView, setPanelView] = useState<'workbench' | 'saved'>('workbench');
  const [draft, setDraft] = useState<ScenarioDraft>(() => loadDraft() ?? emptyDraft());
  const [activeScenarioId, setActiveScenarioId] = useState<string | null>(null);
  const [activeScenarioName, setActiveScenarioName] = useState<string | null>(null);
  const [baselineAsOf, setBaselineAsOf] = useState<string>(todayIso());
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [saveAsNew, setSaveAsNew] = useState(false);
  const [compareA, setCompareA] = useState('');
  const [compareB, setCompareB] = useState('');

  const dashboardQuery = useQuery({
    queryKey: ['finance-dashboard', teamId || 'all'],
    queryFn: async () => (await apiClient.get<FinanceDashboard>(`/finance/dashboard${q}`)).data,
  });

  const workingModelsQuery = useQuery({
    queryKey: ['lookup-working-models'],
    queryFn: fetchWorkingModels,
  });

  const currenciesQuery = useQuery({
    queryKey: ['finance-currencies'],
    queryFn: async () =>
      (await apiClient.get<Array<{ code: string; name: string }>>('/finance/currencies')).data,
  });

  const fxRatesQuery = useQuery({
    queryKey: ['finance-fx-rates'],
    queryFn: async () =>
      (
        await apiClient.get<
          Array<{
            from_currency: string;
            to_currency: string;
            rate: number | string;
            effective_date?: string;
          }>
        >('/finance/fx-rates')
      ).data,
  });

  const savedListQuery = useQuery({
    queryKey: ['finance-planning-scenarios'],
    queryFn: async () =>
      (await apiClient.get<SavedScenarioListItem[]>('/finance/planning-scenarios')).data,
  });

  const compareQuery = useQuery({
    queryKey: ['finance-planning-scenarios-compare', compareA, compareB, teamId],
    enabled: Boolean(compareA && compareB && compareA !== compareB),
    queryFn: async () =>
      (
        await apiClient.post<{
          scenario_a: CompareSummary;
          scenario_b: CompareSummary;
        }>('/finance/planning-scenarios/compare', {
          scenario_id_a: compareA,
          scenario_id_b: compareB,
          team_id: teamId || null,
        })
      ).data,
  });

  useEffect(() => {
    saveDraft(draft);
  }, [draft]);

  const saveMutation = useMutation({
    mutationFn: async (payload: {
      name: string;
      id?: string | null;
      asNew: boolean;
    }) => {
      const body = {
        name: payload.name,
        baseline_as_of: todayIso(),
        payload: draftPayload(draft),
      };
      if (payload.id && !payload.asNew) {
        return (
          await apiClient.patch<SavedScenario>(`/finance/planning-scenarios/${payload.id}`, body)
        ).data;
      }
      return (await apiClient.post<SavedScenario>('/finance/planning-scenarios', body)).data;
    },
    onSuccess: (row) => {
      setActiveScenarioId(row.id);
      setActiveScenarioName(row.name);
      setBaselineAsOf(row.baseline_as_of);
      queryClient.invalidateQueries({ queryKey: ['finance-planning-scenarios'] });
      setSaveOpen(false);
    },
  });

  const cloneMutation = useMutation({
    mutationFn: async (id: string) =>
      (await apiClient.post<SavedScenario>(`/finance/planning-scenarios/${id}/clone`)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['finance-planning-scenarios'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/finance/planning-scenarios/${id}`);
    },
    onSuccess: (_, id) => {
      if (activeScenarioId === id) {
        setActiveScenarioId(null);
        setActiveScenarioName(null);
      }
      queryClient.invalidateQueries({ queryKey: ['finance-planning-scenarios'] });
    },
  });

  const data = dashboardQuery.data;
  const currency = data?.base_currency ?? 'INR';
  const workingModels = workingModelsQuery.data ?? [];
  const currencyOptions = currenciesQuery.data?.length
    ? currenciesQuery.data
    : [{ code: 'INR', name: 'Indian Rupee' }, { code: 'USD', name: 'US Dollar' }, { code: 'EUR', name: 'Euro' }];
  const fxRates = fxRatesQuery.data ?? [];

  const resolveRevenueFx = (code: string): { rate: number; missing: boolean } => {
    const looked = lookupFxRateToBase(fxRates, code, currency);
    if (looked == null) {
      return { rate: code.toUpperCase() === currency.toUpperCase() ? 1 : 1, missing: code.toUpperCase() !== currency.toUpperCase() };
    }
    return { rate: looked, missing: false };
  };

  const setNewTeamRevenueCurrency = (teamRowId: string, code: string) => {
    const { rate } = resolveRevenueFx(code);
    setDraft((d) => ({
      ...d,
      new_teams: d.new_teams.map((t) =>
        t.id === teamRowId
          ? {
              ...t,
              revenue_currency_code: code.toUpperCase(),
              revenue_fx_rate_to_base: rate,
            }
          : t,
      ),
    }));
  };

  useEffect(() => {
    if (!fxRatesQuery.data?.length) return;
    setDraft((d) => {
      let changed = false;
      const next = d.new_teams.map((t) => {
        const code = (t.revenue_currency_code || currency).toUpperCase();
        const looked = lookupFxRateToBase(fxRatesQuery.data!, code, currency);
        if (looked == null) return { ...t, revenue_currency_code: code };
        if (
          (t.revenue_currency_code || '').toUpperCase() === code &&
          Number(t.revenue_fx_rate_to_base) === looked
        ) {
          return t;
        }
        changed = true;
        return {
          ...t,
          revenue_currency_code: code,
          revenue_fx_rate_to_base: looked,
        };
      });
      return changed ? { ...d, new_teams: next } : d;
    });
  }, [fxRatesQuery.data, currency]);

  const baseline = useMemo(
    () => (data ? baselineFromDashboard(data) : null),
    [data],
  );

  const deliveryTeams = useMemo(
    () => (baseline?.teams ?? []).filter((t) => !t.is_overhead_home),
    [baseline],
  );

  const teamOptions = useMemo(
    () => [
      ...deliveryTeams.map((t) => ({ id: t.team_id, name: t.team_name })),
      ...draft.new_teams.map((t) => ({ id: t.id, name: t.name || 'New team' })),
    ],
    [deliveryTeams, draft.new_teams],
  );

  const overheadForCalc = useMemo(() => {
    const o = draft.overhead;
    return {
      extra_hq_salary_monthly: o.extra_hq_salary_monthly,
      extra_shared_opex_monthly: draft.opex_yearly
        ? yearlyToMonthly(o.extra_shared_opex_monthly)
        : o.extra_shared_opex_monthly,
      extra_shared_capex_monthly: draft.capex_yearly
        ? yearlyToMonthly(o.extra_shared_capex_monthly)
        : o.extra_shared_capex_monthly,
    };
  }, [draft]);

  const result = useMemo(() => {
    if (!baseline) return null;
    return computeScenario(baseline, overheadForCalc, draft.expansion, {
      new_teams: draft.new_teams,
      management_hires: draft.management_hires,
      facility_lines: draft.facility_lines,
    });
  }, [baseline, overheadForCalc, draft]);

  const staleBaseline =
    activeScenarioId && baselineAsOf && baselineAsOf < todayIso();

  const reset = () => {
    clearDraft();
    setDraft(emptyDraft());
    setActiveScenarioId(null);
    setActiveScenarioName(null);
    setBaselineAsOf(todayIso());
  };

  const loadScenario = async (id: string) => {
    const row = (await apiClient.get<SavedScenario>(`/finance/planning-scenarios/${id}`)).data;
    const teams = (row.payload.new_teams ?? []).map((t) => {
      const code = (t.revenue_currency_code || currency).toUpperCase();
      const looked = lookupFxRateToBase(fxRates, code, currency);
      return {
        ...t,
        revenue_currency_code: code,
        revenue_fx_rate_to_base:
          Number(t.revenue_fx_rate_to_base) > 0
            ? Number(t.revenue_fx_rate_to_base)
            : looked ?? 1,
        opex_lines: normalizeNewTeamOpexLines(t),
      };
    });
    setDraft({
      ...emptyDraft(),
      ...row.payload,
      overhead: { ...emptyDraft().overhead, ...row.payload.overhead },
      expansion: {
        hires: row.payload.expansion?.hires ?? [],
        software: row.payload.expansion?.software ?? [],
      },
      new_teams: teams,
      management_hires: row.payload.management_hires ?? [],
      facility_lines: row.payload.facility_lines ?? [],
      opex_yearly: Boolean(row.payload.opex_yearly),
      capex_yearly: Boolean(row.payload.capex_yearly),
    });
    setActiveScenarioId(row.id);
    setActiveScenarioName(row.name);
    setBaselineAsOf(row.baseline_as_of);
    setPanelView('workbench');
  };

  const openSave = (asNew: boolean) => {
    setSaveAsNew(asNew);
    setSaveName(asNew ? '' : activeScenarioName ?? '');
    setSaveOpen(true);
  };

  const addNewTeam = () => {
    const { rate } = resolveRevenueFx(currency);
    const row: NewTeamLine = {
      id: newTeamId(),
      name: 'New delivery team',
      working_model_code: 'retainer',
      revenue_mode: 'expected_revenue',
      fixed_fee_amount: 0,
      fixed_fee_period: 'monthly',
      expected_monthly_revenue: 0,
      opex_lines: [],
      revenue_currency_code: currency,
      revenue_fx_rate_to_base: rate,
      delivery_headcount: 1,
      salary_monthly_each: 0,
      billable: true,
    };
    setDraft((d) => ({ ...d, new_teams: [...d.new_teams, row] }));
  };

  const addNewTeamOpex = (teamRowId: string) => {
    const line: NewTeamOpexLine = {
      id: newId(),
      category: 'software_license',
      label: '',
      amount_monthly: 0,
    };
    setDraft((d) => ({
      ...d,
      new_teams: d.new_teams.map((t) =>
        t.id === teamRowId
          ? { ...t, opex_lines: [...(t.opex_lines ?? []), line] }
          : t,
      ),
    }));
  };

  const updateNewTeamOpex = (
    teamRowId: string,
    lineId: string,
    patch: Partial<NewTeamOpexLine>,
  ) => {
    setDraft((d) => ({
      ...d,
      new_teams: d.new_teams.map((t) =>
        t.id === teamRowId
          ? {
              ...t,
              opex_lines: (t.opex_lines ?? []).map((line) =>
                line.id === lineId ? { ...line, ...patch } : line,
              ),
            }
          : t,
      ),
    }));
  };

  const removeNewTeamOpex = (teamRowId: string, lineId: string) => {
    setDraft((d) => ({
      ...d,
      new_teams: d.new_teams.map((t) =>
        t.id === teamRowId
          ? { ...t, opex_lines: (t.opex_lines ?? []).filter((line) => line.id !== lineId) }
          : t,
      ),
    }));
  };

  const addMgmt = () => {
    const row: ManagementHireLine = {
      id: newId(),
      label: 'Manager',
      headcount: 1,
      salary_monthly_each: 0,
      attribution: 'hq',
      team_id: null,
    };
    setDraft((d) => ({ ...d, management_hires: [...d.management_hires, row] }));
  };

  const addFacility = () => {
    const row: FacilityLine = {
      id: newId(),
      category: 'rent',
      label: 'Space',
      amount_monthly: 0,
      yearly: false,
      attribution: 'hq',
      team_id: null,
    };
    setDraft((d) => ({ ...d, facility_lines: [...d.facility_lines, row] }));
  };

  const addHire = () => {
    const teamId0 = teamOptions[0]?.id ?? '';
    const row: HireLine = {
      id: newId(),
      team_id: teamId0,
      headcount: 1,
      salary_monthly_each: 0,
      billable: true,
      attribution: 'team',
    };
    setDraft((d) => ({
      ...d,
      expansion: { ...d.expansion, hires: [...d.expansion.hires, row] },
    }));
  };

  const addSoftware = () => {
    const teamId0 = teamOptions[0]?.id ?? '';
    const row: SoftwareLine = {
      id: newId(),
      team_id: teamId0,
      amount_monthly: 0,
      expense_kind: 'opex',
      attribution: 'team',
    };
    setDraft((d) => ({
      ...d,
      expansion: { ...d.expansion, software: [...d.expansion.software, row] },
    }));
  };

  if (dashboardQuery.isLoading || !data || !baseline || !result) {
    return <LoadingState message="Loading scenario baselines…" />;
  }

  return (
    <Stack spacing={2.5}>
      <FinanceHeroBanner
        title="Scenarios / Planning"
        subtitle="Model new teams, management, facilities, and expansion. Save scenarios to the server for later review. Simulation only — does not change live books."
        chips={
          <>
            <Chip
              size="small"
              color="warning"
              icon={<ScienceOutlinedIcon />}
              label="Simulation"
              sx={{ fontWeight: 700 }}
            />
            <Chip size="small" label={currency} sx={{ fontWeight: 700 }} />
            {activeScenarioName ? (
              <Chip size="small" color="primary" label={activeScenarioName} />
            ) : null}
          </>
        }
      />

      <Stack direction="row" spacing={1} sx={{ justifyContent: 'space-between', flexWrap: 'wrap' }}>
        <ToggleButtonGroup
          exclusive
          size="small"
          value={panelView}
          onChange={(_, v) => v && setPanelView(v)}
        >
          <ToggleButton value="workbench">Workbench</ToggleButton>
          <ToggleButton value="saved">Saved scenarios</ToggleButton>
        </ToggleButtonGroup>
        <Stack direction="row" spacing={1}>
          {panelView === 'workbench' ? (
            <>
              <Button
                size="small"
                variant="contained"
                startIcon={<SaveOutlinedIcon />}
                onClick={() => openSave(false)}
                disabled={!activeScenarioId}
              >
                Save
              </Button>
              <Button size="small" variant="outlined" startIcon={<SaveOutlinedIcon />} onClick={() => openSave(true)}>
                Save as new
              </Button>
              <Button size="small" variant="outlined" startIcon={<RestartAltIcon />} onClick={reset}>
                Reset
              </Button>
            </>
          ) : null}
        </Stack>
      </Stack>

      {staleBaseline ? (
        <Alert severity="info" variant="outlined">
          Baseline snapshot from {baselineAsOf}. Live Overview has been refreshed — re-save to update
          baseline date or adjust inputs.
        </Alert>
      ) : null}

      {panelView === 'saved' ? (
        <FinanceSection title="Saved scenarios" subtitle="Load, clone, or compare saved worksheets.">
          <TableContainer sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Baseline</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(savedListQuery.data ?? []).map((row) => (
                  <TableRow key={row.id} hover>
                    <TableCell sx={{ fontWeight: 650 }}>{row.name}</TableCell>
                    <TableCell>{row.scenario_type}</TableCell>
                    <TableCell>{row.status}</TableCell>
                    <TableCell>{row.baseline_as_of}</TableCell>
                    <TableCell align="right">
                      <IconButton size="small" aria-label="Load" onClick={() => loadScenario(row.id)}>
                        <FolderOpenOutlinedIcon fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        aria-label="Clone"
                        onClick={() => cloneMutation.mutate(row.id)}
                      >
                        <ContentCopyOutlinedIcon fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        aria-label="Delete"
                        onClick={() => deleteMutation.mutate(row.id)}
                      >
                        <DeleteOutlinedIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          <Box sx={{ mt: 2 }}>
            <Typography sx={{ fontWeight: 700, mb: 1 }}>Compare scenarios</Typography>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ mb: 2 }}>
              <FormControl size="small" sx={{ minWidth: 200 }}>
                <InputLabel>Scenario A</InputLabel>
                <Select label="Scenario A" value={compareA} onChange={(e) => setCompareA(String(e.target.value))}>
                  <MenuItem value="">—</MenuItem>
                  {(savedListQuery.data ?? []).map((row) => (
                    <MenuItem key={row.id} value={row.id}>{row.name}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl size="small" sx={{ minWidth: 200 }}>
                <InputLabel>Scenario B</InputLabel>
                <Select label="Scenario B" value={compareB} onChange={(e) => setCompareB(String(e.target.value))}>
                  <MenuItem value="">—</MenuItem>
                  {(savedListQuery.data ?? []).map((row) => (
                    <MenuItem key={row.id} value={row.id}>{row.name}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Stack>
            {compareQuery.data ? (
              <TableContainer sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Metric</TableCell>
                      <TableCell align="right">{compareQuery.data.scenario_a.name}</TableCell>
                      <TableCell align="right">{compareQuery.data.scenario_b.name}</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {[
                      ['Pool / mo', 'simulated_pool'],
                      ['CPR', 'simulated_cpr'],
                      ['Company Op Cost', 'company_simulated_operating'],
                      ['Δ Op Cost', 'delta_company_operating'],
                      ['Total sim. net', 'total_simulated_net'],
                    ].map(([label, key]) => (
                      <TableRow key={key}>
                        <TableCell>{label}</TableCell>
                        <TableCell align="right">
                          {financeMoney(
                            toFiniteNumber(
                              compareQuery.data!.scenario_a[key as keyof CompareSummary] as number | string,
                            ),
                            currency,
                          )}
                        </TableCell>
                        <TableCell align="right">
                          {financeMoney(
                            toFiniteNumber(
                              compareQuery.data!.scenario_b[key as keyof CompareSummary] as number | string,
                            ),
                            currency,
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            ) : null}
          </Box>
        </FinanceSection>
      ) : (
        <>
          <Grid container spacing={1.5}>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <KpiMetricCard
                compact
                accent="info"
                icon={AccountBalanceWalletOutlinedIcon}
                title="Simulated pool / mo"
                value={financeMoney(result.simulated_pool, currency)}
                subtitle={`Δ ${financeMoney(result.delta_pool, currency)} vs live`}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <KpiMetricCard
                compact
                accent="primary"
                icon={PaymentsOutlinedIcon}
                title="Simulated CPR"
                value={financeMoney(result.simulated_cpr, currency)}
                subtitle={`Live ${financeMoney(baseline.cpr, currency)}`}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <KpiMetricCard
                compact
                accent="warning"
                icon={ShowChartOutlinedIcon}
                title="Company Op Cost / mo"
                value={financeMoney(result.company_simulated_operating, currency)}
                subtitle={`Δ ${financeMoney(result.delta_company_operating, currency)}`}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <KpiMetricCard
                compact
                accent="success"
                icon={GroupsOutlinedIcon}
                title="Sim billable FTE"
                value={String(result.simulated_billable_fte)}
                subtitle={`Baseline ${baseline.billable_fte}`}
              />
            </Grid>
          </Grid>

          <FinanceSection
            title="New teams"
            subtitle="Hypothetical delivery teams with working model and revenue (any FX currency → base INR via FX Rates)."
            action={
              <Button size="small" startIcon={<AddIcon />} onClick={addNewTeam}>
                Add new team
              </Button>
            }
          >
            {draft.new_teams.length ? (
              <Stack spacing={2}>
                {draft.new_teams.map((row) => (
                  <Stack key={row.id} spacing={1} sx={{ flexWrap: 'wrap' }}>
                    <Stack direction={{ xs: 'column', md: 'row' }} spacing={1} sx={{ flexWrap: 'wrap' }}>
                      <TextField
                        size="small"
                        label="Team name"
                        value={row.name}
                        onChange={(e) =>
                          setDraft((d) => ({
                            ...d,
                            new_teams: d.new_teams.map((t) =>
                              t.id === row.id ? { ...t, name: e.target.value } : t,
                            ),
                          }))
                        }
                        sx={{ minWidth: 180 }}
                      />
                      <FormControl size="small" sx={{ minWidth: 160 }}>
                        <InputLabel>Working model</InputLabel>
                        <Select
                          label="Working model"
                          value={row.working_model_code}
                          onChange={(e) =>
                            setDraft((d) => ({
                              ...d,
                              new_teams: d.new_teams.map((t) =>
                                t.id === row.id
                                  ? { ...t, working_model_code: String(e.target.value) }
                                  : t,
                              ),
                            }))
                          }
                        >
                          {workingModels.map((wm) => (
                            <MenuItem key={wm.id} value={wm.code ?? wm.strategy_key}>
                              {wm.name}
                            </MenuItem>
                          ))}
                          {!workingModels.length ? (
                            <>
                              <MenuItem value="retainer">Retainer</MenuItem>
                              <MenuItem value="project_based">Project based</MenuItem>
                              <MenuItem value="time_materials">Time & materials</MenuItem>
                              <MenuItem value="overheads">Overheads</MenuItem>
                            </>
                          ) : null}
                        </Select>
                      </FormControl>
                      {numField('Headcount', row.delivery_headcount, (n) =>
                        setDraft((d) => ({
                          ...d,
                          new_teams: d.new_teams.map((t) =>
                            t.id === row.id
                              ? { ...t, delivery_headcount: Math.max(0, Math.floor(n)) }
                              : t,
                          ),
                        })),
                        110,
                      )}
                      {numField('Salary / mo each', row.salary_monthly_each, (n) =>
                        setDraft((d) => ({
                          ...d,
                          new_teams: d.new_teams.map((t) =>
                            t.id === row.id ? { ...t, salary_monthly_each: n } : t,
                          ),
                        })),
                        140,
                      )}
                      {numField(
                        `Expected revenue / mo (${(row.revenue_currency_code || currency).toUpperCase()})`,
                        row.expected_monthly_revenue,
                        (n) =>
                          setDraft((d) => ({
                            ...d,
                            new_teams: d.new_teams.map((t) =>
                              t.id === row.id ? { ...t, expected_monthly_revenue: n } : t,
                            ),
                          })),
                        170,
                      )}
                      <FormControl size="small" sx={{ minWidth: 110 }}>
                        <InputLabel>Revenue FX</InputLabel>
                        <Select
                          label="Revenue FX"
                          value={(row.revenue_currency_code || currency).toUpperCase()}
                          onChange={(e) => setNewTeamRevenueCurrency(row.id, String(e.target.value))}
                        >
                          {currencyOptions.map((c) => (
                            <MenuItem key={c.code} value={c.code}>
                              {c.code}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                      <FormControlLabel
                        control={
                          <Checkbox
                            checked={row.billable}
                            onChange={(_, checked) =>
                              setDraft((d) => ({
                                ...d,
                                new_teams: d.new_teams.map((t) =>
                                  t.id === row.id ? { ...t, billable: checked } : t,
                                ),
                              }))
                            }
                          />
                        }
                        label="Billable FTE"
                      />
                      <IconButton
                        aria-label="Remove new team"
                        onClick={() =>
                          setDraft((d) => ({
                            ...d,
                            new_teams: d.new_teams.filter((t) => t.id !== row.id),
                          }))
                        }
                      >
                        <DeleteOutlinedIcon fontSize="small" />
                      </IconButton>
                    </Stack>
                    <Box sx={{ pl: { md: 0.5 }, width: '100%' }}>
                      <Stack
                        direction="row"
                        spacing={1}
                        sx={{ alignItems: 'center', justifyContent: 'space-between', mb: 1 }}
                      >
                        <Typography variant="body2" sx={{ fontWeight: 650 }}>
                          OpEx / mo
                          {(row.opex_lines ?? []).length
                            ? ` · ${financeMoney(newTeamOpexMonthly(row), currency)} total`
                            : ''}
                        </Typography>
                        <Button size="small" startIcon={<AddIcon />} onClick={() => addNewTeamOpex(row.id)}>
                          Add OpEx
                        </Button>
                      </Stack>
                      {(row.opex_lines ?? []).length ? (
                        <Stack spacing={1}>
                          {(row.opex_lines ?? []).map((line) => (
                            <Stack
                              key={line.id}
                              direction={{ xs: 'column', md: 'row' }}
                              spacing={1}
                              sx={{ alignItems: { md: 'center' }, flexWrap: 'wrap' }}
                            >
                              <FormControl size="small" sx={{ minWidth: 160 }}>
                                <InputLabel>Category</InputLabel>
                                <Select
                                  label="Category"
                                  value={line.category}
                                  onChange={(e) =>
                                    updateNewTeamOpex(row.id, line.id, {
                                      category: e.target.value as NewTeamOpexCategory,
                                    })
                                  }
                                >
                                  {NEW_TEAM_OPEX_CATEGORIES.map((c) => (
                                    <MenuItem key={c.value} value={c.value}>
                                      {c.label}
                                    </MenuItem>
                                  ))}
                                </Select>
                              </FormControl>
                              <TextField
                                size="small"
                                label="Description"
                                placeholder="e.g. Adobe / AWS"
                                value={line.label}
                                onChange={(e) =>
                                  updateNewTeamOpex(row.id, line.id, { label: e.target.value })
                                }
                                sx={{ minWidth: 160 }}
                              />
                              {numField('Amount / mo', line.amount_monthly, (n) =>
                                updateNewTeamOpex(row.id, line.id, { amount_monthly: n }),
                                130,
                              )}
                              <IconButton
                                aria-label="Remove OpEx line"
                                onClick={() => removeNewTeamOpex(row.id, line.id)}
                              >
                                <DeleteOutlinedIcon fontSize="small" />
                              </IconButton>
                            </Stack>
                          ))}
                        </Stack>
                      ) : (
                        <Typography variant="caption" color="text.secondary">
                          No OpEx yet — add software licenses, cloud, travel, or other monthly expenses.
                        </Typography>
                      )}
                    </Box>
                    {(row.revenue_currency_code || currency).toUpperCase() !==
                    currency.toUpperCase() ? (
                      <Typography variant="caption" color="text.secondary" sx={{ pl: 0.5 }}>
                        {(() => {
                          const code = (row.revenue_currency_code || currency).toUpperCase();
                          const looked = lookupFxRateToBase(fxRates, code, currency);
                          const missing = looked == null;
                          const rate =
                            Number(row.revenue_fx_rate_to_base) > 0
                              ? Number(row.revenue_fx_rate_to_base)
                              : looked ?? 1;
                          const native = newTeamMonthlyRevenueNative({
                            ...row,
                            revenue_fx_rate_to_base: rate,
                          });
                          const inBase = newTeamMonthlyRevenue({
                            ...row,
                            revenue_fx_rate_to_base: rate,
                          });
                          return missing
                            ? `No FX rate for ${code}→${currency} — using 1.0 (set rate under FX Rates)`
                            : `${financeMoney(native, code)} → ${financeMoney(inBase, currency)} @ ${rate}`;
                        })()}
                      </Typography>
                    ) : null}
                  </Stack>
                ))}
              </Stack>
            ) : (
              <Typography variant="body2" color="text.secondary">
                No hypothetical teams yet.
              </Typography>
            )}
          </FinanceSection>

          <FinanceSection
            title="Management hires"
            subtitle="HQ management feeds the shared overhead pool (CPR); team-attached management is team direct Op Cost."
            action={
              <Button size="small" startIcon={<AddIcon />} onClick={addMgmt}>
                Add management hire
              </Button>
            }
          >
            {draft.management_hires.length ? (
              <Stack spacing={1.25}>
                {draft.management_hires.map((row) => (
                  <Stack
                    key={row.id}
                    direction={{ xs: 'column', md: 'row' }}
                    spacing={1}
                    sx={{ alignItems: { md: 'center' }, flexWrap: 'wrap' }}
                  >
                    <TextField
                      size="small"
                      label="Role"
                      value={row.label}
                      onChange={(e) =>
                        setDraft((d) => ({
                          ...d,
                          management_hires: d.management_hires.map((m) =>
                            m.id === row.id ? { ...m, label: e.target.value } : m,
                          ),
                        }))
                      }
                      sx={{ minWidth: 140 }}
                    />
                    {numField('Count', row.headcount, (n) =>
                      setDraft((d) => ({
                        ...d,
                        management_hires: d.management_hires.map((m) =>
                          m.id === row.id ? { ...m, headcount: Math.max(0, Math.floor(n)) } : m,
                        ),
                      })),
                      90,
                    )}
                    {numField('Salary / mo each', row.salary_monthly_each, (n) =>
                      setDraft((d) => ({
                        ...d,
                        management_hires: d.management_hires.map((m) =>
                          m.id === row.id ? { ...m, salary_monthly_each: n } : m,
                        ),
                      })),
                      140,
                    )}
                    <FormControl size="small" sx={{ minWidth: 120 }}>
                      <InputLabel>Attribution</InputLabel>
                      <Select
                        label="Attribution"
                        value={row.attribution}
                        onChange={(e) =>
                          setDraft((d) => ({
                            ...d,
                            management_hires: d.management_hires.map((m) =>
                              m.id === row.id
                                ? {
                                    ...m,
                                    attribution: e.target.value as 'hq' | 'team',
                                    team_id:
                                      e.target.value === 'team'
                                        ? m.team_id ?? teamOptions[0]?.id ?? null
                                        : null,
                                  }
                                : m,
                            ),
                          }))
                        }
                      >
                        <MenuItem value="hq">HQ pool</MenuItem>
                        <MenuItem value="team">Team direct</MenuItem>
                      </Select>
                    </FormControl>
                    {row.attribution === 'team' ? (
                      <FormControl size="small" sx={{ minWidth: 160 }}>
                        <InputLabel>Team</InputLabel>
                        <Select
                          label="Team"
                          value={row.team_id ?? ''}
                          onChange={(e) =>
                            setDraft((d) => ({
                              ...d,
                              management_hires: d.management_hires.map((m) =>
                                m.id === row.id ? { ...m, team_id: String(e.target.value) } : m,
                              ),
                            }))
                          }
                        >
                          {teamOptions.map((t) => (
                            <MenuItem key={t.id} value={t.id}>{t.name}</MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    ) : null}
                    <IconButton
                      aria-label="Remove management hire"
                      onClick={() =>
                        setDraft((d) => ({
                          ...d,
                          management_hires: d.management_hires.filter((m) => m.id !== row.id),
                        }))
                      }
                    >
                      <DeleteOutlinedIcon fontSize="small" />
                    </IconButton>
                  </Stack>
                ))}
              </Stack>
            ) : (
              <Typography variant="body2" color="text.secondary">No management hires.</Typography>
            )}
          </FinanceSection>

          <FinanceSection
            title="Space & utilities"
            subtitle="Shared HQ spend increases the pool; team-dedicated spend is team OpEx."
            action={
              <Button size="small" startIcon={<AddIcon />} onClick={addFacility}>
                Add facility line
              </Button>
            }
          >
            {draft.facility_lines.length ? (
              <Stack spacing={1.25}>
                {draft.facility_lines.map((row) => (
                  <Stack
                    key={row.id}
                    direction={{ xs: 'column', md: 'row' }}
                    spacing={1}
                    sx={{ alignItems: { md: 'center' }, flexWrap: 'wrap' }}
                  >
                    <FormControl size="small" sx={{ minWidth: 120 }}>
                      <InputLabel>Category</InputLabel>
                      <Select
                        label="Category"
                        value={row.category}
                        onChange={(e) =>
                          setDraft((d) => ({
                            ...d,
                            facility_lines: d.facility_lines.map((f) =>
                              f.id === row.id
                                ? { ...f, category: e.target.value as FacilityLine['category'] }
                                : f,
                            ),
                          }))
                        }
                      >
                        <MenuItem value="rent">Rent</MenuItem>
                        <MenuItem value="utilities">Utilities</MenuItem>
                        <MenuItem value="facilities">Facilities</MenuItem>
                        <MenuItem value="capex">CapEx</MenuItem>
                        <MenuItem value="other">Other</MenuItem>
                      </Select>
                    </FormControl>
                    <TextField
                      size="small"
                      label="Label"
                      value={row.label}
                      onChange={(e) =>
                        setDraft((d) => ({
                          ...d,
                          facility_lines: d.facility_lines.map((f) =>
                            f.id === row.id ? { ...f, label: e.target.value } : f,
                          ),
                        }))
                      }
                      sx={{ minWidth: 140 }}
                    />
                    {numField(
                      row.yearly ? 'Amount / yr' : 'Amount / mo',
                      row.amount_monthly,
                      (n) =>
                        setDraft((d) => ({
                          ...d,
                          facility_lines: d.facility_lines.map((f) =>
                            f.id === row.id ? { ...f, amount_monthly: n } : f,
                          ),
                        })),
                      130,
                    )}
                    <FormControl size="small" sx={{ minWidth: 120 }}>
                      <InputLabel>Attribution</InputLabel>
                      <Select
                        label="Attribution"
                        value={row.attribution}
                        onChange={(e) =>
                          setDraft((d) => ({
                            ...d,
                            facility_lines: d.facility_lines.map((f) =>
                              f.id === row.id
                                ? {
                                    ...f,
                                    attribution: e.target.value as 'hq' | 'team',
                                    team_id:
                                      e.target.value === 'team'
                                        ? f.team_id ?? teamOptions[0]?.id ?? null
                                        : null,
                                  }
                                : f,
                            ),
                          }))
                        }
                      >
                        <MenuItem value="hq">HQ pool</MenuItem>
                        <MenuItem value="team">Team direct</MenuItem>
                      </Select>
                    </FormControl>
                    {row.attribution === 'team' ? (
                      <FormControl size="small" sx={{ minWidth: 160 }}>
                        <InputLabel>Team</InputLabel>
                        <Select
                          label="Team"
                          value={row.team_id ?? ''}
                          onChange={(e) =>
                            setDraft((d) => ({
                              ...d,
                              facility_lines: d.facility_lines.map((f) =>
                                f.id === row.id ? { ...f, team_id: String(e.target.value) } : f,
                              ),
                            }))
                          }
                        >
                          {teamOptions.map((t) => (
                            <MenuItem key={t.id} value={t.id}>{t.name}</MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    ) : null}
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={row.yearly}
                          onChange={(_, checked) =>
                            setDraft((d) => ({
                              ...d,
                              facility_lines: d.facility_lines.map((f) =>
                                f.id === row.id ? { ...f, yearly: checked } : f,
                              ),
                            }))
                          }
                        />
                      }
                      label="Yearly"
                    />
                    <IconButton
                      aria-label="Remove facility"
                      onClick={() =>
                        setDraft((d) => ({
                          ...d,
                          facility_lines: d.facility_lines.filter((f) => f.id !== row.id),
                        }))
                      }
                    >
                      <DeleteOutlinedIcon fontSize="small" />
                    </IconButton>
                  </Stack>
                ))}
              </Stack>
            ) : (
              <Typography variant="body2" color="text.secondary">No facility lines.</Typography>
            )}
          </FinanceSection>

          <FinanceSection
            title="Shared overhead pool"
            subtitle="Live management salaries and HQ costs are already in the simulation baseline. Scenario additions below are shared across all delivery teams via CPR."
          >
            {result.shared_overhead ? (
              <TableContainer sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 700 }}>Component</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>Live / mo</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>Scenario +</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>Simulated</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {[
                      {
                        label: 'Management / HQ salaries',
                        live: result.shared_overhead.live_management_salary,
                        add:
                          result.shared_overhead.scenario_extra_salary +
                          result.shared_overhead.scenario_management_hq +
                          result.shared_overhead.scenario_hires_hq,
                      },
                      {
                        label: 'Shared OpEx',
                        live: result.shared_overhead.live_shared_opex,
                        add:
                          result.shared_overhead.scenario_extra_opex +
                          result.shared_overhead.scenario_facility_hq_opex +
                          result.shared_overhead.scenario_software_hq_opex,
                      },
                      {
                        label: 'Shared CapEx',
                        live: result.shared_overhead.live_shared_capex,
                        add:
                          result.shared_overhead.scenario_extra_capex +
                          result.shared_overhead.scenario_facility_hq_capex +
                          result.shared_overhead.scenario_software_hq_capex,
                      },
                    ].map((row) => (
                      <TableRow key={row.label}>
                        <TableCell>{row.label}</TableCell>
                        <TableCell align="right">{financeMoney(row.live, currency)}</TableCell>
                        <TableCell align="right">
                          {row.add > 0 ? financeMoney(row.add, currency) : '—'}
                        </TableCell>
                        <TableCell align="right">{financeMoney(row.live + row.add, currency)}</TableCell>
                      </TableRow>
                    ))}
                    <TableRow sx={{ bgcolor: designTokens.semantic.primarySoft }}>
                      <TableCell sx={{ fontWeight: 700 }}>Total shared pool</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>
                        {financeMoney(result.shared_overhead.live_pool, currency)}
                      </TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>
                        {financeMoney(result.shared_overhead.scenario_additions_total, currency)}
                      </TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>
                        {financeMoney(result.shared_overhead.simulated_pool, currency)}
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </TableContainer>
            ) : null}
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              CPR {financeMoney(result.simulated_cpr, currency)} per billable FTE — allocated into each
              delivery team&apos;s Op Cost.
              {baseline.overhead_breakdown?.management_team_name
                ? ` Overhead home: ${baseline.overhead_breakdown.management_team_name}.`
                : ''}
            </Typography>
          </FinanceSection>

          <FinanceSection
            title="Overhead scenario"
            subtitle="Additional shared amounts (management salaries, rent, utilities) — rolled into the pool above."
          >
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ flexWrap: 'wrap' }}>
              {numField('Extra HQ salary / mo', draft.overhead.extra_hq_salary_monthly, (n) =>
                setDraft((d) => ({
                  ...d,
                  overhead: { ...d.overhead, extra_hq_salary_monthly: n },
                })),
              )}
              <Stack spacing={0.5}>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                  {numField(
                    draft.opex_yearly ? 'Extra shared OpEx / yr' : 'Extra shared OpEx / mo',
                    draft.overhead.extra_shared_opex_monthly,
                    (n) =>
                      setDraft((d) => ({
                        ...d,
                        overhead: { ...d.overhead, extra_shared_opex_monthly: n },
                      })),
                  )}
                  <ToggleButtonGroup
                    exclusive
                    size="small"
                    value={draft.opex_yearly ? 'year' : 'month'}
                    onChange={(_, v) => v && setDraft((d) => ({ ...d, opex_yearly: v === 'year' }))}
                  >
                    <ToggleButton value="month">/ mo</ToggleButton>
                    <ToggleButton value="year">/ yr</ToggleButton>
                  </ToggleButtonGroup>
                </Stack>
              </Stack>
              <Stack spacing={0.5}>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                  {numField(
                    draft.capex_yearly ? 'Extra shared CapEx / yr' : 'Extra shared CapEx / mo',
                    draft.overhead.extra_shared_capex_monthly,
                    (n) =>
                      setDraft((d) => ({
                        ...d,
                        overhead: { ...d.overhead, extra_shared_capex_monthly: n },
                      })),
                  )}
                  <ToggleButtonGroup
                    exclusive
                    size="small"
                    value={draft.capex_yearly ? 'year' : 'month'}
                    onChange={(_, v) => v && setDraft((d) => ({ ...d, capex_yearly: v === 'year' }))}
                  >
                    <ToggleButton value="month">/ mo</ToggleButton>
                    <ToggleButton value="year">/ yr</ToggleButton>
                  </ToggleButtonGroup>
                </Stack>
              </Stack>
            </Stack>
          </FinanceSection>

          <FinanceSection
            title="Existing team expansion"
            subtitle="Hires and software on current delivery teams."
            action={
              <Stack direction="row" spacing={1}>
                <Button size="small" startIcon={<AddIcon />} onClick={addHire} disabled={!teamOptions.length}>
                  Add hire
                </Button>
                <Button size="small" startIcon={<AddIcon />} onClick={addSoftware} disabled={!teamOptions.length}>
                  Add software
                </Button>
              </Stack>
            }
          >
            <Stack spacing={2}>
              {draft.expansion.hires.map((row) => (
                <Stack key={row.id} direction="row" spacing={1} sx={{ flexWrap: 'wrap', alignItems: 'center' }}>
                  <FormControl size="small" sx={{ minWidth: 160 }}>
                    <InputLabel>Team</InputLabel>
                    <Select
                      label="Team"
                      value={row.team_id}
                      onChange={(e) =>
                        setDraft((d) => ({
                          ...d,
                          expansion: {
                            ...d.expansion,
                            hires: d.expansion.hires.map((h) =>
                              h.id === row.id ? { ...h, team_id: String(e.target.value) } : h,
                            ),
                          },
                        }))
                      }
                    >
                      {teamOptions.map((t) => (
                        <MenuItem key={t.id} value={t.id}>{t.name}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  {numField('Headcount', row.headcount, (n) =>
                    setDraft((d) => ({
                      ...d,
                      expansion: {
                        ...d.expansion,
                        hires: d.expansion.hires.map((h) =>
                          h.id === row.id ? { ...h, headcount: Math.max(0, Math.floor(n)) } : h,
                        ),
                      },
                    })),
                    100,
                  )}
                  {numField('Salary / mo', row.salary_monthly_each, (n) =>
                    setDraft((d) => ({
                      ...d,
                      expansion: {
                        ...d.expansion,
                        hires: d.expansion.hires.map((h) =>
                          h.id === row.id ? { ...h, salary_monthly_each: n } : h,
                        ),
                      },
                    })),
                    120,
                  )}
                  <FormControl size="small" sx={{ minWidth: 130 }}>
                    <InputLabel>Cost pool</InputLabel>
                    <Select
                      label="Cost pool"
                      value={row.attribution ?? 'team'}
                      onChange={(e) =>
                        setDraft((d) => ({
                          ...d,
                          expansion: {
                            ...d.expansion,
                            hires: d.expansion.hires.map((h) =>
                              h.id === row.id
                                ? {
                                    ...h,
                                    attribution: e.target.value as 'hq' | 'team',
                                    billable:
                                      e.target.value === 'hq' ? false : h.billable,
                                  }
                                : h,
                            ),
                          },
                        }))
                      }
                    >
                      <MenuItem value="team">Team direct</MenuItem>
                      <MenuItem value="hq">Shared HQ pool</MenuItem>
                    </Select>
                  </FormControl>
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={row.billable}
                        disabled={(row.attribution ?? 'team') === 'hq'}
                        onChange={(_, checked) =>
                          setDraft((d) => ({
                            ...d,
                            expansion: {
                              ...d.expansion,
                              hires: d.expansion.hires.map((h) =>
                                h.id === row.id ? { ...h, billable: checked } : h,
                              ),
                            },
                          }))
                        }
                      />
                    }
                    label="Billable"
                  />
                  <IconButton onClick={() =>
                    setDraft((d) => ({
                      ...d,
                      expansion: {
                        ...d.expansion,
                        hires: d.expansion.hires.filter((h) => h.id !== row.id),
                      },
                    }))
                  }>
                    <DeleteOutlinedIcon fontSize="small" />
                  </IconButton>
                </Stack>
              ))}
              {draft.expansion.software.map((row) => (
                <Stack key={row.id} direction="row" spacing={1} sx={{ flexWrap: 'wrap', alignItems: 'center' }}>
                  <FormControl size="small" sx={{ minWidth: 140 }}>
                    <InputLabel>Attribution</InputLabel>
                    <Select
                      label="Attribution"
                      value={row.attribution ?? 'team'}
                      onChange={(e) =>
                        setDraft((d) => ({
                          ...d,
                          expansion: {
                            ...d.expansion,
                            software: d.expansion.software.map((s) =>
                              s.id === row.id
                                ? {
                                    ...s,
                                    attribution: e.target.value as 'hq' | 'team',
                                    team_id:
                                      e.target.value === 'team'
                                        ? s.team_id ?? teamOptions[0]?.id ?? ''
                                        : s.team_id,
                                  }
                                : s,
                            ),
                          },
                        }))
                      }
                    >
                      <MenuItem value="team">Team</MenuItem>
                      <MenuItem value="hq">HQ pool</MenuItem>
                    </Select>
                  </FormControl>
                  {(row.attribution ?? 'team') === 'team' ? (
                    <FormControl size="small" sx={{ minWidth: 160 }}>
                      <InputLabel>Team</InputLabel>
                      <Select
                        label="Team"
                        value={row.team_id}
                        onChange={(e) =>
                          setDraft((d) => ({
                            ...d,
                            expansion: {
                              ...d.expansion,
                              software: d.expansion.software.map((s) =>
                                s.id === row.id ? { ...s, team_id: String(e.target.value) } : s,
                              ),
                            },
                          }))
                        }
                      >
                        {teamOptions.map((t) => (
                          <MenuItem key={t.id} value={t.id}>{t.name}</MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  ) : null}
                  <FormControl size="small" sx={{ minWidth: 100 }}>
                    <InputLabel>Kind</InputLabel>
                    <Select
                      label="Kind"
                      value={row.expense_kind ?? 'opex'}
                      onChange={(e) =>
                        setDraft((d) => ({
                          ...d,
                          expansion: {
                            ...d.expansion,
                            software: d.expansion.software.map((s) =>
                              s.id === row.id
                                ? { ...s, expense_kind: e.target.value as 'opex' | 'capex' }
                                : s,
                            ),
                          },
                        }))
                      }
                    >
                      <MenuItem value="opex">OpEx</MenuItem>
                      <MenuItem value="capex">CapEx</MenuItem>
                    </Select>
                  </FormControl>
                  {numField('Amount / mo', row.amount_monthly, (n) =>
                    setDraft((d) => ({
                      ...d,
                      expansion: {
                        ...d.expansion,
                        software: d.expansion.software.map((s) =>
                          s.id === row.id ? { ...s, amount_monthly: n } : s,
                        ),
                      },
                    })),
                    120,
                  )}
                  <IconButton onClick={() =>
                    setDraft((d) => ({
                      ...d,
                      expansion: {
                        ...d.expansion,
                        software: d.expansion.software.filter((s) => s.id !== row.id),
                      },
                    }))
                  }>
                    <DeleteOutlinedIcon fontSize="small" />
                  </IconButton>
                </Stack>
              ))}
            </Stack>
          </FinanceSection>

          <FinanceSection title="Simulated team P&L" subtitle="Includes new teams and scenario CPR.">
            <TableContainer
              sx={{
                borderRadius: `${designTokens.radius.md}px`,
                border: '1px solid',
                borderColor: 'divider',
              }}
            >
              <Table size="small">
                <TableHead>
                  <TableRow sx={{ bgcolor: designTokens.semantic.primarySoft }}>
                    <TableCell sx={{ fontWeight: 700 }}>Team</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700 }}>Revenue</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700 }}>Sim. Op Cost</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700 }}>Sim. net</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700 }}>After-tax</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700 }}>Break-even</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {result.teams.map((row) => (
                    <TableRow key={row.team_id} hover>
                      <TableCell sx={{ fontWeight: 650 }}>
                        {row.team_name}
                        {row.is_new_team ? (
                          <Chip size="small" label="New" sx={{ ml: 1 }} />
                        ) : null}
                      </TableCell>
                      <TableCell align="right">{financeMoney(row.revenue, currency)}</TableCell>
                      <TableCell align="right">{financeMoney(row.simulated_operating, currency)}</TableCell>
                      <TableCell align="right">{financeMoney(row.simulated_net, currency)}</TableCell>
                      <TableCell align="right">{financeMoney(row.simulated_after_tax, currency)}</TableCell>
                      <TableCell align="right">{financeMoney(row.break_even_revenue, currency)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </FinanceSection>
        </>
      )}

      <Dialog open={saveOpen} onClose={() => setSaveOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>{saveAsNew ? 'Save scenario as new' : 'Save scenario'}</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            margin="dense"
            label="Scenario name"
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSaveOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={!saveName.trim() || saveMutation.isPending}
            onClick={() =>
              saveMutation.mutate({
                name: saveName.trim(),
                id: activeScenarioId,
                asNew: saveAsNew,
              })
            }
          >
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
