import {
  LinearProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import type { DashboardProjectStageRow } from '../../types';
import { PROJECT_STAGE_LABELS } from '../../types/common';
import { formatNumber } from '../../utils/format';

interface ProjectsByStageWidgetProps {
  rows: DashboardProjectStageRow[];
}

export function ProjectsByStageWidget({ rows }: ProjectsByStageWidgetProps) {
  const total = rows.reduce((sum, row) => sum + row.project_count, 0);

  if (!rows.length) {
    return (
      <Paper
        variant="outlined"
        sx={{
          borderRadius: 2.5,
          p: 3,
          boxShadow: (theme) => theme.palette.prosohm.shadowCard,
        }}
      >
        <Typography variant="body2" color="text.secondary">
          No active projects by stage.
        </Typography>
      </Paper>
    );
  }

  return (
    <Paper
      variant="outlined"
      sx={{
        borderRadius: 2.5,
        overflow: 'hidden',
        boxShadow: (theme) => theme.palette.prosohm.shadowCard,
      }}
    >
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell sx={{ fontWeight: 700, fontSize: '0.75rem', textTransform: 'uppercase' }}>
                Stage
              </TableCell>
              <TableCell align="right" sx={{ fontWeight: 700, fontSize: '0.75rem', textTransform: 'uppercase' }}>
                Projects
              </TableCell>
              <TableCell sx={{ width: '40%' }} />
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((row) => {
              const percent = total > 0 ? Math.round((row.project_count / total) * 100) : 0;
              return (
                <TableRow key={row.project_stage} hover>
                  <TableCell sx={{ fontWeight: 600 }}>
                    {PROJECT_STAGE_LABELS[row.project_stage]}
                  </TableCell>
                  <TableCell align="right">{formatNumber(row.project_count, 0)}</TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                      <LinearProgress
                        variant="determinate"
                        value={percent}
                        sx={{ flex: 1, height: 6, borderRadius: 999 }}
                      />
                      <Typography variant="caption" color="text.secondary" sx={{ minWidth: 32 }}>
                        {percent}%
                      </Typography>
                    </Stack>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
}
