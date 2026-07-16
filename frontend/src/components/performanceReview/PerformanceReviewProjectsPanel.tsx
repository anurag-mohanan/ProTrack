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

export type ReviewProjectRow = {
  id?: string;
  project_id?: string | null;
  tool_number: string;
  part_description?: string | null;
  customer_name?: string | null;
  assignment_role?: string | null;
  hours_logged?: number | string | null;
  execution_status?: string | null;
  ownership_type?: string | null;
  tasks_summary?: string | null;
  contribution_summary?: string | null;
  achievement_notes?: string | null;
  is_auto_imported?: boolean;
  sort_order: number;
};

type PerformanceReviewProjectsPanelProps = {
  projects: ReviewProjectRow[];
  periodStart?: string | null;
  periodEnd?: string | null;
};

export function PerformanceReviewProjectsPanel({
  projects,
  periodStart,
  periodEnd,
}: PerformanceReviewProjectsPanelProps) {
  const owned = projects.filter((row) => (row.ownership_type || 'owned') !== 'supported');
  const supported = projects.filter((row) => row.ownership_type === 'supported');

  return (
    <Box className="review-projects-block" sx={{ mt: 1.5 }}>
      <Typography
        variant="subtitle2"
        sx={{
          fontWeight: 800,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          mb: 0.75,
          fontSize: 11,
        }}
      >
        Projects done / Achievements
        {periodStart && periodEnd ? (
          <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 1 }}>
            ({periodStart} → {periodEnd})
          </Typography>
        ) : null}
      </Typography>

      <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.25}>
        <Box
          sx={{
            flex: 1.4,
            maxHeight: 180,
            overflow: 'auto',
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 1,
            bgcolor: 'background.paper',
          }}
        >
          <Box
            sx={{
              px: 1,
              py: 0.5,
              bgcolor: 'grey.900',
              color: 'common.white',
              fontSize: 11,
              fontWeight: 700,
            }}
          >
            Owned projects
          </Box>
          {owned.length === 0 ? (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', p: 1 }}>
              No owned projects in this review year.
            </Typography>
          ) : (
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontSize: 10, py: 0.5 }}>Project</TableCell>
                  <TableCell sx={{ fontSize: 10, py: 0.5 }}>Tasks done</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {owned.map((row, index) => (
                  <TableRow key={row.id ?? `owned-${row.tool_number}-${index}`}>
                    <TableCell sx={{ py: 0.4, fontSize: 11, verticalAlign: 'top' }}>
                      <Typography sx={{ fontWeight: 700, fontSize: 11, lineHeight: 1.2 }}>
                        {row.tool_number}
                      </Typography>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', lineHeight: 1.2 }}>
                        {row.part_description || row.customer_name || row.assignment_role || '—'}
                      </Typography>
                    </TableCell>
                    <TableCell sx={{ py: 0.4, fontSize: 10, color: 'text.secondary' }}>
                      {row.tasks_summary || '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Box>

        <Box
          sx={{
            flex: 0.8,
            maxHeight: 180,
            overflow: 'auto',
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 1,
            bgcolor: 'background.paper',
          }}
        >
          <Box
            sx={{
              px: 1,
              py: 0.5,
              bgcolor: 'grey.800',
              color: 'common.white',
              fontSize: 11,
              fontWeight: 700,
            }}
          >
            Supported projects
          </Box>
          {supported.length === 0 ? (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', p: 1 }}>
              None
            </Typography>
          ) : (
            <Stack spacing={0.5} sx={{ p: 1 }}>
              {supported.map((row, index) => (
                <Stack
                  key={row.id ?? `supported-${row.tool_number}-${index}`}
                  direction="row"
                  sx={{ justifyContent: 'space-between', alignItems: 'center' }}
                >
                  <Typography sx={{ fontWeight: 700, fontSize: 11 }}>{row.tool_number}</Typography>
                  <Chip size="small" label="Supported" sx={{ height: 18, fontSize: 10 }} />
                </Stack>
              ))}
            </Stack>
          )}
        </Box>
      </Stack>
    </Box>
  );
}
