import { Box, Chip, Stack, Typography } from '@mui/material';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import type { NavigateFunction } from 'react-router-dom';
import type { AiInsight } from '../../types/Ai';
import { DashboardPanel } from '../ui/design-system/DashboardPanel';

interface AiOperationsPanelProps {
  insights: AiInsight[];
  navigate: NavigateFunction;
  compact?: boolean;
  loading?: boolean;
}

const severityColor = {
  info: 'info',
  warning: 'warning',
  error: 'error',
} as const;

export function AiOperationsPanel({
  insights,
  navigate,
  compact = false,
}: AiOperationsPanelProps) {
  return (
    <DashboardPanel
      title="AI Operations Assistant"
      subtitle="Dynamic recommendations from live engineering data"
      height={compact ? '100%' : undefined}
    >
      <Stack spacing={1.25}>
        {insights.length ? (
          insights.map((insight) => (
            <Box
              key={insight.id}
              onClick={() => insight.href && navigate(insight.href)}
              sx={{
                p: 1.25,
                borderRadius: 2,
                border: '1px solid',
                borderColor: 'divider',
                cursor: insight.href ? 'pointer' : 'default',
                transition: 'background-color 0.2s ease, box-shadow 0.2s ease',
                '&:hover': insight.href
                  ? { bgcolor: 'action.hover', boxShadow: 1 }
                  : undefined,
              }}
            >
              <Stack direction="row" spacing={1} sx={{ alignItems: 'flex-start' }}>
                <AutoAwesomeRoundedIcon sx={{ fontSize: 16, mt: 0.2, color: 'primary.main' }} />
                <Box sx={{ minWidth: 0, flex: 1 }}>
                  <Stack
                    direction="row"
                    spacing={0.75}
                    sx={{ alignItems: 'center', mb: 0.25, flexWrap: 'wrap' }}
                    useFlexGap
                  >
                    <Typography variant="body2" sx={{ fontWeight: 700 }}>
                      {insight.title}
                    </Typography>
                    <Chip
                      size="small"
                      label={insight.category}
                      color={severityColor[insight.severity as keyof typeof severityColor] ?? 'default'}
                      variant="outlined"
                      sx={{ height: 20, fontSize: 10 }}
                    />
                    <Chip
                      size="small"
                      label={`${Math.round(insight.confidence)}%`}
                      variant="outlined"
                      sx={{ height: 20, fontSize: 10 }}
                    />
                  </Stack>
                  {insight.detail ? (
                    <Typography variant="caption" color="text.secondary">
                      {insight.detail}
                    </Typography>
                  ) : null}
                </Box>
              </Stack>
            </Box>
          ))
        ) : (
          <Typography variant="body2" color="text.secondary">
            Analyzing project data — insights will appear as patterns emerge.
          </Typography>
        )}
      </Stack>
    </DashboardPanel>
  );
}
