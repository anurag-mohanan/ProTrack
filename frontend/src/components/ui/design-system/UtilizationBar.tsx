import { Box, Typography } from '@mui/material';
import { designTokens } from '../../../theme/designTokens';

interface UtilizationBarProps {
  label: string;
  value: number;
  showValue?: boolean;
  height?: number;
}

function barColor(value: number): string {
  if (value >= 90) return designTokens.utilization.high;
  if (value >= 75) return designTokens.utilization.medium;
  return designTokens.utilization.low;
}

export function UtilizationBar({
  label,
  value,
  showValue = true,
  height = 8,
}: UtilizationBarProps) {
  const clamped = Math.min(100, Math.max(0, value));
  const color = barColor(clamped);

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, width: '100%' }}>
      <Typography
        variant="body2"
        sx={{
          fontWeight: 600,
          minWidth: 88,
          maxWidth: 120,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {label}
      </Typography>
      <Box
        sx={{
          flex: 1,
          height,
          borderRadius: designTokens.radius.pill,
          bgcolor: designTokens.semantic.neutralSoft,
          overflow: 'hidden',
        }}
      >
        <Box
          sx={{
            width: `${clamped}%`,
            height: '100%',
            borderRadius: designTokens.radius.pill,
            bgcolor: color,
            transition: `width ${designTokens.motion.normal}`,
          }}
        />
      </Box>
      {showValue ? (
        <Typography variant="caption" sx={{ fontWeight: 700, minWidth: 36, textAlign: 'right' }}>
          {clamped}%
        </Typography>
      ) : null}
    </Box>
  );
}
