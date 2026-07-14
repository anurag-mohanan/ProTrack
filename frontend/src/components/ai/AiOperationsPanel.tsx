import { useMemo, useState } from 'react';
import { Box, Button, IconButton, Stack, Typography } from '@mui/material';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import RefreshRoundedIcon from '@mui/icons-material/RefreshRounded';
import type { NavigateFunction } from 'react-router-dom';
import type { AiInsight } from '../../types/Ai';
import { designTokens } from '../../theme/designTokens';

interface AiOperationsPanelProps {
  insights: AiInsight[];
  navigate: NavigateFunction;
  loading?: boolean;
  onRefresh?: () => void;
}

const severityIcon: Record<string, string> = {
  error: '🔴',
  warning: '🟡',
  info: '🔵',
  success: '🟢',
};

const severityOrder: Record<string, number> = {
  error: 0,
  warning: 1,
  info: 2,
  success: 3,
};

export function AiOperationsPanel({
  insights,
  navigate,
  loading = false,
  onRefresh,
}: AiOperationsPanelProps) {
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [expanded, setExpanded] = useState(false);

  const visible = useMemo(() => {
    const sorted = [...insights].sort(
      (a, b) => (severityOrder[a.severity] ?? 9) - (severityOrder[b.severity] ?? 9),
    );
    const filtered = sorted.filter((item) => !dismissed.has(item.id));
    return expanded ? filtered : filtered.slice(0, 5);
  }, [insights, dismissed, expanded]);

  return (
    <Box
      sx={{
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: `${designTokens.radius.lg}px`,
        bgcolor: designTokens.semantic.card,
        boxShadow: designTokens.elevation.card,
        p: 2,
        height: '100%',
      }}
    >
      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', mb: 1.25 }}>
        <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center' }}>
          <AutoAwesomeRoundedIcon sx={{ fontSize: 18, color: 'primary.main' }} />
          <Typography variant="subtitle2" sx={{ fontWeight: 800 }}>
            AI Assistant
          </Typography>
        </Stack>
        <IconButton size="small" onClick={onRefresh} disabled={loading} aria-label="Refresh insights">
          <RefreshRoundedIcon fontSize="small" />
        </IconButton>
      </Stack>

      <Stack spacing={1.25}>
        {visible.length ? (
          visible.map((insight) => (
            <Box
              key={insight.id}
              onClick={() => insight.href && navigate(insight.href)}
              sx={{
                px: 1.5,
                py: 1.25,
                borderRadius: 1.5,
                border: '1px solid',
                borderColor: 'divider',
                cursor: insight.href ? 'pointer' : 'default',
                transition: 'background-color 0.15s ease, box-shadow 0.15s ease',
                '&:hover': insight.href ? { bgcolor: 'action.hover' } : undefined,
              }}
            >
              <Stack direction="row" spacing={1} sx={{ alignItems: 'flex-start' }}>
                <Typography sx={{ fontSize: 14, lineHeight: 1.2, flexShrink: 0, mt: 0.15 }}>
                  {severityIcon[insight.severity] ?? '🔵'}
                </Typography>
                <Box sx={{ flex: 1, minWidth: 0, pr: 0.5 }}>
                  <Typography variant="body2" sx={{ fontWeight: 700, lineHeight: 1.35 }}>
                    {insight.title}
                  </Typography>
                  {insight.detail ? (
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ display: 'block', mt: 0.35, lineHeight: 1.4, wordBreak: 'break-word' }}
                    >
                      {insight.detail}
                    </Typography>
                  ) : null}
                </Box>
                <IconButton
                  size="small"
                  aria-label="Dismiss insight"
                  sx={{ flexShrink: 0, mt: -0.25, mr: -0.5 }}
                  onClick={(event) => {
                    event.stopPropagation();
                    setDismissed((current) => new Set(current).add(insight.id));
                  }}
                >
                  <CloseRoundedIcon sx={{ fontSize: 14 }} />
                </IconButton>
              </Stack>
            </Box>
          ))
        ) : (
          <Typography variant="body2" color="text.secondary">
            {loading ? 'Analyzing engineering data…' : 'No priority insights right now.'}
          </Typography>
        )}
      </Stack>

      {insights.length > 5 ? (
        <Button
          size="small"
          sx={{ mt: 1, textTransform: 'none', fontWeight: 700 }}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? 'Show Less' : 'View More'}
        </Button>
      ) : null}
    </Box>
  );
}
