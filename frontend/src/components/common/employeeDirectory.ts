import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchAssignableEmployees, itAllocationKeys } from '../../api/itAllocation';
import type { EmployeeRosterRow } from '../../types/ResourceShifts';

export function employeeShiftLabel(
  row: Pick<EmployeeRosterRow, 'shift_state' | 'shift_display' | 'shift_name'>,
): string {
  if (row.shift_state === 'INACTIVE') return 'Inactive';
  if (row.shift_state === 'NOT_ASSIGNED') return 'Not Assigned';
  return row.shift_display || row.shift_name || 'Assigned';
}

/** "Name (ID) · Department · Designation · Shift" — searchable by any of those parts. */
export function employeeOptionLabel(row: EmployeeRosterRow): string {
  return [
    `${row.name}${row.employee_code ? ` (${row.employee_code})` : ''}`,
    row.department || 'No department',
    row.designation,
    `Shift: ${employeeShiftLabel(row)}`,
  ]
    .filter(Boolean)
    .join(' · ');
}

/** Active employees from the Employee Master (IT allocation directory) as select options. */
export function useAssignableEmployees(enabled = true) {
  const params = { status: 'active' as const };
  const query = useQuery({
    queryKey: itAllocationKeys.employees(params),
    queryFn: () => fetchAssignableEmployees(params),
    staleTime: 30_000,
    enabled,
  });
  const options = useMemo(
    () => (query.data?.rows ?? []).map((row) => ({ value: row.user_id, label: employeeOptionLabel(row) })),
    [query.data],
  );
  const byId = useMemo(() => new Map((query.data?.rows ?? []).map((row) => [row.user_id, row])), [query.data]);
  return { query, options, byId };
}
