import {
  Box,
  Button,
  Chip,
  Grid,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import AutoAwesomeOutlinedIcon from '@mui/icons-material/AutoAwesomeOutlined';
import WorkOutlineOutlinedIcon from '@mui/icons-material/WorkOutlineOutlined';
import { FinanceSection } from '../finance/FinanceCockpitPrimitives';
import { formatReviewPeriod } from './performanceReviewPeriod';

export type ReviewProjectRow = {
  id?: string;
  project_id?: string | null;
  tool_number: string;
  part_description?: string | null;
  customer_name?: string | null;
  assignment_role?: string | null;
  hours_logged?: number | string | null;
  execution_status?: string | null;
  project_stage?: string | null;
  completed_at?: string | null;
  contribution_summary?: string | null;
  achievement_notes?: string | null;
  is_auto_imported?: boolean;
  sort_order: number;
};

type PerformanceReviewProjectsPanelProps = {
  projects: ReviewProjectRow[];
  periodStart?: string | null;
  periodEnd?: string | null;
  canManage: boolean;
  importing?: boolean;
  onChange: (projects: ReviewProjectRow[]) => void;
  onImportSuggested?: () => void;
};

function cloneProjects(projects: ReviewProjectRow[]): ReviewProjectRow[] {
  return projects.map((row) => ({ ...row }));
}

export function PerformanceReviewProjectsPanel({
  projects,
  periodStart,
  periodEnd,
  canManage,
  importing = false,
  onChange,
  onImportSuggested,
}: PerformanceReviewProjectsPanelProps) {
  const totalHours = projects.reduce(
    (sum, row) => sum + (Number(row.hours_logged) || 0),
    0,
  );

  const updateRow = (index: number, patch: Partial<ReviewProjectRow>) => {
    const next = cloneProjects(projects);
    next[index] = { ...next[index], ...patch };
    onChange(next);
  };

  const removeRow = (index: number) => {
    onChange(projects.filter((_, rowIndex) => rowIndex !== index));
  };

  const addManualRow = () => {
    onChange([
      ...projects,
      {
        tool_number: '',
        sort_order: projects.length,
        is_auto_imported: false,
      },
    ]);
  };

  return (
    <FinanceSection
      title="Projects & achievements"
      subtitle="Projects completed or contributed to during the review year — auto-imported from ProTrack assignments and timesheets."
      action={
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
          <Chip
            size="small"
            icon={<WorkOutlineOutlinedIcon />}
            label={`${projects.length} projects · ${totalHours.toFixed(1)}h`}
            variant="outlined"
          />
          {canManage && onImportSuggested ? (
            <Button
              size="small"
              variant="outlined"
              startIcon={<AutoAwesomeOutlinedIcon />}
              disabled={importing}
              onClick={onImportSuggested}
            >
              Import from platform
            </Button>
          ) : null}
        </Stack>
      }
    >
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Review window: {formatReviewPeriod(periodStart, periodEnd)}. Aligns to the Excel
        field &quot;Projects done / Achievements in reviewing year&quot;.
      </Typography>

      {projects.length === 0 ? (
        <Box
          sx={{
            p: 2.5,
            borderRadius: 2,
            border: '1px dashed',
            borderColor: 'divider',
            textAlign: 'center',
          }}
        >
          <Typography color="text.secondary" sx={{ mb: 1 }}>
            No projects linked yet.
          </Typography>
          {canManage ? (
            <Stack direction="row" spacing={1} sx={{ justifyContent: 'center' }}>
              {onImportSuggested ? (
                <Button
                  size="small"
                  variant="contained"
                  startIcon={<AutoAwesomeOutlinedIcon />}
                  disabled={importing}
                  onClick={onImportSuggested}
                >
                  Import assigned projects
                </Button>
              ) : null}
              <Button size="small" variant="outlined" onClick={addManualRow}>
                Add manually
              </Button>
            </Stack>
          ) : null}
        </Box>
      ) : (
        <Stack spacing={2}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Tool / Project</TableCell>
                <TableCell>Customer</TableCell>
                <TableCell>Role</TableCell>
                <TableCell align="right">Hours</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {projects.map((row, index) => (
                <TableRow key={row.id ?? `${row.tool_number}-${index}`}>
                  <TableCell>
                    <Typography sx={{ fontWeight: 700 }}>{row.tool_number || '—'}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {row.part_description || 'No description'}
                    </Typography>
                    {row.is_auto_imported ? (
                      <Chip size="small" label="Auto" sx={{ mt: 0.5 }} variant="outlined" />
                    ) : null}
                  </TableCell>
                  <TableCell>{row.customer_name || '—'}</TableCell>
                  <TableCell>{row.assignment_role || '—'}</TableCell>
                  <TableCell align="right">
                    {row.hours_logged === null || row.hours_logged === undefined
                      ? '—'
                      : Number(row.hours_logged).toFixed(1)}
                  </TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={row.execution_status || 'unknown'}
                      variant="outlined"
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {projects.map((row, index) => (
            <Box
              key={`detail-${row.id ?? `${row.tool_number}-${index}`}`}
              sx={{
                p: 1.5,
                borderRadius: 2,
                border: '1px solid',
                borderColor: 'divider',
              }}
            >
              <Stack
                direction="row"
                sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 1 }}
              >
                <Typography sx={{ fontWeight: 700 }}>
                  {row.tool_number || `Project ${index + 1}`}
                </Typography>
                {canManage ? (
                  <Button size="small" color="error" onClick={() => removeRow(index)}>
                    Remove
                  </Button>
                ) : null}
              </Stack>
              <Grid container spacing={1.5}>
                {canManage ? (
                  <>
                    <Grid size={{ xs: 12, sm: 4 }}>
                      <TextField
                        fullWidth
                        size="small"
                        label="Tool number"
                        value={row.tool_number}
                        onChange={(e) => updateRow(index, { tool_number: e.target.value })}
                      />
                    </Grid>
                    <Grid size={{ xs: 12, sm: 8 }}>
                      <TextField
                        fullWidth
                        size="small"
                        label="Description"
                        value={row.part_description ?? ''}
                        onChange={(e) => updateRow(index, { part_description: e.target.value })}
                      />
                    </Grid>
                  </>
                ) : null}
                <Grid size={{ xs: 12, md: 6 }}>
                  <TextField
                    fullWidth
                    size="small"
                    multiline
                    minRows={2}
                    label="Contribution summary"
                    value={row.contribution_summary ?? ''}
                    onChange={(e) => updateRow(index, { contribution_summary: e.target.value })}
                    disabled={!canManage}
                  />
                </Grid>
                <Grid size={{ xs: 12, md: 6 }}>
                  <TextField
                    fullWidth
                    size="small"
                    multiline
                    minRows={2}
                    label="Achievement notes (employee)"
                    value={row.achievement_notes ?? ''}
                    onChange={(e) => updateRow(index, { achievement_notes: e.target.value })}
                  />
                </Grid>
              </Grid>
            </Box>
          ))}

          {canManage ? (
            <Button size="small" variant="outlined" onClick={addManualRow}>
              Add project manually
            </Button>
          ) : null}
        </Stack>
      )}
    </FinanceSection>
  );
}
