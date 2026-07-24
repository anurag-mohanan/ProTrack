import {
  Chip,
  Link,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { Link as RouterLink } from 'react-router-dom';
import { hrProcessAuditApi, type ProcessAuditItem } from '../api/hrProcessAudit';
import { PageHeader } from '../components/common/PageHeader';
import { LoadingState } from '../components/common/LoadingState';

const FLAG_LABEL: Record<string, string> = {
  incomplete_onboarding: 'Incomplete onboarding',
  incomplete_training: 'Incomplete training',
  missing_exit: 'Missing exit',
  orphan_placement: 'Orphan placement',
  exit_done_still_active: 'Exit done, still active',
};

function severityColor(severity: ProcessAuditItem['severity']) {
  if (severity === 'high') return 'error';
  if (severity === 'medium') return 'warning';
  return 'default';
}

export function HrProcessAuditPage() {
  const query = useQuery({
    queryKey: ['hr-process-audit'],
    queryFn: () => hrProcessAuditApi.get(14),
  });

  if (query.isLoading) return <LoadingState message="Loading process audit…" />;
  const data = query.data;
  const items = data?.items ?? [];

  return (
    <Stack spacing={2}>
      <PageHeader subtitle="Incomplete onboarding, missing exit interviews, and placement gaps." />
      <Typography variant="h5" sx={{ fontWeight: 600 }}>
        Process Audit
      </Typography>
      <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
        <Chip label={`Total ${data?.total ?? 0}`} size="small" />
        {Object.entries(data?.counts ?? {}).map(([flag, count]) => (
          <Chip
            key={flag}
            label={`${FLAG_LABEL[flag] ?? flag}: ${count}`}
            size="small"
            variant="outlined"
          />
        ))}
        <Typography variant="caption" color="text.secondary" sx={{ alignSelf: 'center' }}>
          As of {data?.as_of ?? '—'} · SLA {data?.sla_days ?? 14} days
        </Typography>
      </Stack>

      {items.length === 0 ? (
        <Typography color="text.secondary">No process gaps flagged.</Typography>
      ) : (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Flag</TableCell>
              <TableCell>Person</TableCell>
              <TableCell>Detail</TableCell>
              <TableCell>Open</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {items.map((row, index) => (
              <TableRow key={`${row.flag}-${row.subject_user_id ?? row.checklist_id ?? index}`}>
                <TableCell>
                  <Chip
                    size="small"
                    color={severityColor(row.severity)}
                    label={FLAG_LABEL[row.flag] ?? row.title}
                  />
                </TableCell>
                <TableCell>{row.subject_name}</TableCell>
                <TableCell>
                  <Typography variant="body2">{row.detail}</Typography>
                </TableCell>
                <TableCell>
                  <Link component={RouterLink} to={row.deep_link.split('?')[0]}>
                    Open
                  </Link>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Stack>
  );
}
