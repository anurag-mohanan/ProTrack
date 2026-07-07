import { Box, LinearProgress, Typography } from '@mui/material';
import type { ProjectMilestoneSummary } from '../../../types/Milestone';
import { designTokens } from '../../../theme/designTokens';
import { formatNumber } from '../../../utils/format';

interface ProjectMilestoneSummaryCardProps {
  summary: ProjectMilestoneSummary;
}

export function ProjectMilestoneSummaryCard({ summary }: ProjectMilestoneSummaryCardProps) {
  const inProgress =
    summary.in_progress_count ??
    Math.max(0, summary.milestone_count - summary.completed_count - (summary.not_started_count ?? 0));
  const notStarted = summary.not_started_count ?? 0;
  const progress = summary.overall_progress_percent ?? 0;

  return (
    <Box
      sx={{
        mb: 1.25,
        px: 1.5,
        py: 1,
        borderRadius: 2,
        border: 1,
        borderColor: 'divider',
        bgcolor: designTokens.semantic.card,
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: 2,
      }}
    >
      <Box>
        <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 700 }}>
          Milestones
        </Typography>
        <Typography sx={{ fontSize: '0.85rem', fontWeight: 700 }}>
          {summary.milestone_count} Total · {summary.completed_count} Completed · {inProgress} In
          Progress · {notStarted} Not Started
        </Typography>
      </Box>

      <Box sx={{ flex: 1, minWidth: 160, maxWidth: 280 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.25 }}>
          <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 700 }}>
            Progress
          </Typography>
          <Typography variant="caption" sx={{ fontWeight: 800 }}>
            {formatNumber(progress, 0)}%
          </Typography>
        </Box>
        <LinearProgress
          variant="determinate"
          value={progress}
          sx={{
            height: 5,
            borderRadius: designTokens.radius.pill,
            bgcolor: designTokens.semantic.neutralSoft,
            '& .MuiLinearProgress-bar': {
              borderRadius: designTokens.radius.pill,
              bgcolor: designTokens.semantic.primary,
            },
          }}
        />
      </Box>

      <Typography sx={{ fontSize: '0.85rem', fontWeight: 700, whiteSpace: 'nowrap' }}>
        {formatNumber(summary.remaining_hours, 0)} hrs Remaining
      </Typography>
    </Box>
  );
}
