import { Box, Grid, Typography } from '@mui/material';
import type { DashboardProjectStageRow } from '../../types';
import { PROJECT_STAGE_LABELS, type ProjectStage } from '../../types/common';
import { designTokens } from '../../theme/designTokens';
import { formatNumber } from '../../utils/format';

const STAGE_COLORS: Record<ProjectStage, { main: string; soft: string }> = {
  preliminary: designTokens.stage.preliminary,
  intermediate: designTokens.stage.intermediate,
  final: designTokens.stage.final,
};

interface ProjectStageCardsProps {
  rows: DashboardProjectStageRow[];
}

export function ProjectStageCards({ rows }: ProjectStageCardsProps) {
  if (!rows.length) {
    return (
      <Typography variant="body2" color="text.secondary">
        No active projects by stage.
      </Typography>
    );
  }

  return (
    <Grid container spacing={2}>
      {rows.map((row) => {
        const colors = STAGE_COLORS[row.project_stage];
        return (
          <Grid key={row.project_stage} size={{ xs: 6, sm: 4, md: 3 }}>
            <Box
              sx={{
                p: 2,
                borderRadius: `${designTokens.radius.lg}px`,
                bgcolor: colors.soft,
                border: '1px solid',
                borderColor: 'divider',
                transition: `transform ${designTokens.motion.fast}`,
                '&:hover': { transform: 'translateY(-2px)' },
              }}
            >
              <Typography variant="caption" sx={{ fontWeight: 700, color: colors.main }}>
                {PROJECT_STAGE_LABELS[row.project_stage]}
              </Typography>
              <Typography sx={{ fontSize: 32, fontWeight: 800, lineHeight: 1.1, mt: 0.5 }}>
                {formatNumber(row.project_count, 0)}
              </Typography>
            </Box>
          </Grid>
        );
      })}
    </Grid>
  );
}
