import { useMemo, useState } from 'react';
import { Autocomplete, Box, Chip, Stack, TextField, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { fetchAssignableEmployees, itAllocationKeys } from '../../api/itAllocation';
import { fetchEmployeeRoster, resourceShiftKeys } from '../../api/resourceShifts';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import type { EmployeeRosterRow } from '../../types/ResourceShifts';
import { employeeShiftLabel } from './employeeDirectory';

type Props = {
  value: string;
  onChange: (employee: EmployeeRosterRow | null) => void;
  /** `it` uses the IT allocation directory, `shifts` the Resource Planning shift roster. */
  source?: 'it' | 'shifts';
  label?: string;
  required?: boolean;
  disabled?: boolean;
  helperText?: string;
};

export function EmployeeShiftChip({ row }: { row: EmployeeRosterRow }) {
  const color = row.shift_state === 'ASSIGNED' ? 'primary' : row.shift_state === 'NOT_ASSIGNED' ? 'warning' : 'default';
  return <Chip size="small" variant="outlined" color={color} label={employeeShiftLabel(row)} />;
}

/**
 * Employee selector backed by the full Employee Master (not team- or timesheet-scoped):
 * search by name, employee ID, department or designation; each option shows the current shift.
 */
export function EmployeePicker({
  value,
  onChange,
  source = 'it',
  label = 'Employee',
  required,
  disabled,
  helperText,
}: Props) {
  const [input, setInput] = useState('');
  const q = useDebouncedValue(input.trim(), 250);
  const params = { status: 'active' as const, q: q || undefined };
  const query = useQuery({
    queryKey: source === 'it' ? itAllocationKeys.employees(params) : resourceShiftKeys.roster(params),
    queryFn: () => (source === 'it' ? fetchAssignableEmployees(params) : fetchEmployeeRoster(params)),
    staleTime: 30_000,
    enabled: !disabled,
  });
  const [selected, setSelected] = useState<EmployeeRosterRow | null>(null);
  const options = useMemo(() => {
    const rows = query.data?.rows ?? [];
    if (selected && selected.user_id === value && !rows.some((r) => r.user_id === selected.user_id)) {
      return [selected, ...rows];
    }
    return rows;
  }, [query.data, selected, value]);
  const current = options.find((row) => row.user_id === value) ?? null;

  return (
    <Autocomplete
      options={options}
      value={current}
      disabled={disabled}
      loading={query.isFetching}
      filterOptions={(rows) => rows}
      getOptionLabel={(row) => row.name}
      isOptionEqualToValue={(a, b) => a.user_id === b.user_id}
      onInputChange={(_e, next, reason) => {
        if (reason === 'input' || reason === 'clear') setInput(next);
      }}
      onChange={(_e, row) => {
        setSelected(row);
        if (!row) setInput('');
        onChange(row);
      }}
      noOptionsText={query.isError ? 'Could not load employees' : 'No matching active employees'}
      renderOption={(props, row) => {
        const { key, ...rest } = props as typeof props & { key: string };
        return (
          <Box component="li" key={key} {...rest}>
            <Stack sx={{ width: '100%' }} spacing={0.25}>
              <Stack direction="row" spacing={1} sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {row.name}
                  {row.employee_code ? ` · ${row.employee_code}` : ''}
                </Typography>
                <EmployeeShiftChip row={row} />
              </Stack>
              <Typography variant="caption" color="text.secondary">
                {[row.department || 'No department', row.designation].filter(Boolean).join(' · ')}
              </Typography>
            </Stack>
          </Box>
        );
      }}
      renderInput={(inputProps) => (
        <TextField
          {...inputProps}
          label={label}
          required={required}
          size="small"
          placeholder="Search name, ID, department, designation"
          helperText={
            helperText ??
            (current
              ? `${current.department || 'No department'} · Shift: ${employeeShiftLabel(current)}`
              : undefined)
          }
        />
      )}
    />
  );
}
