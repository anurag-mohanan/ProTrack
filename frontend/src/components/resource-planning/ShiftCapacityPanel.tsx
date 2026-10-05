import { Box, Chip, Stack, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { fetchShiftCapacity, resourceShiftKeys } from '../../api/resourceShifts';
import { QUERY_STALE_TIMES } from '../../config/queryConfig';
import { LoadingState } from '../common/LoadingState';
import { ErrorState } from '../common/ErrorState';
import { DashboardPanel } from '../ui/design-system';

/** Employees, workstations and concurrent license rights per shift (allocation engine). */
export function ShiftCapacityPanel({ date }: { date: string }) {
  const query = useQuery({
    queryKey: resourceShiftKeys.capacity({ date }),
    queryFn: () => fetchShiftCapacity({ date }),
    staleTime: QUERY_STALE_TIMES.dashboard,
  });

  return (
    <DashboardPanel title="Capacity by shift" subtitle={`Employees, workstations and floating licenses · ${date}`}>
      {query.isLoading ? (
        <LoadingState message="Loading capacity…" />
      ) : query.error ? (
        <ErrorState error={query.error} />
      ) : (
        <Stack spacing={1.5}>
          {query.data && query.data.employees_without_shift > 0 ? (
            <Typography variant="body2" color="warning.main">
              {query.data.employees_without_shift} active employee(s) have no shift assigned.
            </Typography>
          ) : null}
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} useFlexGap>
            {(query.data?.shifts ?? []).map((row) => (
              <Box
                key={row.shift_code}
                sx={{ flex: 1, minWidth: 220, p: 1.5, border: '1px solid', borderColor: 'divider', borderRadius: 2 }}
              >
                <Typography variant="subtitle2">{row.shift_display}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {row.window}
                </Typography>
                <Stack spacing={0.5} sx={{ mt: 1 }}>
                  <Typography variant="body2">
                    <strong>{row.employees}</strong> employees
                  </Typography>
                  <Typography variant="body2">
                    Workstations: <strong>{row.workstations.assigned}</strong> assigned ·{' '}
                    <strong>{row.workstations.available}</strong> available
                    {row.workstations.blocked ? ` · ${row.workstations.blocked} blocked` : ''}
                  </Typography>
                  <Typography variant="body2">
                    Laptops: <strong>{row.laptops.assigned}</strong> assigned · <strong>{row.laptops.available}</strong>{' '}
                    available
                  </Typography>
                  {row.licenses.length ? (
                    <Stack direction="row" spacing={0.5} useFlexGap sx={{ flexWrap: 'wrap', pt: 0.5 }}>
                      {row.licenses.map((lic) => (
                        <Chip
                          key={lic.license_pool_id}
                          size="small"
                          variant="outlined"
                          color={lic.available > 0 ? 'success' : 'warning'}
                          label={`${lic.software_name ?? lic.entitlement_code ?? 'License'} ${lic.scheduled}/${lic.rights} used · ${lic.available} free`}
                        />
                      ))}
                    </Stack>
                  ) : (
                    <Typography variant="caption" color="text.secondary">
                      No floating license pools.
                    </Typography>
                  )}
                </Stack>
              </Box>
            ))}
          </Stack>
        </Stack>
      )}
    </DashboardPanel>
  );
}
