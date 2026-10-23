import { useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Chip,
  CircularProgress,
  Link,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import {
  engineeringPerformanceQueryKeys,
  fetchEngineeringDataQuality,
} from '../../api/engineeringPerformance';
import type { DataQualityCheck } from '../../types/EngineeringPerformance';
import { ErrorState } from '../common/ErrorState';

const SEVERITY_COLOR: Record<DataQualityCheck['severity'], 'error' | 'warning' | 'info'> = {
  high: 'error',
  medium: 'warning',
  low: 'info',
};

function CheckRow({ check }: { check: DataQualityCheck }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <Accordion
      disableGutters
      expanded={expanded}
      onChange={(_, open) => setExpanded(open)}
      disabled={check.count === 0}
    >
      <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
        <Stack direction="row" spacing={1.5} sx={{ width: '100%', alignItems: 'center' }}>
          <Chip
            size="small"
            label={check.count}
            color={check.count === 0 ? 'success' : SEVERITY_COLOR[check.severity]}
            sx={{ minWidth: 40 }}
          />
          <Typography sx={{ flexGrow: 1 }}>{check.label}</Typography>
          <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'capitalize' }}>
            {check.severity}
          </Typography>
        </Stack>
      </AccordionSummary>
      <AccordionDetails>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {check.description}
        </Typography>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Record</TableCell>
              <TableCell>Description</TableCell>
              <TableCell>Detail</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {check.items.map((item) => (
              <TableRow key={`${item.kind}-${item.id}`}>
                <TableCell>
                  {item.kind === 'project' ? (
                    <Link component={RouterLink} to={`/projects/${item.id}`}>
                      {item.label ?? 'Project'}
                    </Link>
                  ) : (
                    item.label
                  )}
                </TableCell>
                <TableCell>{item.description ?? '—'}</TableCell>
                <TableCell>{item.detail ?? '—'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {check.count > check.items.length ? (
          <Typography variant="caption" color="text.secondary">
            Showing the first {check.items.length} of {check.count}.
          </Typography>
        ) : null}
      </AccordionDetails>
    </Accordion>
  );
}

export function EngineeringDataQualityPanel() {
  const query = useQuery({
    queryKey: engineeringPerformanceQueryKeys.dataQuality,
    queryFn: fetchEngineeringDataQuality,
  });

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack direction="row" spacing={1} sx={{ mb: 1, alignItems: 'center' }}>
        <Typography variant="h6" sx={{ flexGrow: 1 }}>
          Engineering Data Quality
        </Typography>
        {query.isFetching ? <CircularProgress size={18} /> : null}
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Records that make schedules and KPIs unreliable. Nothing is changed automatically; open a
        record to correct it.
      </Typography>
      {query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : query.data ? (
        <Box>
          {query.data.total_issues === 0 ? (
            <Alert severity="success" sx={{ mb: 1 }}>
              No data-quality issues found across {query.data.projects_checked} projects.
            </Alert>
          ) : (
            <Typography variant="body2" sx={{ mb: 1 }}>
              {query.data.total_issues} issue{query.data.total_issues === 1 ? '' : 's'} across{' '}
              {query.data.projects_checked} projects checked.
            </Typography>
          )}
          {query.data.checks.map((check) => (
            <CheckRow key={check.code} check={check} />
          ))}
        </Box>
      ) : null}
    </Paper>
  );
}
