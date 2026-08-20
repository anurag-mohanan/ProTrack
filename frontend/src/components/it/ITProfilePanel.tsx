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
import { formatCellValue } from '../../utils/format';

interface ITProfilePanelProps {
  profile: ITProfile | undefined;
  loading?: boolean;
  emptyMessage?: string;
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
  const isEmpty = assets.length === 0 && accounts.length === 0 && ips.length === 0;

  if (isEmpty) {
    return (
      <Typography variant="body2" color="text.secondary">
        {emptyMessage}
      </Typography>
    );
  }

  return (
    <Stack spacing={2.5}>
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
