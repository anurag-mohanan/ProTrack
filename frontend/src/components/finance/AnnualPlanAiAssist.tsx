import {
  Box,
  Button,
  Chip,
  LinearProgress,
  Stack,
  Typography,
} from '@mui/material';
import AutoAwesomeOutlinedIcon from '@mui/icons-material/AutoAwesomeOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import { designTokens } from '../../theme/designTokens';
import { chartTheme } from '../../theme/chartTheme';
import { FinanceSection } from './FinanceCockpitPrimitives';

type Insight = {
  id: string;
  severity: string;
  title: string;
  detail: string;
  action_code?: string | null;
  action_label?: string | null;
};

type InsightsPayload = {
  confidence_percent: number;
  fill_ratio_percent: number;
  months_elapsed: number;
  disclaimer: string;
  headline: string;
  insights: Insight[];
};

const severityColor: Record<string, string> = {
  high: designTokens.health.red.main,
  medium: designTokens.health.yellow.main,
  low: designTokens.semantic.primary,
  info: designTokens.semantic.neutral,
};

export function AnnualPlanAiAssist({
  planId,
  onApplied,
}: {
  planId: string;
  onApplied: () => void;
}) {
  const { showError, showSuccess } = useToast();
  const queryClient = useQueryClient();

  const insightsQuery = useQuery({
    queryKey: ['finance-plan-ai', planId],
    enabled: Boolean(planId),
    queryFn: async () =>
      (await apiClient.get<InsightsPayload>(`/finance/plans/${planId}/ai-insights`)).data,
  });

  const applyMutation = useMutation({
    mutationFn: async (actionCode: string) =>
      (await apiClient.post(`/finance/plans/${planId}/ai-apply`, { action_code: actionCode })).data,
    onSuccess: () => {
      showSuccess('AI Assist applied to the plan');
      void queryClient.invalidateQueries({ queryKey: ['finance-plan-ai', planId] });
      onApplied();
    },
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      showError(error.response?.data?.detail ?? 'Could not apply AI action');
    },
  });

  const data = insightsQuery.data;

  return (
    <FinanceSection
      title="AI Assist"
      subtitle="Data-driven recommendations (no external LLM)"
      action={
        <Chip
          size="small"
          icon={<AutoAwesomeOutlinedIcon />}
          label={data ? `${data.confidence_percent}% conf.` : '…'}
          sx={{ fontWeight: 700 }}
        />
      }
    >
      {insightsQuery.isLoading || !data ? (
        <Typography color="text.secondary">Analyzing plan…</Typography>
      ) : (
        <Stack spacing={1.5}>
          <Typography variant="body2" sx={{ fontWeight: 700, color: chartTheme.ink.primary }}>
            {data.headline}
          </Typography>
          <Box>
            <Stack direction="row" sx={{ justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="caption" color="text.secondary">
                Plan fill {data.fill_ratio_percent}%
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {data.months_elapsed} mo elapsed
              </Typography>
            </Stack>
            <LinearProgress
              variant="determinate"
              value={Math.min(100, data.fill_ratio_percent)}
              sx={{
                height: 6,
                borderRadius: 99,
                bgcolor: chartTheme.surface.track,
                '& .MuiLinearProgress-bar': {
                  bgcolor: designTokens.semantic.primary,
                  borderRadius: 99,
                },
              }}
            />
          </Box>
          <Typography variant="caption" color="text.secondary">
            {data.disclaimer}
          </Typography>
          {data.insights.map((insight) => (
            <Box
              key={insight.id}
              sx={{
                p: 1.25,
                borderRadius: 2,
                border: `1px solid ${chartTheme.surface.hairline}`,
                bgcolor: chartTheme.surface.muted,
              }}
            >
              <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 0.5 }}>
                <Chip
                  size="small"
                  label={insight.severity}
                  sx={{
                    height: 22,
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    bgcolor: `${severityColor[insight.severity] ?? designTokens.semantic.neutral}22`,
                    color: severityColor[insight.severity] ?? designTokens.semantic.neutral,
                  }}
                />
                <Typography sx={{ fontWeight: 700, fontSize: '0.9rem' }}>{insight.title}</Typography>
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ mb: insight.action_code ? 1 : 0 }}>
                {insight.detail}
              </Typography>
              {insight.action_code && insight.action_label ? (
                <Button
                  size="small"
                  variant="contained"
                  disabled={applyMutation.isPending}
                  onClick={() => applyMutation.mutate(insight.action_code as string)}
                >
                  {insight.action_label}
                </Button>
              ) : null}
            </Box>
          ))}
        </Stack>
      )}
    </FinanceSection>
  );
}
