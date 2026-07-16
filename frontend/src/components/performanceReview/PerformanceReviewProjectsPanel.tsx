import {
  Box,
  Chip,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
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
  complexity?: string | null;
  contribution_summary?: string | null;
  achievement_notes?: string | null;
  is_auto_imported?: boolean;
  sort_order: number;
};

const COMPLEXITY_OPTIONS = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'expert', label: 'Expert' },
];

function complexityTone(value?: string | null): 'default' | 'success' | 'warning' | 'error' | 'info' {
  switch (value) {
    case 'low':
      return 'success';
    case 'medium':
      return 'info';
    case 'high':
      return 'warning';
    case 'expert':
      return 'error';
    default:
      return 'default';
  }
}

function complexityLabel(value?: string | null): string {
  const match = COMPLEXITY_OPTIONS.find((row) => row.value === value);
  return match?.label ?? (value ? value : '—');
}

type PerformanceReviewProjectsPanelProps = {
  projects: ReviewProjectRow[];
  periodStart?: string | null;
  periodEnd?: string | null;
  canManage?: boolean;
  onChange?: (next: ReviewProjectRow[]) => void;
};

export function PerformanceReviewProjectsPanel({
  projects,
  periodStart,
  periodEnd,
  canManage = false,
  onChange,
}: PerformanceReviewProjectsPanelProps) {
  const owned = projects.filter((row) => (row.ownership_type || 'owned') !== 'supported');
  const supported = projects.filter((row) => row.ownership_type === 'supported');

  const updateOwnedComplexity = (indexInOwned: number, complexity: string) => {
    if (!onChange) return;
    let ownedCursor = -1;
    const next = projects.map((row) => {
      if ((row.ownership_type || 'owned') === 'supported') return row;
      ownedCursor += 1;
      if (ownedCursor !== indexInOwned) return row;
      return { ...row, complexity };
    });
    onChange(next);
  };

  return (
    <Box className="review-projects-block" sx={{ mt: 1 }}>
      <Typography
        variant="subtitle2"
        sx={{
          fontWeight: 800,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          mb: 0.5,
          fontSize: 11,
        }}
      >
        Projects completed
        {periodStart && periodEnd ? (
          <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 1 }}>
            ({periodStart} → {periodEnd})
          </Typography>
        ) : (
          <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 1 }}>
            (review year ending June)
          </Typography>
        )}
      </Typography>

      <Stack direction={{ xs: 'column', md: 'row' }} spacing={1}>
        <Box
          sx={{
            flex: 1.5,
            maxHeight: 140,
            overflow: 'auto',
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 1,
            bgcolor: 'background.paper',
          }}
        >
          <Box
            sx={{
              px: 0.75,
              py: 0.35,
              bgcolor: 'grey.900',
              color: 'common.white',
              fontSize: 10,
              fontWeight: 700,
            }}
          >
            Owned · complexity & tasks
          </Box>
          {owned.length === 0 ? (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', p: 0.75 }}>
              No owned projects completed in this review year.
            </Typography>
          ) : (
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontSize: 9, py: 0.25, px: 0.75 }}>Project</TableCell>
                  <TableCell sx={{ fontSize: 9, py: 0.25, px: 0.5, width: 88 }}>Complexity</TableCell>
                  <TableCell sx={{ fontSize: 9, py: 0.25, px: 0.75 }}>Tasks</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {owned.map((row, index) => (
                  <TableRow key={row.id ?? `owned-${row.tool_number}-${index}`}>
                    <TableCell sx={{ py: 0.25, px: 0.75, fontSize: 10, verticalAlign: 'top' }}>
                      <Typography sx={{ fontWeight: 700, fontSize: 10, lineHeight: 1.15 }}>
                        {row.tool_number}
                      </Typography>
                    </TableCell>
                    <TableCell sx={{ py: 0.2, px: 0.5, verticalAlign: 'top' }}>
                      {canManage && onChange ? (
                        <TextField
                          select
                          size="small"
                          value={row.complexity || 'medium'}
                          onChange={(e) => updateOwnedComplexity(index, e.target.value)}
                          sx={{
                            minWidth: 78,
                            '& .MuiInputBase-input': { fontSize: 10, py: 0.35, px: 0.75 },
                          }}
                        >
                          {COMPLEXITY_OPTIONS.map((opt) => (
                            <MenuItem key={opt.value} value={opt.value} sx={{ fontSize: 11 }}>
                              {opt.label}
                            </MenuItem>
                          ))}
                        </TextField>
                      ) : (
                        <Chip
                          size="small"
                          label={complexityLabel(row.complexity)}
                          color={complexityTone(row.complexity)}
                          sx={{ height: 18, fontSize: 9 }}
                        />
                      )}
                    </TableCell>
                    <TableCell sx={{ py: 0.25, px: 0.75, fontSize: 9, color: 'text.secondary' }}>
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
            flex: 0.7,
            maxHeight: 140,
            overflow: 'auto',
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 1,
            bgcolor: 'background.paper',
          }}
        >
          <Box
            sx={{
              px: 0.75,
              py: 0.35,
              bgcolor: 'grey.800',
              color: 'common.white',
              fontSize: 10,
              fontWeight: 700,
            }}
          >
            Supported
          </Box>
          {supported.length === 0 ? (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', p: 0.75 }}>
              None
            </Typography>
          ) : (
            <Stack spacing={0.35} sx={{ p: 0.75 }}>
              {supported.map((row, index) => (
                <Stack
                  key={row.id ?? `supported-${row.tool_number}-${index}`}
                  direction="row"
                  sx={{ justifyContent: 'space-between', alignItems: 'center', gap: 0.5 }}
                >
                  <Typography sx={{ fontWeight: 700, fontSize: 10 }}>{row.tool_number}</Typography>
                  <Chip size="small" label="Supported" sx={{ height: 16, fontSize: 9 }} />
                </Stack>
              ))}
            </Stack>
          )}
        </Box>
      </Stack>
    </Box>
  );
}
