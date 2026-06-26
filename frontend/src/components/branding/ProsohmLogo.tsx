import { Box, Typography, useTheme } from '@mui/material';

interface ProsohmLogoProps {
  variant?: 'full' | 'mark';
  light?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

const sizeMap = {
  sm: { mark: 28, title: '1rem', subtitle: '0.625rem' },
  md: { mark: 36, title: '1.125rem', subtitle: '0.6875rem' },
  lg: { mark: 48, title: '1.5rem', subtitle: '0.75rem' },
};

export function ProsohmLogo({
  variant = 'full',
  light = false,
  size = 'md',
}: ProsohmLogoProps) {
  const theme = useTheme();
  const dimensions = sizeMap[size];
  const primary = theme.palette.primary.main;
  const textColor = light
    ? theme.palette.prosohm.sidebarText
    : theme.palette.text.primary;

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
      <Box
        sx={{
          width: dimensions.mark,
          height: dimensions.mark,
          borderRadius: '12px',
          background: `linear-gradient(135deg, ${primary} 0%, ${theme.palette.primary.dark} 100%)`,
          display: 'grid',
          placeItems: 'center',
          boxShadow: `0 8px 20px ${theme.palette.primary.main}33`,
        }}
      >
        <Typography
          sx={{
            color: 'primary.contrastText',
            fontWeight: 800,
            fontSize: dimensions.mark * 0.38,
            lineHeight: 1,
          }}
        >
          P
        </Typography>
      </Box>
      {variant === 'full' ? (
        <Box>
          <Typography
            sx={{
              fontWeight: 800,
              fontSize: dimensions.title,
              lineHeight: 1.1,
              color: textColor,
              letterSpacing: '-0.02em',
            }}
          >
            Prosohm
          </Typography>
          {size !== 'sm' ? (
            <Typography
              sx={{
                fontSize: dimensions.subtitle,
                fontWeight: 600,
                color: light ? theme.palette.prosohm.sidebarTextMuted : 'text.secondary',
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
              }}
            >
              ProTrack
            </Typography>
          ) : null}
        </Box>
      ) : null}
    </Box>
  );
}
