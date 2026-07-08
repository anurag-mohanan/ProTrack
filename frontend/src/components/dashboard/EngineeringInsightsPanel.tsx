import { Box, Chip, Stack, Typography } from '@mui/material';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import type { NavigateFunction } from 'react-router-dom';
import type { EngineeringInsight } from '../../types';
import { DashboardPanel } from '../ui/design-system/DashboardPanel';

interface EngineeringInsightsPanelProps {
  insights: EngineeringInsight[];
  navigate: NavigateFunction;
  compact?: boolean;
}

const severityColor = {
  info: 'info',
  warning: 'warning',
  error: 'error',
} as const;

export function EngineeringInsightsPanel({
  insights,
  navigate,
  compact = false,
}: EngineeringInsightsPanelProps) {
  return (
    <DashboardPanel
      title="AI Engineering Assistant"
      subtitle="Intelligent recommendations from live project data"
      height={compact ? '100%' : undefined}
    >
      <Stack spacing={1.25}>
        {insights.length ? (
          insights.map((insight, index) => (
            <Box
              key={`${insight.title}-${index}`}
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
                  <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center', mb: 0.25 }}>
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
            Insights will appear as projects, milestones, and workload patterns develop.
          </Typography>
        )}
      </Stack>
    </DashboardPanel>
  );
}
