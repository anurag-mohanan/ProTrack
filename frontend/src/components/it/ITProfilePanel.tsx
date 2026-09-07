import {
  Box,
  Chip,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { LoadingState } from '../common/LoadingState';
import type { ITProfile } from '../../types/itOperations';
import { formatCellValue, formatDate } from '../../utils/format';

interface ITProfilePanelProps {
  profile: ITProfile | undefined;
  loading?: boolean;
  emptyMessage?: string;
}

function shiftLabel(shift: ITProfile['shift']): string | null {
  if (!shift) return null;
  return (
    shift.display ||
    shift.shift_display ||
    shift.name ||
    shift.shift_name ||
    shift.code ||
    shift.shift_code ||
    null
  );
}

export function ITProfilePanel({
  profile,
  loading = false,
  emptyMessage = 'No IT assets, accounts, or IP allocations on record.',
}: ITProfilePanelProps) {
  if (loading) {
    return <LoadingState message="Loading IT profile…" />;
  }

  const assets = profile?.assets ?? [];
  const accounts = profile?.accounts ?? [];
  const ips = profile?.ips ?? [];
  const software = profile?.software ?? [];
  const missing = profile?.missing_software ?? [];
  const computer = profile?.computer ?? null;
  const shift = profile?.shift ?? null;
  const isEmpty =
    assets.length === 0 &&
    accounts.length === 0 &&
    ips.length === 0 &&
    software.length === 0 &&
    !computer &&
    !shift;

  if (isEmpty) {
    return (
      <Typography variant="body2" color="text.secondary">
        {emptyMessage}
      </Typography>
    );
  }

  return (
    <Stack spacing={2.5}>
      <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', alignItems: 'center' }}>
        <Chip
          size="small"
          color={profile?.is_compliant === false ? 'warning' : 'success'}
          label={profile?.is_compliant === false ? 'IT gaps' : 'IT compliant'}
          variant="outlined"
        />
        {shiftLabel(shift) ? (
          <Chip size="small" label={`Shift: ${shiftLabel(shift)}`} variant="outlined" />
        ) : null}
        {typeof profile?.required_software_count === 'number' ? (
          <Typography variant="caption" color="text.secondary">
            Software {software.length}/{profile.required_software_count} required
          </Typography>
        ) : null}
      </Stack>

      {computer ? (
        <Box>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Primary computer
          </Typography>
          <Table size="small">
            <TableBody>
              <TableRow>
                <TableCell width="30%">Name</TableCell>
                <TableCell>{formatCellValue(computer.computer_name)}</TableCell>
              </TableRow>
              <TableRow>
                <TableCell>Asset #</TableCell>
                <TableCell>{formatCellValue(computer.asset_number)}</TableCell>
              </TableRow>
              <TableRow>
                <TableCell>Status</TableCell>
                <TableCell>
                  {computer.asset_status ? (
                    <Chip size="small" label={computer.asset_status} />
                  ) : (
                    '—'
                  )}
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell>Assigned</TableCell>
                <TableCell>
                  {computer.assigned_date ? formatDate(computer.assigned_date) : '—'}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </Box>
      ) : (
        <Typography variant="body2" color="text.secondary">
          No primary computer assigned.
        </Typography>
      )}

      {assets.length > 0 ? (
        <Box>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Assigned assets
          </Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Asset #</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Make / Model</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Location</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {assets.map((asset) => (
                <TableRow key={asset.id}>
                  <TableCell>{asset.asset_number}</TableCell>
                  <TableCell>
                    {formatCellValue(asset.asset_type_name ?? asset.asset_type_code)}
                  </TableCell>
                  <TableCell>
                    {[asset.make, asset.model].filter(Boolean).join(' ') || '—'}
                  </TableCell>
                  <TableCell>
                    <Chip size="small" label={asset.status} />
                  </TableCell>
                  <TableCell>{formatCellValue(asset.location)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      ) : null}

      {software.length > 0 || missing.length > 0 ? (
        <Box>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Software & licenses
          </Typography>
          {software.length > 0 ? (
            <Table size="small" sx={{ mb: missing.length ? 1.5 : 0 }}>
              <TableHead>
                <TableRow>
                  <TableCell>Software</TableCell>
                  <TableCell>License type</TableCell>
                  <TableCell>Assigned</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {software.map((row) => (
                  <TableRow key={row.assignment_id}>
                    <TableCell>{formatCellValue(row.software_name)}</TableCell>
                    <TableCell>{formatCellValue(row.license_type)}</TableCell>
                    <TableCell>
                      {row.assigned_date ? formatDate(row.assigned_date) : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : null}
          {missing.length > 0 ? (
            <Stack direction="row" spacing={0.75} sx={{ flexWrap: 'wrap' }}>
              {missing.map((name) => (
                <Chip key={name} size="small" color="warning" label={`Missing: ${name}`} />
              ))}
            </Stack>
          ) : null}
        </Box>
      ) : null}

      {accounts.length > 0 ? (
        <Box>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            IT accounts
          </Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Type</TableCell>
                <TableCell>Username</TableCell>
                <TableCell>Display name</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {accounts.map((account) => (
                <TableRow key={account.id}>
                  <TableCell>{account.account_type}</TableCell>
                  <TableCell>{formatCellValue(account.username)}</TableCell>
                  <TableCell>{formatCellValue(account.display_name)}</TableCell>
                  <TableCell>
                    <Chip size="small" label={account.status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      ) : null}

      {ips.length > 0 ? (
        <Box>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Allocated IPs
          </Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Address</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Allocation</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {ips.map((ip) => (
                <TableRow key={ip.id}>
                  <TableCell>{ip.address}</TableCell>
                  <TableCell>
                    <Chip size="small" label={ip.status} />
                  </TableCell>
                  <TableCell>{formatCellValue(ip.allocation_type)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      ) : null}
    </Stack>
  );
}
