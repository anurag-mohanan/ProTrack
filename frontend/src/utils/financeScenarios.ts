/**
 * Client-side Finance Scenarios / Planning calculators (v2).
 * Simulation only — persisted scenarios use the API. Formulas mirrored in
 * app/services/finance/scenario_calculator.py for CI.
 */

export type ScenarioBaselineTeam = {
  team_id: string;
  team_name: string;
  is_overhead_home?: boolean;
  revenue: number;
  direct_operating: number;
  allocated_overhead: number;
  operating: number;
  net_profit: number;
  billable_fte: number;
  estimated_cost: number;
};

export type ScenarioBaseline = {
  overhead_pool: number;
  billable_fte: number;
  cpr: number;
  company_operating: number;
  corporate_tax_percent: number;
  teams: ScenarioBaselineTeam[];
  /** Live shared overhead home breakdown (management salaries + HQ OpEx/CapEx). */
  overhead_breakdown?: {
    management_salary: number;
    shared_opex: number;
    shared_capex: number;
    management_team_name?: string;
  };
};

export type OverheadScenarioInput = {
  extra_hq_salary_monthly: number;
  extra_shared_opex_monthly: number;
  extra_shared_capex_monthly: number;
};

export type HireLine = {
  id: string;
  team_id: string;
  headcount: number;
  salary_monthly_each: number;
  billable: boolean;
  /** HQ = shared overhead pool (management); team = team direct Op Cost. */
  attribution?: 'team' | 'hq';
};

export type SoftwareLine = {
  id: string;
  team_id: string;
  amount_monthly: number;
  expense_kind?: 'opex' | 'capex';
  attribution?: 'team' | 'hq';
  yearly?: boolean;
  label?: string;
};

export type ExpansionScenarioInput = {
  hires: HireLine[];
  software: SoftwareLine[];
};

export type NewTeamOpexCategory =
  | 'software_license'
  | 'cloud_subscription'
  | 'hardware'
  | 'travel'
  | 'training'
  | 'facilities'
  | 'other';

export const NEW_TEAM_OPEX_CATEGORIES: { value: NewTeamOpexCategory; label: string }[] = [
  { value: 'software_license', label: 'Software license' },
  { value: 'cloud_subscription', label: 'Cloud / SaaS' },
  { value: 'hardware', label: 'Hardware' },
  { value: 'travel', label: 'Travel' },
  { value: 'training', label: 'Training' },
  { value: 'facilities', label: 'Facilities' },
  { value: 'other', label: 'Other expenses' },
];

export type NewTeamOpexLine = {
  id: string;
  category: NewTeamOpexCategory;
  label: string;
  amount_monthly: number;
};

export type NewTeamLine = {
  id: string;
  name: string;
  working_model_code: string;
  revenue_mode: 'fixed_fee' | 'expected_revenue' | 'pipeline';
  fixed_fee_amount: number;
  fixed_fee_period: 'monthly' | 'quarterly' | 'annual';
  expected_monthly_revenue: number;
  /** @deprecated Prefer opex_lines — kept for older saved scenarios. */
  expected_monthly_cost?: number;
  /** Team OpEx lines (software license, other expenses, …). */
  opex_lines: NewTeamOpexLine[];
  /** ISO currency for revenue inputs (converted to base via fx rate). */
  revenue_currency_code: string;
  /** Multiplier to company base (INR). 1 when revenue is already in base. */
  revenue_fx_rate_to_base: number;
  pipeline_monthly?: number;
  win_rate_percent?: number;
  delivery_headcount: number;
  salary_monthly_each: number;
  billable: boolean;
};

export type ManagementHireLine = {
  id: string;
  label: string;
  headcount: number;
  salary_monthly_each: number;
  attribution: 'hq' | 'team';
  team_id: string | null;
};

export type FacilityLine = {
  id: string;
  category: 'rent' | 'utilities' | 'facilities' | 'capex' | 'other';
  label: string;
  amount_monthly: number;
  yearly: boolean;
  attribution: 'hq' | 'team';
  team_id: string | null;
};

export type ScenarioDraft = {
  schema_version: number;
  overhead: OverheadScenarioInput & {
    opex_yearly?: boolean;
    capex_yearly?: boolean;
  };
  expansion: ExpansionScenarioInput;
  opex_yearly: boolean;
  capex_yearly: boolean;
  new_teams: NewTeamLine[];
  management_hires: ManagementHireLine[];
  facility_lines: FacilityLine[];
};

export function yearlyToMonthly(amount: number): number {
  if (!Number.isFinite(amount)) return 0;
  return round2(amount / 12);
}

export function round2(n: number): number {
  if (!Number.isFinite(n)) return 0;
  return Math.round(n * 100) / 100;
}

export function afterTaxNet(preTaxNet: number, taxPercent: number): number {
  const factor = (100 - taxPercent) / 100;
  return round2(preTaxNet * factor);
}

export function normalizeFixedFeeMonthly(amount: number, period: string): number {
  const key = (period || 'monthly').toLowerCase();
  if (key === 'quarterly') return round2(amount / 3);
  if (key === 'annual') return yearlyToMonthly(amount);
  return round2(amount);
}

export function revenueFxMultiplier(row: Pick<NewTeamLine, 'revenue_currency_code' | 'revenue_fx_rate_to_base'>): number {
  const rate = Number(row.revenue_fx_rate_to_base);
  if (Number.isFinite(rate) && rate > 0) return rate;
  const code = (row.revenue_currency_code || 'INR').toUpperCase();
  return code === 'INR' ? 1 : 1;
}

/** Native-currency monthly revenue before FX (for UI captions). */
export function newTeamMonthlyRevenueNative(row: NewTeamLine): number {
  const code = (row.working_model_code || 'project_based').toLowerCase();
  if (code === 'overheads') return 0;
  const mode = row.revenue_mode || 'expected_revenue';
  if (mode === 'fixed_fee') {
    return normalizeFixedFeeMonthly(row.fixed_fee_amount, row.fixed_fee_period);
  }
  if (mode === 'pipeline') {
    const pipeline = Number(row.pipeline_monthly) || 0;
    const winRate = Number(row.win_rate_percent) || 100;
    return round2((pipeline * winRate) / 100);
  }
  if (row.expected_monthly_revenue > 0) return row.expected_monthly_revenue;
  return normalizeFixedFeeMonthly(row.fixed_fee_amount, row.fixed_fee_period);
}

/** Monthly revenue in company base currency (INR). */
export function newTeamMonthlyRevenue(row: NewTeamLine): number {
  return round2(newTeamMonthlyRevenueNative(row) * revenueFxMultiplier(row));
}

/** Monthly OpEx total for a new team (categorized lines + legacy expected_monthly_cost). */
export function newTeamOpexMonthly(row: NewTeamLine): number {
  const lines = row.opex_lines ?? [];
  const fromLines = lines.reduce(
    (sum, line) => sum + Math.max(0, Number(line.amount_monthly) || 0),
    0,
  );
  if (fromLines > 0) return round2(fromLines);
  return round2(Math.max(0, Number(row.expected_monthly_cost) || 0));
}

export function normalizeNewTeamOpexLines(row: Partial<NewTeamLine>): NewTeamOpexLine[] {
  if (Array.isArray(row.opex_lines) && row.opex_lines.length) {
    return row.opex_lines.map((line) => ({
      id: line.id || `${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`,
      category: (line.category || 'other') as NewTeamOpexCategory,
      label: line.label || '',
      amount_monthly: Math.max(0, Number(line.amount_monthly) || 0),
    }));
  }
  const legacy = Math.max(0, Number(row.expected_monthly_cost) || 0);
  if (legacy > 0) {
    return [
      {
        id: `${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`,
        category: 'other',
        label: 'Legacy expected cost',
        amount_monthly: legacy,
      },
    ];
  }
  return [];
}

export type FxRateRow = {
  from_currency: string;
  to_currency: string;
  rate: number | string;
  effective_date?: string;
};

/** Latest rate from ``fromCurrency`` → ``baseCurrency`` (1 if same). Returns null if missing. */
export function lookupFxRateToBase(
  rates: FxRateRow[],
  fromCurrency: string,
  baseCurrency = 'INR',
): number | null {
  const source = (fromCurrency || baseCurrency).toUpperCase();
  const target = (baseCurrency || 'INR').toUpperCase();
  if (source === target) return 1;
  const matches = rates
    .filter(
      (r) =>
        (r.from_currency || '').toUpperCase() === source &&
        (r.to_currency || '').toUpperCase() === target,
    )
    .sort((a, b) => String(b.effective_date || '').localeCompare(String(a.effective_date || '')));
  if (!matches.length) return null;
  const rate = Number(matches[0].rate);
  return Number.isFinite(rate) && rate > 0 ? rate : null;
}

function monthlyAmount(amount: number, yearly: boolean): number {
  return yearly ? yearlyToMonthly(amount) : amount;
}

function softwareMonthly(row: SoftwareLine): number {
  const amt = Math.max(0, Number(row.amount_monthly) || 0);
  return row.yearly ? yearlyToMonthly(amt) : amt;
}

function managementDeltas(rows: ManagementHireLine[]): { hq: number; byTeam: Record<string, number> } {
  let hq = 0;
  const byTeam: Record<string, number> = {};
  for (const row of rows) {
    const amount = Math.max(0, Number(row.headcount) || 0) * Math.max(0, Number(row.salary_monthly_each) || 0);
    if (row.attribution === 'hq') {
      hq = round2(hq + amount);
    } else if (row.team_id) {
      byTeam[row.team_id] = round2((byTeam[row.team_id] || 0) + amount);
    }
  }
  return { hq, byTeam };
}

function facilityDeltas(rows: FacilityLine[]): {
  hqOpex: number;
  hqCapex: number;
  byTeam: Record<string, number>;
} {
  let hqOpex = 0;
  let hqCapex = 0;
  const byTeam: Record<string, number> = {};
  for (const row of rows) {
    const amt = monthlyAmount(Math.max(0, Number(row.amount_monthly) || 0), row.yearly);
    const isCapex = row.category === 'capex';
    if (row.attribution === 'hq') {
      if (isCapex) hqCapex = round2(hqCapex + amt);
      else hqOpex = round2(hqOpex + amt);
    } else if (row.team_id) {
      byTeam[row.team_id] = round2((byTeam[row.team_id] || 0) + amt);
    }
  }
  return { hqOpex, hqCapex, byTeam };
}

function hqSoftwareDeltas(software: SoftwareLine[]): { opex: number; capex: number } {
  let opex = 0;
  let capex = 0;
  for (const row of software) {
    if ((row.attribution || 'team') !== 'hq') continue;
    const amt = softwareMonthly(row);
    if ((row.expense_kind || 'opex') === 'capex') capex = round2(capex + amt);
    else opex = round2(opex + amt);
  }
  return { opex, capex };
}

function teamSoftwareDelta(software: SoftwareLine[], teamId: string): number {
  return round2(
    software
      .filter((row) => (row.attribution || 'team') !== 'hq' && row.team_id === teamId)
      .reduce((sum, row) => sum + softwareMonthly(row), 0),
  );
}

export function simulatedOverheadPool(
  baseline: ScenarioBaseline,
  overhead: OverheadScenarioInput,
  extras?: {
    hqMgmt?: number;
    hqHires?: number;
    hqFacOpex?: number;
    hqFacCapex?: number;
    hqSwOpex?: number;
    hqSwCapex?: number;
  },
): number {
  const e = extras || {};
  return round2(
    baseline.overhead_pool +
      overhead.extra_hq_salary_monthly +
      overhead.extra_shared_opex_monthly +
      overhead.extra_shared_capex_monthly +
      (e.hqMgmt || 0) +
      (e.hqHires || 0) +
      (e.hqFacOpex || 0) +
      (e.hqFacCapex || 0) +
      (e.hqSwOpex || 0) +
      (e.hqSwCapex || 0),
  );
}

export function extraBillableFte(
  expansion: ExpansionScenarioInput,
  newTeams: NewTeamLine[] = [],
): number {
  const fromHires = expansion.hires.reduce((sum, row) => {
    if (!row.billable || (row.attribution || 'team') === 'hq') return sum;
    return sum + Math.max(0, Number(row.headcount) || 0);
  }, 0);
  const fromNew = newTeams.reduce((sum, row) => {
    if (!row.billable) return sum;
    return sum + Math.max(0, Number(row.delivery_headcount) || 0);
  }, 0);
  return fromHires + fromNew;
}

export function simulatedBillableFte(
  baseline: ScenarioBaseline,
  expansion: ExpansionScenarioInput,
  newTeams: NewTeamLine[] = [],
): number {
  return baseline.billable_fte + extraBillableFte(expansion, newTeams);
}

export function simulatedCpr(pool: number, billableFte: number): number {
  if (billableFte <= 0) return 0;
  return round2(pool / billableFte);
}

function hireDeltas(hires: HireLine[]): { hq: number; byTeam: Record<string, number> } {
  let hq = 0;
  const byTeam: Record<string, number> = {};
  for (const row of hires) {
    const amount =
      Math.max(0, Number(row.headcount) || 0) * Math.max(0, Number(row.salary_monthly_each) || 0);
    if ((row.attribution || 'team') === 'hq') {
      hq = round2(hq + amount);
    } else if (row.team_id) {
      byTeam[row.team_id] = round2((byTeam[row.team_id] || 0) + amount);
    }
  }
  return { hq, byTeam };
}

export function teamHireSalaryDelta(hires: HireLine[], teamId: string): number {
  return hireDeltas(hires).byTeam[teamId] || 0;
}

export function hqHireSalaryDelta(hires: HireLine[]): number {
  return hireDeltas(hires).hq;
}

export function teamExtraBillableFte(hires: HireLine[], teamId: string): number {
  return hires
    .filter(
      (row) =>
        row.team_id === teamId &&
        row.billable &&
        (row.attribution || 'team') !== 'hq',
    )
    .reduce((sum, row) => sum + Math.max(0, Number(row.headcount) || 0), 0);
}

export type SharedOverheadBreakdown = {
  live_management_salary: number;
  live_shared_opex: number;
  live_shared_capex: number;
  live_pool: number;
  scenario_extra_salary: number;
  scenario_extra_opex: number;
  scenario_extra_capex: number;
  scenario_management_hq: number;
  scenario_hires_hq: number;
  scenario_facility_hq_opex: number;
  scenario_facility_hq_capex: number;
  scenario_software_hq_opex: number;
  scenario_software_hq_capex: number;
  scenario_additions_total: number;
  simulated_pool: number;
};

export type SimulatedTeamResult = {
  team_id: string;
  team_name: string;
  revenue: number;
  current_net: number;
  current_operating: number;
  simulated_direct: number;
  simulated_allocated: number;
  simulated_operating: number;
  simulated_net: number;
  simulated_after_tax: number;
  delta_operating: number;
  break_even_revenue: number;
  break_even_revenue_after_tax: number;
  is_new_team?: boolean;
};

export type ScenarioResult = {
  simulated_pool: number;
  delta_pool: number;
  simulated_billable_fte: number;
  simulated_cpr: number;
  delta_cpr: number;
  company_direct_delta: number;
  company_simulated_operating: number;
  delta_company_operating: number;
  shared_overhead: SharedOverheadBreakdown;
  teams: SimulatedTeamResult[];
};

export function computeScenario(
  baseline: ScenarioBaseline,
  overhead: OverheadScenarioInput,
  expansion: ExpansionScenarioInput,
  v2?: Pick<ScenarioDraft, 'new_teams' | 'management_hires' | 'facility_lines'>,
): ScenarioResult {
  const newTeams = v2?.new_teams ?? [];
  const mgmt = managementDeltas(v2?.management_hires ?? []);
  const fac = facilityDeltas(v2?.facility_lines ?? []);
  const swHq = hqSoftwareDeltas(expansion.software);
  const hiresHq = hqHireSalaryDelta(expansion.hires);

  const scenarioExtraOpex = overhead.extra_shared_opex_monthly;
  const scenarioExtraCapex = overhead.extra_shared_capex_monthly;
  const scenarioAdditions = round2(
    overhead.extra_hq_salary_monthly +
      scenarioExtraOpex +
      scenarioExtraCapex +
      mgmt.hq +
      hiresHq +
      fac.hqOpex +
      fac.hqCapex +
      swHq.opex +
      swHq.capex,
  );

  const pool = simulatedOverheadPool(baseline, overhead, {
    hqMgmt: mgmt.hq,
    hqHires: hiresHq,
    hqFacOpex: fac.hqOpex,
    hqFacCapex: fac.hqCapex,
    hqSwOpex: swHq.opex,
    hqSwCapex: swHq.capex,
  });
  const fte = simulatedBillableFte(baseline, expansion, newTeams);
  const cpr = simulatedCpr(pool, fte);
  const tax = baseline.corporate_tax_percent;

  let companyDirectDelta = 0;
  const teams: SimulatedTeamResult[] = [];

  for (const team of baseline.teams) {
    if (team.is_overhead_home) continue;

    const hireSal = teamHireSalaryDelta(expansion.hires, team.team_id);
    const soft = teamSoftwareDelta(expansion.software, team.team_id);
    const mgmtTeam = mgmt.byTeam[team.team_id] || 0;
    const facTeam = fac.byTeam[team.team_id] || 0;
    const simulatedDirect = round2(team.direct_operating + hireSal + soft + mgmtTeam + facTeam);
    const extraFte = teamExtraBillableFte(expansion.hires, team.team_id);
    const simulatedFte = team.billable_fte + extraFte;
    const simulatedAllocated = round2(cpr * simulatedFte);
    const simulatedOperating = round2(simulatedDirect + simulatedAllocated);
    const simulatedNet = round2(team.revenue - team.estimated_cost - simulatedOperating);
    const simulatedAfterTax = afterTaxNet(simulatedNet, tax);
    const deltaOp = round2(simulatedOperating - team.operating);
    const breakEven = simulatedOperating;
    const breakEvenAfterTax = round2(simulatedOperating + team.estimated_cost);

    companyDirectDelta = round2(companyDirectDelta + hireSal + soft + mgmtTeam + facTeam);

    teams.push({
      team_id: team.team_id,
      team_name: team.team_name,
      revenue: team.revenue,
      current_net: team.net_profit,
      current_operating: team.operating,
      simulated_direct: simulatedDirect,
      simulated_allocated: simulatedAllocated,
      simulated_operating: simulatedOperating,
      simulated_net: simulatedNet,
      simulated_after_tax: simulatedAfterTax,
      delta_operating: deltaOp,
      break_even_revenue: breakEven,
      break_even_revenue_after_tax: breakEvenAfterTax,
      is_new_team: false,
    });
  }

  for (const row of newTeams) {
    const headcount = Math.max(0, Number(row.delivery_headcount) || 0);
    const salaryEach = Math.max(0, Number(row.salary_monthly_each) || 0);
    const direct = round2(headcount * salaryEach);
    const opex = newTeamOpexMonthly(row);
    const soft = teamSoftwareDelta(expansion.software, row.id);
    const mgmtTeam = mgmt.byTeam[row.id] || 0;
    const facTeam = fac.byTeam[row.id] || 0;
    const simulatedDirect = round2(direct + opex + soft + mgmtTeam + facTeam);
    const simulatedFte = row.billable ? headcount : 0;
    const simulatedAllocated = round2(cpr * simulatedFte);
    const simulatedOperating = round2(simulatedDirect + simulatedAllocated);
    const revenue = newTeamMonthlyRevenue(row);
    const simulatedNet = round2(revenue - simulatedOperating);
    const simulatedAfterTax = afterTaxNet(simulatedNet, tax);
    const breakEven = simulatedOperating;
    const breakEvenAfterTax = simulatedOperating;

    companyDirectDelta = round2(companyDirectDelta + direct + opex + soft + mgmtTeam + facTeam);

    teams.push({
      team_id: row.id,
      team_name: row.name || 'New team',
      revenue,
      current_net: 0,
      current_operating: 0,
      simulated_direct: simulatedDirect,
      simulated_allocated: simulatedAllocated,
      simulated_operating: simulatedOperating,
      simulated_net: simulatedNet,
      simulated_after_tax: simulatedAfterTax,
      delta_operating: simulatedOperating,
      break_even_revenue: breakEven,
      break_even_revenue_after_tax: breakEvenAfterTax,
      is_new_team: true,
    });
  }

  const companySimOperating = round2(
    baseline.company_operating + companyDirectDelta + (pool - baseline.overhead_pool),
  );

  const breakdown = baseline.overhead_breakdown;

  return {
    simulated_pool: pool,
    delta_pool: round2(pool - baseline.overhead_pool),
    simulated_billable_fte: fte,
    simulated_cpr: cpr,
    delta_cpr: round2(cpr - baseline.cpr),
    company_direct_delta: companyDirectDelta,
    company_simulated_operating: companySimOperating,
    delta_company_operating: round2(companySimOperating - baseline.company_operating),
    shared_overhead: {
      live_management_salary: breakdown?.management_salary ?? baseline.overhead_pool,
      live_shared_opex: breakdown?.shared_opex ?? 0,
      live_shared_capex: breakdown?.shared_capex ?? 0,
      live_pool: baseline.overhead_pool,
      scenario_extra_salary: overhead.extra_hq_salary_monthly,
      scenario_extra_opex: scenarioExtraOpex,
      scenario_extra_capex: scenarioExtraCapex,
      scenario_management_hq: mgmt.hq,
      scenario_hires_hq: hiresHq,
      scenario_facility_hq_opex: fac.hqOpex,
      scenario_facility_hq_capex: fac.hqCapex,
      scenario_software_hq_opex: swHq.opex,
      scenario_software_hq_capex: swHq.capex,
      scenario_additions_total: scenarioAdditions,
      simulated_pool: pool,
    },
    teams,
  };
}

export const SCENARIO_STORAGE_KEY = 'protrack.finance.scenarios.draft.v2';

export function emptyDraft(): ScenarioDraft {
  return {
    schema_version: 2,
    overhead: {
      extra_hq_salary_monthly: 0,
      extra_shared_opex_monthly: 0,
      extra_shared_capex_monthly: 0,
    },
    expansion: { hires: [], software: [] },
    opex_yearly: false,
    capex_yearly: false,
    new_teams: [],
    management_hires: [],
    facility_lines: [],
  };
}

export function draftPayload(draft: ScenarioDraft): ScenarioDraft {
  return {
    ...draft,
    schema_version: 2,
    overhead: {
      ...draft.overhead,
      opex_yearly: draft.opex_yearly,
      capex_yearly: draft.capex_yearly,
    },
  };
}

export function loadDraft(): ScenarioDraft | null {
  try {
    const raw = localStorage.getItem(SCENARIO_STORAGE_KEY);
    if (!raw) {
      const legacy = localStorage.getItem('protrack.finance.scenarios.draft.v1');
      if (!legacy) return null;
      const parsed = JSON.parse(legacy) as Partial<ScenarioDraft>;
      return {
        ...emptyDraft(),
        ...parsed,
        overhead: { ...emptyDraft().overhead, ...(parsed.overhead || {}) },
        expansion: { ...emptyDraft().expansion, ...(parsed.expansion || {}) },
      };
    }
    const parsed = JSON.parse(raw) as ScenarioDraft;
    if (!parsed?.overhead || !parsed?.expansion) return null;
    return {
      ...emptyDraft(),
      ...parsed,
      overhead: { ...emptyDraft().overhead, ...parsed.overhead },
      expansion: {
        hires: parsed.expansion?.hires ?? [],
        software: parsed.expansion?.software ?? [],
      },
      new_teams: (parsed.new_teams ?? []).map((t) => ({
        ...t,
        opex_lines: normalizeNewTeamOpexLines(t),
      })),
      management_hires: parsed.management_hires ?? [],
      facility_lines: parsed.facility_lines ?? [],
    };
  } catch {
    return null;
  }
}

export function saveDraft(draft: ScenarioDraft): void {
  try {
    localStorage.setItem(SCENARIO_STORAGE_KEY, JSON.stringify(draftPayload(draft)));
  } catch {
    /* ignore quota */
  }
}

export function clearDraft(): void {
  try {
    localStorage.removeItem(SCENARIO_STORAGE_KEY);
    localStorage.removeItem('protrack.finance.scenarios.draft.v1');
  } catch {
    /* ignore */
  }
}

export function newId(): string {
  return `${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

export function newTeamId(): string {
  return `new_${newId()}`;
}
