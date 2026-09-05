/**
 * Transparent business what-if calculator for Finance Scenario Planning.
 * Mirrored in app/services/finance/what_if_calculator.py for CI.
 */

export type WhatIfInputs = {
  expected_projects: number;
  average_project_value: number;
  win_rate_percent: number;
  pipeline_value: number;
  use_pipeline: boolean;
  headcount: number;
  planned_hires: number;
  expected_attrition: number;
  working_days: number;
  hours_per_day: number;
  utilization_percent: number;
  average_cost_per_hour: number;
  other_costs: number;
  cost_increase_percent: number;
  average_hours_per_project: number;
  margin_target_percent: number;
  /** schema_version >= 4 — cash & financing */
  opening_cash: number;
  collections_realization_percent: number;
  extra_loan_emi_monthly: number;
  od_interest_monthly: number;
  investment_income_monthly: number;
  one_time_capex_cash: number;
  minimum_cash_reserve: number;
};

export type FormulaStep = {
  label: string;
  expression: string;
  substituted: string;
  result: number;
  unit?: string;
};

export type WhatIfResult = {
  scenario_headcount: number;
  available_hours: number;
  productive_hours: number;
  expected_projects_won: number;
  expected_revenue: number;
  required_project_hours: number;
  labor_cost: number;
  other_costs_adjusted: number;
  total_cost: number;
  gross_profit: number;
  gross_margin_percent: number;
  capacity_gap: number;
  headcount_required: number;
  break_even_revenue: number;
  break_even_projects: number;
  revenue_per_employee: number;
  profit_per_employee: number;
  expected_collections: number;
  cash_inflows: number;
  cash_outflows: number;
  net_cash_flow: number;
  ending_cash: number;
  scenario_runway_months: number | null;
  cash_status: 'cash_generative' | 'burning' | 'missing_opening_cash';
  steps: FormulaStep[];
  warnings: string[];
};

export const WHAT_IF_INPUT_HELP: Record<
  keyof WhatIfInputs,
  { label: string; unit: string; description: string; why: string }
> = {
  expected_projects: {
    label: 'Expected projects',
    unit: 'count',
    description: 'Number of new projects you expect to win in the planning period.',
    why: 'Drives expected revenue when not using pipeline × win rate.',
  },
  average_project_value: {
    label: 'Average project value',
    unit: 'currency',
    description: 'Typical awarded value per project.',
    why: 'Used with project count (or break-even projects) to size revenue.',
  },
  win_rate_percent: {
    label: 'Expected win rate',
    unit: '%',
    description: 'Share of pipeline expected to convert to awards.',
    why: 'Converts quoted pipeline into expected awarded value.',
  },
  pipeline_value: {
    label: 'Quoted pipeline',
    unit: 'currency',
    description: 'Total value of open quotes in the pipeline.',
    why: 'Base for pipeline-based revenue when enabled.',
  },
  use_pipeline: {
    label: 'Use pipeline × win rate',
    unit: 'flag',
    description: 'When on, revenue = pipeline × win rate instead of projects × average value.',
    why: 'Lets you model conversion of an existing quote pipeline.',
  },
  headcount: {
    label: 'Current headcount',
    unit: 'people',
    description: 'Designers/engineers available today.',
    why: 'Starting point for capacity and labor cost.',
  },
  planned_hires: {
    label: 'Planned hires',
    unit: 'people',
    description: 'Additional people planned in this scenario.',
    why: 'Increases capacity and labor cost.',
  },
  expected_attrition: {
    label: 'Expected attrition',
    unit: 'people',
    description: 'People expected to leave in the period.',
    why: 'Reduces available headcount.',
  },
  working_days: {
    label: 'Working days',
    unit: 'days',
    description: 'Working days in the planning period.',
    why: 'Sets available calendar capacity.',
  },
  hours_per_day: {
    label: 'Hours per day',
    unit: 'hours',
    description: 'Standard productive working hours per day.',
    why: 'Converts days into available hours.',
  },
  utilization_percent: {
    label: 'Utilization',
    unit: '%',
    description: 'Share of available time spent on productive/project work.',
    why: 'Higher utilization increases productive capacity without hiring.',
  },
  average_cost_per_hour: {
    label: 'Average cost per hour',
    unit: 'currency/hour',
    description: 'Fully loaded average labor cost rate.',
    why: 'Turns productive hours into labor cost.',
  },
  other_costs: {
    label: 'Other costs',
    unit: 'currency',
    description: 'Non-labor costs (tools, overhead share, contractors, etc.).',
    why: 'Added to labor to get total cost and break-even.',
  },
  cost_increase_percent: {
    label: 'Cost increase',
    unit: '%',
    description: 'Assumed uplift applied to other costs.',
    why: 'Models inflation or overhead growth.',
  },
  average_hours_per_project: {
    label: 'Average hours per project',
    unit: 'hours',
    description: 'Expected delivery hours per won project.',
    why: 'Determines required capacity vs productive hours.',
  },
  margin_target_percent: {
    label: 'Margin target',
    unit: '%',
    description: 'Minimum acceptable gross margin for warnings.',
    why: 'Flags scenarios that fall below your target.',
  },
  opening_cash: {
    label: 'Opening cash',
    unit: 'currency',
    description: 'Bank + cash available at the start of the scenario period.',
    why: 'Baseline for ending cash and runway (from Treasury cash position when seeded).',
  },
  collections_realization_percent: {
    label: 'Collections realization',
    unit: '%',
    description: 'Share of expected revenue you expect to collect as cash in the period.',
    why: 'Separates P&L turnover from cash collections (payment timing).',
  },
  extra_loan_emi_monthly: {
    label: 'Loan EMI / repayments',
    unit: 'currency',
    description: 'Cash loan repayments in the period (principal + interest cash outflow).',
    why: 'Principal is financing/cash, not P&L expense; still reduces cash.',
  },
  od_interest_monthly: {
    label: 'OD interest',
    unit: 'currency',
    description: 'Overdraft interest/charges expected in the period.',
    why: 'OD interest is finance cost and cash outflow; OD drawdown is not revenue.',
  },
  investment_income_monthly: {
    label: 'Investment income',
    unit: 'currency',
    description: 'Cash income expected from investments in the period.',
    why: 'Investment income increases cash; purchases are modeled separately as CapEx cash.',
  },
  one_time_capex_cash: {
    label: 'One-time CapEx cash',
    unit: 'currency',
    description: 'Cash spent on capital purchases in the period.',
    why: 'CapEx is cash + asset — not automatic operating expense.',
  },
  minimum_cash_reserve: {
    label: 'Minimum cash reserve',
    unit: 'currency',
    description: 'Floor cash balance that should not be breached.',
    why: 'Triggers a warning when projected ending cash falls below the reserve.',
  },
};

export function defaultWhatIfInputs(partial?: Partial<WhatIfInputs>): WhatIfInputs {
  return {
    expected_projects: 10,
    average_project_value: 500000,
    win_rate_percent: 70,
    pipeline_value: 0,
    use_pipeline: false,
    headcount: 10,
    planned_hires: 0,
    expected_attrition: 0,
    working_days: 21,
    hours_per_day: 8,
    utilization_percent: 75,
    average_cost_per_hour: 1500,
    other_costs: 100000,
    cost_increase_percent: 0,
    average_hours_per_project: 120,
    margin_target_percent: 25,
    opening_cash: 0,
    collections_realization_percent: 80,
    extra_loan_emi_monthly: 0,
    od_interest_monthly: 0,
    investment_income_monthly: 0,
    one_time_capex_cash: 0,
    minimum_cash_reserve: 0,
    ...partial,
  };
}

function n(value: number): number {
  return Number.isFinite(value) ? value : 0;
}

function r2(value: number): number {
  return Math.round(n(value) * 100) / 100;
}

export function computeWhatIf(inputs: WhatIfInputs): WhatIfResult {
  const headcount = Math.max(0, n(inputs.headcount) + n(inputs.planned_hires) - n(inputs.expected_attrition));
  const available = r2(n(inputs.working_days) * n(inputs.hours_per_day) * headcount);
  const productive = r2(available * (n(inputs.utilization_percent) / 100));

  let expectedRevenue: number;
  let expectedProjectsWon: number;
  let revenueStep: FormulaStep;
  if (inputs.use_pipeline) {
    expectedRevenue = r2(n(inputs.pipeline_value) * (n(inputs.win_rate_percent) / 100));
    expectedProjectsWon =
      n(inputs.average_project_value) > 0
        ? r2(expectedRevenue / n(inputs.average_project_value))
        : 0;
    revenueStep = {
      label: 'Expected revenue',
      expression: 'Quoted pipeline × Win rate %',
      substituted: `${n(inputs.pipeline_value)} × ${n(inputs.win_rate_percent)}%`,
      result: expectedRevenue,
      unit: 'currency',
    };
  } else {
    expectedProjectsWon = n(inputs.expected_projects);
    expectedRevenue = r2(expectedProjectsWon * n(inputs.average_project_value));
    revenueStep = {
      label: 'Expected revenue',
      expression: 'Expected projects × Average project value',
      substituted: `${expectedProjectsWon} × ${n(inputs.average_project_value)}`,
      result: expectedRevenue,
      unit: 'currency',
    };
  }

  const requiredHours = r2(expectedProjectsWon * n(inputs.average_hours_per_project));
  const labor = r2(productive * n(inputs.average_cost_per_hour));
  const other = r2(n(inputs.other_costs) * (1 + n(inputs.cost_increase_percent) / 100));
  const totalCost = r2(labor + other);
  const profit = r2(expectedRevenue - totalCost);
  const margin = expectedRevenue > 0 ? r2((profit / expectedRevenue) * 100) : 0;
  const capacityGap = r2(productive - requiredHours);
  const productivePerPerson =
    headcount > 0 ? productive / headcount : n(inputs.working_days) * n(inputs.hours_per_day) * (n(inputs.utilization_percent) / 100);
  const headcountRequired =
    productivePerPerson > 0 ? r2(requiredHours / productivePerPerson) : 0;
  const contribution = expectedRevenue > 0 ? (expectedRevenue - labor) / expectedRevenue : 0;
  const breakEvenRevenue =
    contribution > 0 ? r2(other / contribution) : expectedRevenue > 0 ? 0 : other;
  const breakEvenProjects =
    n(inputs.average_project_value) > 0 ? r2(breakEvenRevenue / n(inputs.average_project_value)) : 0;

  const steps: FormulaStep[] = [
    {
      label: 'Scenario headcount',
      expression: 'Current + Planned hires − Attrition',
      substituted: `${n(inputs.headcount)} + ${n(inputs.planned_hires)} − ${n(inputs.expected_attrition)}`,
      result: headcount,
      unit: 'people',
    },
    {
      label: 'Available hours',
      expression: 'Working days × Hours/day × Headcount',
      substituted: `${n(inputs.working_days)} × ${n(inputs.hours_per_day)} × ${headcount}`,
      result: available,
      unit: 'hours',
    },
    {
      label: 'Productive hours',
      expression: 'Available hours × Utilization %',
      substituted: `${available} × ${n(inputs.utilization_percent)}%`,
      result: productive,
      unit: 'hours',
    },
    revenueStep,
    {
      label: 'Required project hours',
      expression: 'Won projects × Hours per project',
      substituted: `${expectedProjectsWon} × ${n(inputs.average_hours_per_project)}`,
      result: requiredHours,
      unit: 'hours',
    },
    {
      label: 'Labor cost',
      expression: 'Productive hours × Cost per hour',
      substituted: `${productive} × ${n(inputs.average_cost_per_hour)}`,
      result: labor,
      unit: 'currency',
    },
    {
      label: 'Other costs (adjusted)',
      expression: 'Other costs × (1 + Cost increase %)',
      substituted: `${n(inputs.other_costs)} × (1 + ${n(inputs.cost_increase_percent)}%)`,
      result: other,
      unit: 'currency',
    },
    {
      label: 'Total cost',
      expression: 'Labor cost + Other costs',
      substituted: `${labor} + ${other}`,
      result: totalCost,
      unit: 'currency',
    },
    {
      label: 'Gross profit',
      expression: 'Revenue − Total cost',
      substituted: `${expectedRevenue} − ${totalCost}`,
      result: profit,
      unit: 'currency',
    },
    {
      label: 'Gross margin %',
      expression: 'Gross profit ÷ Revenue × 100',
      substituted: `${profit} ÷ ${expectedRevenue} × 100`,
      result: margin,
      unit: '%',
    },
    {
      label: 'Capacity gap',
      expression: 'Productive hours − Required project hours',
      substituted: `${productive} − ${requiredHours}`,
      result: capacityGap,
      unit: 'hours',
    },
    {
      label: 'Break-even revenue',
      expression: 'Other costs ÷ Contribution margin',
      substituted:
        contribution > 0
          ? `${other} ÷ ${(contribution * 100).toFixed(1)}%`
          : 'Not meaningful when contribution ≤ 0',
      result: breakEvenRevenue,
      unit: 'currency',
    },
  ];

  const warnings: string[] = [];
  if (capacityGap < 0) {
    warnings.push(
      `Required project hours (${requiredHours}) exceed productive capacity (${productive}) by ${Math.abs(capacityGap)} hours.`,
    );
  }
  if (headcountRequired > headcount + 0.1) {
    warnings.push(
      `Workload implies about ${headcountRequired} people; scenario headcount is ${headcount}.`,
    );
  }
  if (n(inputs.utilization_percent) > 95) {
    warnings.push('Utilization above 95% is unusually high and may not be sustainable.');
  }
  if (margin < n(inputs.margin_target_percent)) {
    warnings.push(
      `Gross margin ${margin}% is below the ${n(inputs.margin_target_percent)}% target.`,
    );
  }
  if (n(inputs.cost_increase_percent) > 0 && expectedRevenue > 0) {
    const costGrowth = n(inputs.cost_increase_percent);
    // Compare other-cost growth vs revenue only when using explicit projects baseline.
    if (!inputs.use_pipeline && costGrowth > 0 && margin < n(inputs.margin_target_percent)) {
      warnings.push('Cost growth is pressuring margin under current revenue assumptions.');
    }
  }
  if (capacityGap > productive * 0.35 && productive > 0) {
    warnings.push('Large capacity surplus — revenue target may under-utilize the team.');
  }
  if (inputs.use_pipeline && n(inputs.pipeline_value) <= 0) {
    warnings.push('Pipeline mode is on but pipeline value is zero.');
  }

  const realization = Math.min(100, Math.max(0, n(inputs.collections_realization_percent)));
  const expectedCollections = r2(expectedRevenue * (realization / 100));
  const cashIn = r2(
    expectedCollections + n(inputs.investment_income_monthly),
  );
  const cashOut = r2(
    totalCost +
      n(inputs.extra_loan_emi_monthly) +
      n(inputs.od_interest_monthly) +
      n(inputs.one_time_capex_cash),
  );
  const netCash = r2(cashIn - cashOut);
  const openingCash = n(inputs.opening_cash);
  const endingCash = r2(openingCash + netCash);
  let cashStatus: WhatIfResult['cash_status'] = 'burning';
  let runwayMonths: number | null = null;
  if (openingCash <= 0 && n(inputs.minimum_cash_reserve) <= 0) {
    cashStatus = 'missing_opening_cash';
  } else if (netCash >= 0) {
    cashStatus = 'cash_generative';
    runwayMonths = null;
  } else {
    cashStatus = 'burning';
    runwayMonths = openingCash > 0 ? r2(openingCash / Math.abs(netCash)) : 0;
  }

  steps.push(
    {
      label: 'Expected collections',
      expression: 'Expected revenue × Collections realization %',
      substituted: `${expectedRevenue} × ${realization}%`,
      result: expectedCollections,
      unit: 'currency',
    },
    {
      label: 'Cash inflows',
      expression: 'Collections + Investment income',
      substituted: `${expectedCollections} + ${n(inputs.investment_income_monthly)}`,
      result: cashIn,
      unit: 'currency',
    },
    {
      label: 'Cash outflows',
      expression: 'Total cost + Loan EMI + OD interest + CapEx cash',
      substituted: `${totalCost} + ${n(inputs.extra_loan_emi_monthly)} + ${n(inputs.od_interest_monthly)} + ${n(inputs.one_time_capex_cash)}`,
      result: cashOut,
      unit: 'currency',
    },
    {
      label: 'Net cash flow',
      expression: 'Cash in − Cash out',
      substituted: `${cashIn} − ${cashOut}`,
      result: netCash,
      unit: 'currency',
    },
    {
      label: 'Ending cash',
      expression: 'Opening cash + Net cash flow',
      substituted: `${openingCash} + ${netCash}`,
      result: endingCash,
      unit: 'currency',
    },
  );

  if (cashStatus === 'missing_opening_cash') {
    warnings.push(
      'Opening cash is zero — set a Treasury cash position or enter opening cash for runway.',
    );
  }
  if (cashStatus === 'burning' && runwayMonths != null && runwayMonths < 3) {
    warnings.push(
      `Projected cash runway is only ${runwayMonths} months at this net burn.`,
    );
  }
  if (endingCash < n(inputs.minimum_cash_reserve)) {
    warnings.push(
      `Ending cash ${endingCash} falls below the minimum reserve ${n(inputs.minimum_cash_reserve)}.`,
    );
  }
  if (n(inputs.extra_loan_emi_monthly) > cashIn * 0.4 && cashIn > 0) {
    warnings.push('Loan repayments are high relative to expected collections.');
  }

  return {
    scenario_headcount: headcount,
    available_hours: available,
    productive_hours: productive,
    expected_projects_won: expectedProjectsWon,
    expected_revenue: expectedRevenue,
    required_project_hours: requiredHours,
    labor_cost: labor,
    other_costs_adjusted: other,
    total_cost: totalCost,
    gross_profit: profit,
    gross_margin_percent: margin,
    capacity_gap: capacityGap,
    headcount_required: headcountRequired,
    break_even_revenue: breakEvenRevenue,
    break_even_projects: breakEvenProjects,
    revenue_per_employee: headcount > 0 ? r2(expectedRevenue / headcount) : 0,
    profit_per_employee: headcount > 0 ? r2(profit / headcount) : 0,
    expected_collections: expectedCollections,
    cash_inflows: cashIn,
    cash_outflows: cashOut,
    net_cash_flow: netCash,
    ending_cash: endingCash,
    scenario_runway_months: runwayMonths,
    cash_status: cashStatus,
    steps,
    warnings,
  };
}

export type WhatIfCaseKey = 'base' | 'best' | 'worst';

export function whatIfPreset(base: WhatIfInputs, key: WhatIfCaseKey): WhatIfInputs {
  if (key === 'best') {
    return {
      ...base,
      expected_projects: Math.round(n(base.expected_projects) * 1.4),
      win_rate_percent: Math.min(95, n(base.win_rate_percent) + 10),
      utilization_percent: Math.min(95, n(base.utilization_percent) + 10),
      cost_increase_percent: Math.max(0, n(base.cost_increase_percent) - 3),
      collections_realization_percent: Math.min(95, n(base.collections_realization_percent) + 10),
    };
  }
  if (key === 'worst') {
    return {
      ...base,
      expected_projects: Math.max(0, Math.round(n(base.expected_projects) * 0.7)),
      win_rate_percent: Math.max(5, n(base.win_rate_percent) - 15),
      utilization_percent: Math.max(40, n(base.utilization_percent) - 10),
      cost_increase_percent: n(base.cost_increase_percent) + 10,
      collections_realization_percent: Math.max(40, n(base.collections_realization_percent) - 15),
      one_time_capex_cash: n(base.one_time_capex_cash) * 1.2,
    };
  }
  return { ...base };
}

export function summarizeWhatIfDelta(
  current: WhatIfResult,
  scenario: WhatIfResult,
  formatMoney: (n: number) => string,
): string {
  const revPct =
    current.expected_revenue !== 0
      ? ((scenario.expected_revenue - current.expected_revenue) / Math.abs(current.expected_revenue)) * 100
      : scenario.expected_revenue > 0
        ? 100
        : 0;
  const costPct =
    current.total_cost !== 0
      ? ((scenario.total_cost - current.total_cost) / Math.abs(current.total_cost)) * 100
      : scenario.total_cost > 0
        ? 100
        : 0;
  const profitPct =
    current.gross_profit !== 0
      ? ((scenario.gross_profit - current.gross_profit) / Math.abs(current.gross_profit)) * 100
      : scenario.gross_profit !== 0
        ? 100
        : 0;
  const dir = (v: number) => (v >= 0 ? 'increases' : 'decreases');
  return (
    `Under this scenario, expected revenue ${dir(revPct)} by ${Math.abs(revPct).toFixed(1)}% ` +
    `(${formatMoney(current.expected_revenue)} → ${formatMoney(scenario.expected_revenue)}), ` +
    `while total cost ${dir(costPct)} by ${Math.abs(costPct).toFixed(1)}%. ` +
    `This results in a projected gross profit ${dir(profitPct)} of ${Math.abs(profitPct).toFixed(1)}% ` +
    `and margin move from ${current.gross_margin_percent.toFixed(1)}% to ${scenario.gross_margin_percent.toFixed(1)}%.`
  );
}
