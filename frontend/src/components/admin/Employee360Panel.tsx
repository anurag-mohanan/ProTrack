import { Chip, Stack, Tab, Tabs, Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { fetchEmployee360, itProvisioningKeys } from '../../api/itProvisioning';
import { LoadingState } from '../common/LoadingState';
import { formatCellValue, formatDate } from '../../utils/format';

type Props = {
  userId: string;
};

export function Employee360Panel({ userId }: Props) {
  const [tab, setTab] = useState(0);
  const query = useQuery({
    queryKey: itProvisioningKeys.employee360(userId),
    queryFn: () => fetchEmployee360(userId),
    enabled: Boolean(userId),
  });

  if (query.isLoading) {
    return <LoadingState message="Loading Employee 360…" />;
  }
  if (query.isError || !query.data) {
    return (
      <Typography variant="body2" color="text.secondary">
        Employee 360 is unavailable.
      </Typography>
    );
  }

  const data = query.data;
  const overview = data.overview || {};
  const onboarding = data.onboarding;

  return (
    <Stack spacing={2}>
      <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
        <Chip
          size="small"
          color={
            onboarding?.overall === 'COMPLETE' || onboarding?.overall === 'READY'
              ? 'success'
              : onboarding?.overall === 'PARTIALLY_READY'
                ? 'warning'
                : 'default'
          }
          label={`Onboarding: ${onboarding?.overall || '—'}`}
        />
        <Chip
          size="small"
          label={`IT assets: ${data.it_assets.length}`}
        />
        <Chip size="small" label={`Licenses: ${data.software_licenses.length}`} />
        <Chip size="small" label={`Projects: ${data.projects.length}`} />
      </Stack>

      <Tabs value={tab} onChange={(_, value) => setTab(value)} variant="scrollable">
        <Tab label="Overview" />
        <Tab label="Employment" />
        <Tab label="Shift" />
        <Tab label="IT Assets" />
        <Tab label="Workstation Package" />
        <Tab label="Software & Licenses" />
        <Tab label="Performance Reviews" />
        <Tab label="Projects" />
        <Tab label="Timesheets" />
        <Tab label="Onboarding" />
      </Tabs>

      {tab === 0 ? (
        <Stack spacing={0.75}>
          <Typography variant="body2">Name: {formatCellValue(overview.name)}</Typography>
          <Typography variant="body2">Designation: {formatCellValue(overview.designation)}</Typography>
          <Typography variant="body2">Manager: {formatCellValue(overview.manager)}</Typography>
          <Typography variant="body2">Joining: {formatDate(overview.joining_date as string)}</Typography>
          <Typography variant="body2">Shift: {formatCellValue(overview.shift)}</Typography>
          <Typography variant="body2">Status: {formatCellValue(overview.status)}</Typography>
        </Stack>
      ) : null}

      {tab === 1 ? (
        <Stack spacing={0.75}>
          {Object.entries(data.employment || {}).map(([key, value]) => (
            <Typography key={key} variant="body2">
              {key}: {formatCellValue(value)}
            </Typography>
          ))}
        </Stack>
      ) : null}

      {tab === 2 ? (
        data.shift ? (
          <Stack spacing={0.75}>
            {Object.entries(data.shift).map(([key, value]) => (
              <Typography key={key} variant="body2">
                {key}: {formatCellValue(value)}
              </Typography>
            ))}
          </Stack>
        ) : (
          <Typography variant="body2" color="text.secondary">
            No active shift assignment.
          </Typography>
        )
      ) : null}

      {tab === 3 ? (
        data.it_assets.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No assigned IT assets.
          </Typography>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Asset</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Shift</TableCell>
                <TableCell>Start</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.it_assets.map((row) => (
                <TableRow key={String(row.assignment_id)}>
                  <TableCell>{formatCellValue(row.asset_number)}</TableCell>
                  <TableCell>{formatCellValue(row.asset_type)}</TableCell>
                  <TableCell>{formatCellValue(row.shift_display)}</TableCell>
                  <TableCell>{formatDate(row.assigned_date as string)}</TableCell>
                  <TableCell>{formatCellValue(row.status)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )
      ) : null}

      {tab === 4 ? (
        (data.workstation_packages || []).length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No workstation package assigned.
          </Typography>
        ) : (
          <Stack spacing={1.5}>
            {(data.workstation_packages || []).map((pkg) => {
              const assignment = (pkg.assignment || {}) as Record<string, unknown>;
              return (
                <Stack key={String(pkg.id)} spacing={0.5}>
                  <Typography variant="subtitle2">
                    {String(pkg.code)}
                    {assignment.shared ? ' · Shared Workstation' : ''}
                  </Typography>
                  <Typography variant="body2">
                    Shift: {formatCellValue(assignment.shift_display)}
                  </Typography>
                  <Typography variant="body2">
                    Computer: {formatCellValue(pkg.primary_computer_number)}
                  </Typography>
                  <Typography variant="body2">
                    Members:{' '}
                    {((pkg.members as Record<string, unknown>[]) || [])
                      .map((m) => `${m.asset_number} (${m.role})`)
                      .join(', ')}
                  </Typography>
                  {Array.isArray(assignment.other_users) && assignment.other_users.length ? (
                    <Typography variant="caption" color="text.secondary">
                      Other shift users:{' '}
                      {(assignment.other_users as { user_name?: string }[])
                        .map((u) => u.user_name)
                        .join(', ')}
                    </Typography>
                  ) : null}
                </Stack>
              );
            })}
          </Stack>
        )
      ) : null}

      {tab === 5 ? (
        data.software_licenses.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No software licenses assigned.
          </Typography>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Software</TableCell>
                <TableCell>License</TableCell>
                <TableCell>Assigned</TableCell>
                <TableCell>Expiry</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.software_licenses.map((row) => (
                <TableRow key={String(row.assignment_id)}>
                  <TableCell>{formatCellValue(row.software)}</TableCell>
                  <TableCell>{formatCellValue(row.license_id || row.license_type)}</TableCell>
                  <TableCell>{formatDate(row.assigned_date as string)}</TableCell>
                  <TableCell>{formatDate(row.expiry_date as string)}</TableCell>
                  <TableCell>{formatCellValue(row.status)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )
      ) : null}

      {tab === 6 ? (
        data.performance_reviews.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No performance reviews on record.
          </Typography>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Period</TableCell>
                <TableCell>Reviewer</TableCell>
                <TableCell>Date</TableCell>
                <TableCell>Result</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.performance_reviews.map((row) => (
                <TableRow key={String(row.id)}>
                  <TableCell>{formatCellValue(row.review_period)}</TableCell>
                  <TableCell>{formatCellValue(row.reviewer)}</TableCell>
                  <TableCell>{formatDate(row.review_date as string)}</TableCell>
                  <TableCell>{formatCellValue(row.overall_result)}</TableCell>
                  <TableCell>{formatCellValue(row.status)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )
      ) : null}

      {tab === 7 ? (
        data.projects.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No project assignments.
          </Typography>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Project</TableCell>
                <TableCell>Role</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.projects.map((row) => (
                <TableRow key={String(row.id)}>
                  <TableCell>
                    {formatCellValue(row.project_number || row.name)}
                  </TableCell>
                  <TableCell>{formatCellValue(row.role)}</TableCell>
                  <TableCell>{formatCellValue(row.status)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )
      ) : null}

      {tab === 8 ? (
        <Stack spacing={0.75}>
          <Typography variant="body2">
            Current month hours: {formatCellValue(data.timesheets.current_month_hours)}
          </Typography>
          <Typography variant="body2">
            Projects worked: {formatCellValue(data.timesheets.projects_worked)}
          </Typography>
        </Stack>
      ) : null}

      {tab === 9 ? (
        onboarding ? (
          <Stack spacing={1}>
            <Typography variant="subtitle2">Overall: {onboarding.overall}</Typography>
            {onboarding.items.map((item) => (
              <Stack key={item.key} direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                <Chip
                  size="small"
                  color={item.done ? 'success' : 'default'}
                  label={item.done ? 'Done' : 'Pending'}
                />
                <Typography variant="body2">
                  {item.label}
                  {item.required ? ' (required)' : ''}
                </Typography>
              </Stack>
            ))}
          </Stack>
        ) : (
          <Typography variant="body2" color="text.secondary">
            No onboarding data.
          </Typography>
        )
      ) : null}
    </Stack>
  );
}
