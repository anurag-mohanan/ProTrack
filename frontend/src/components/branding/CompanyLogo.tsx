import { Box, Typography, useTheme } from '@mui/material';
import { useCompany } from '../../context/CompanyContext';
import { getAssetUrl } from '../../utils/assetUrl';

interface CompanyLogoProps {
  variant?: 'full' | 'mark';
  light?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

const sizeMap = {
  sm: { mark: 28, title: '1rem', subtitle: '0.625rem' },
  md: { mark: 36, title: '1.125rem', subtitle: '0.6875rem' },
  lg: { mark: 48, title: '1.5rem', subtitle: '0.75rem' },
};

export function CompanyLogo({
  variant = 'full',
  light = false,
  size = 'md',
}: CompanyLogoProps) {
  const theme = useTheme();
  const { company, appName } = useCompany();
  const dimensions = sizeMap[size];
  const logoUrl = getAssetUrl(company?.logo_url);
  const primary = theme.palette.primary.main;
  const textColor = light ? theme.palette.prosohm.sidebarText : theme.palette.text.primary;
  const subtitle = company?.company_name ?? appName;
  const markLetter = (company?.company_short_name || company?.company_name || 'P').charAt(0).toUpperCase();

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
      <Box
        sx={{
          width: dimensions.mark,
          height: dimensions.mark,
          borderRadius: '12px',
          overflow: 'hidden',
          background: logoUrl
            ? theme.palette.background.paper
            : `linear-gradient(135deg, ${primary} 0%, ${theme.palette.primary.dark} 100%)`,
          display: 'grid',
          placeItems: 'center',
          boxShadow: logoUrl ? 'none' : `0 8px 20px ${theme.palette.primary.main}33`,
        }}
      >
        {logoUrl ? (
          <Box
            component="img"
            src={logoUrl}
            alt={`${subtitle} logo`}
            sx={{ width: '100%', height: '100%', objectFit: 'contain' }}
          />
        ) : (
          <Typography
            sx={{
              color: 'primary.contrastText',
              fontWeight: 800,
              fontSize: dimensions.mark * 0.38,
              lineHeight: 1,
            }}
          >
            {markLetter}
          </Typography>
        )}
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
            ProTrack
          </Typography>
          {size !== 'sm' ? (
            <Typography
              sx={{
                fontSize: dimensions.subtitle,
                fontWeight: 600,
                color: light ? theme.palette.prosohm.sidebarTextMuted : 'text.secondary',
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
              }}
            >
              {subtitle}
            </Typography>
          ) : null}
        </Box>
      ) : null}
    </Box>
  );
}

/** @deprecated Use CompanyLogo */
export const ProsohmLogo = CompanyLogo;
