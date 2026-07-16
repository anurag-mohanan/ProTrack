import { Box, ButtonBase, Stack, Tooltip, Typography } from '@mui/material';
import { alpha, useTheme, type Theme } from '@mui/material/styles';
import type { RatingScaleItem, RatingTone } from './performanceReviewConstants';

type PerformanceReviewRatingPickerProps = {
  value: number | string | null | undefined;
  disabled?: boolean;
  scale: RatingScaleItem[];
  onChange: (value: number | null) => void;
};

function toneColor(theme: Theme, tone: RatingTone): string {
  switch (tone) {
    case 'success':
      return theme.palette.success.main;
    case 'info':
      return theme.palette.info.main;
    case 'warning':
      return theme.palette.warning.main;
    case 'error':
      return theme.palette.error.main;
    case 'primary':
      return theme.palette.primary.main;
    default:
      return theme.palette.text.secondary;
  }
}

export function PerformanceReviewRatingPicker({
  value,
  disabled = false,
  scale,
  onChange,
}: PerformanceReviewRatingPickerProps) {
  const theme = useTheme();
  const selected = value === null || value === undefined || value === '' ? null : Number(value);

  return (
    <Stack direction="row" spacing={0.75} useFlexGap sx={{ flexWrap: 'wrap' }}>
      {scale.map((row) => {
        const active = selected === row.value;
        const color = toneColor(theme, row.tone);
        return (
          <Tooltip key={row.value} title={row.guidance} arrow>
            <ButtonBase
              disabled={disabled}
              onClick={() => onChange(active ? null : row.value)}
              sx={{
                px: 1.25,
                py: 0.75,
                minWidth: row.value === 0 ? 52 : 44,
                borderRadius: 2,
                border: '1.5px solid',
                borderColor: active ? color : alpha(color, 0.35),
                bgcolor: active ? alpha(color, 0.14) : alpha(theme.palette.background.paper, 0.9),
                color: active ? color : theme.palette.text.primary,
                transition: 'all 160ms ease',
                '&:hover': disabled
                  ? undefined
                  : {
                      borderColor: color,
                      bgcolor: alpha(color, 0.08),
                    },
              }}
            >
              <Box sx={{ textAlign: 'center' }}>
                <Typography sx={{ fontWeight: 800, fontSize: 13, lineHeight: 1.1 }}>
                  {row.short_label}
                </Typography>
                <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary' }}>
                  {row.label}
                </Typography>
              </Box>
            </ButtonBase>
          </Tooltip>
        );
      })}
    </Stack>
  );
}
