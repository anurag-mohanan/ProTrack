import { useMemo, useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Checkbox,
  FormControlLabel,
  Grid,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import {
  computeWhatIf,
  defaultWhatIfInputs,
  summarizeWhatIfDelta,
  whatIfPreset,
  WHAT_IF_INPUT_HELP,
  type WhatIfCaseKey,
  type WhatIfInputs,
} from '../../utils/financeWhatIf';
import { FinanceSection, financeMoney } from './FinanceCockpitPrimitives';

type Props = {
  currencyCode?: string;
  baselineHeadcount?: number;
  baselineRevenueMonthly?: number;
  value?: WhatIfInputs;
  onChange?: (next: WhatIfInputs) => void;
};

function FieldHelp({ field }: { field: keyof WhatIfInputs }) {
  const help = WHAT_IF_INPUT_HELP[field];
  return (
    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25 }}>
      {help.description} — {help.why}
    </Typography>
  );
}

export function FinanceWhatIfPanel({
  currencyCode = 'INR',
  baselineHeadcount,
  baselineRevenueMonthly,
  value,
  onChange,
}: Props) {
  const [local, setLocal] = useState<WhatIfInputs>(() =>
    defaultWhatIfInputs({
      headcount: baselineHeadcount && baselineHeadcount > 0 ? baselineHeadcount : 10,
      average_project_value:
        baselineRevenueMonthly && baselineRevenueMonthly > 0
          ? Math.round(baselineRevenueMonthly / 2)
          : 500000,
    }),
  );
  const inputs = value ?? local;
  const setInputs = (next: WhatIfInputs) => {
    if (onChange) onChange(next);
    else setLocal(next);
  };

  const baselineInputs = useMemo(
    () =>
      defaultWhatIfInputs({
        ...inputs,
        planned_hires: 0,
        expected_attrition: 0,
        cost_increase_percent: 0,
        utilization_percent: Math.min(inputs.utilization_percent, 75),
      }),
    // freeze baseline against initial scenario shape for comparison labels
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const current = useMemo(() => computeWhatIf(baselineInputs), [baselineInputs]);
  const scenario = useMemo(() => computeWhatIf(inputs), [inputs]);
  const cases = useMemo(() => {
    const keys: WhatIfCaseKey[] = ['base', 'best', 'worst'];
    return keys.map((key) => ({
      key,
      result: computeWhatIf(key === 'base' ? inputs : whatIfPreset(inputs, key)),
    }));
  }, [inputs]);

  const money = (n: number) => financeMoney(n, currencyCode);
  const summary = summarizeWhatIfDelta(current, scenario, money);

  const numField = (field: keyof WhatIfInputs, label: string) => (
    <Box>
      <TextField
        size="small"
        fullWidth
        type="number"
        label={label}
        value={inputs[field] as number | boolean}
        onChange={(e) =>
          setInputs({ ...inputs, [field]: e.target.value === '' ? 0 : Number(e.target.value) })
        }
      />
      <FieldHelp field={field} />
    </Box>
  );

  return (
    <Stack spacing={2}>
      <FinanceSection
        title="Business what-if model"
        subtitle="Transparent capacity, revenue, cost, profit, and break-even — every result shows its formula."
      >
        <Stack direction="row" spacing={1} sx={{ mb: 1.5, flexWrap: 'wrap' }}>
          {(['base', 'best', 'worst'] as WhatIfCaseKey[]).map((key) => (
            <Button
              key={key}
              size="small"
              variant={key === 'base' ? 'contained' : 'outlined'}
              onClick={() => setInputs(whatIfPreset(inputs, key === 'base' ? 'base' : key))}
            >
              {key === 'base' ? 'Base case' : key === 'best' ? 'Best case' : 'Worst case'}
            </Button>
          ))}
        </Stack>

        <Alert severity="info" sx={{ mb: 2 }}>
          {summary}
        </Alert>

        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700 }}>
          1. Revenue assumptions
        </Typography>
        <Grid container spacing={1.5} sx={{ mb: 2 }}>
          <Grid size={{ xs: 12, sm: 6, md: 4 }}>{numField('expected_projects', 'Expected projects')}</Grid>
          <Grid size={{ xs: 12, sm: 6, md: 4 }}>
            {numField('average_project_value', 'Average project value')}
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 4 }}>{numField('win_rate_percent', 'Win rate %')}</Grid>
          <Grid size={{ xs: 12, sm: 6, md: 4 }}>{numField('pipeline_value', 'Quoted pipeline')}</Grid>
          <Grid size={{ xs: 12, sm: 6, md: 4 }}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={inputs.use_pipeline}
                  onChange={(e) => setInputs({ ...inputs, use_pipeline: e.target.checked })}
                />
              }
              label="Use pipeline × win rate"
            />
            <FieldHelp field="use_pipeline" />
          </Grid>
        </Grid>

        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700 }}>
          2. Resource assumptions
        </Typography>
        <Grid container spacing={1.5} sx={{ mb: 2 }}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>{numField('headcount', 'Current headcount')}</Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>{numField('planned_hires', 'Planned hires')}</Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>{numField('expected_attrition', 'Attrition')}</Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>{numField('working_days', 'Working days')}</Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>{numField('hours_per_day', 'Hours / day')}</Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>{numField('utilization_percent', 'Utilization %')}</Grid>
        </Grid>

        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700 }}>
          3. Cost & project assumptions
        </Typography>
        <Grid container spacing={1.5} sx={{ mb: 2 }}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            {numField('average_cost_per_hour', 'Cost / hour')}
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>{numField('other_costs', 'Other costs')}</Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            {numField('cost_increase_percent', 'Cost increase %')}
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            {numField('average_hours_per_project', 'Hours / project')}
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            {numField('margin_target_percent', 'Margin target %')}
          </Grid>
        </Grid>

        {scenario.warnings.length > 0 ? (
          <Stack spacing={1} sx={{ mb: 2 }}>
            {scenario.warnings.map((w) => (
              <Alert key={w} severity="warning">
                {w}
              </Alert>
            ))}
          </Stack>
        ) : null}

        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700 }}>
          Current vs scenario
        </Typography>
        <Table size="small" sx={{ mb: 2 }}>
          <TableHead>
            <TableRow>
              <TableCell>Metric</TableCell>
              <TableCell align="right">Current</TableCell>
              <TableCell align="right">Scenario</TableCell>
              <TableCell align="right">Δ</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(
              [
                ['Revenue', current.expected_revenue, scenario.expected_revenue, true],
                ['Total cost', current.total_cost, scenario.total_cost, true],
                ['Gross profit', current.gross_profit, scenario.gross_profit, true],
                ['Gross margin %', current.gross_margin_percent, scenario.gross_margin_percent, false],
                ['Headcount', current.scenario_headcount, scenario.scenario_headcount, false],
                ['Productive hours', current.productive_hours, scenario.productive_hours, false],
                ['Capacity gap', current.capacity_gap, scenario.capacity_gap, false],
              ] as const
            ).map(([label, cur, scen, isMoney]) => (
              <TableRow key={label}>
                <TableCell>{label}</TableCell>
                <TableCell align="right">{isMoney ? money(cur) : cur.toFixed(1)}</TableCell>
                <TableCell align="right">{isMoney ? money(scen) : scen.toFixed(1)}</TableCell>
                <TableCell align="right">
                  {isMoney ? money(scen - cur) : (scen - cur).toFixed(1)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>

        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700 }}>
          Base / Best / Worst
        </Typography>
        <Table size="small" sx={{ mb: 2 }}>
          <TableHead>
            <TableRow>
              <TableCell>Metric</TableCell>
              <TableCell align="right">Base</TableCell>
              <TableCell align="right">Best</TableCell>
              <TableCell align="right">Worst</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(
              [
                ['Revenue', 'expected_revenue', true],
                ['Cost', 'total_cost', true],
                ['Profit', 'gross_profit', true],
                ['Margin %', 'gross_margin_percent', false],
                ['Capacity gap', 'capacity_gap', false],
              ] as const
            ).map(([label, key, isMoney]) => (
              <TableRow key={label}>
                <TableCell>{label}</TableCell>
                {cases.map((c) => (
                  <TableCell key={c.key} align="right">
                    {isMoney
                      ? money(c.result[key] as number)
                      : (c.result[key] as number).toFixed(1)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>

        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700 }}>
          How is this calculated?
        </Typography>
        {scenario.steps.map((step) => (
          <Accordion key={step.label} disableGutters>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography sx={{ fontWeight: 600 }}>
                {step.label}:{' '}
                {step.unit === 'currency'
                  ? money(step.result)
                  : step.unit === '%'
                    ? `${step.result}%`
                    : step.result}
              </Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant="body2" sx={{ mb: 0.5 }}>
                Formula: {step.expression}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Values: {step.substituted}
              </Typography>
              <Typography variant="body2" sx={{ mt: 0.5, fontWeight: 600 }}>
                Result:{' '}
                {step.unit === 'currency'
                  ? money(step.result)
                  : step.unit === '%'
                    ? `${step.result}%`
                    : `${step.result}${step.unit ? ` ${step.unit}` : ''}`}
              </Typography>
            </AccordionDetails>
          </Accordion>
        ))}
      </FinanceSection>
    </Stack>
  );
}
