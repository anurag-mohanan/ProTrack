import { Box, Typography, useTheme } from '@mui/material';
import { useCompany } from '../../context/CompanyContext';
import { COMPANY_BYLINE, PRODUCT_NAME, PRODUCT_TAGLINE } from '../../config/appMeta';
import { resolveAssetUrl } from '../../config/env';

interface CompanyLogoProps {
  variant?: 'full' | 'mark';
  light?: boolean;
  size?: 'sm' | 'md' | 'lg';
  showByline?: boolean;
}

const sizeMap = {
  sm: { mark: 28, title: '1rem', subtitle: '0.625rem', byline: '0.5625rem' },
  md: { mark: 36, title: '1.125rem', subtitle: '0.6875rem', byline: '0.625rem' },
  lg: { mark: 48, title: '1.5rem', subtitle: '0.75rem', byline: '0.6875rem' },
};

export function CompanyLogo({
  variant = 'full',
  light = false,
  size = 'md',
  showByline = false,
}: CompanyLogoProps) {
  const theme = useTheme();
  const { company } = useCompany();
  const dimensions = sizeMap[size];
  const logoUrl = resolveAssetUrl(company?.logo_url);
  const primary = theme.palette.primary.main;
  const textColor = light ? theme.palette.prosohm.sidebarText : theme.palette.text.primary;
  const mutedColor = light ? theme.palette.prosohm.sidebarTextMuted : 'text.secondary';
  const markLetter = 'P';

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, minWidth: 0 }}>
      <Box
        sx={{
          width: dimensions.mark,
          height: dimensions.mark,
          borderRadius: '12px',
          overflow: 'hidden',
          flexShrink: 0,
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
            alt={`${company?.company_name ?? PRODUCT_NAME} logo`}
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
        <Box sx={{ minWidth: 0 }}>
          <Typography
            sx={{
              fontWeight: 800,
              fontSize: dimensions.title,
              lineHeight: 1.1,
              color: textColor,
              letterSpacing: '-0.02em',
              whiteSpace: 'nowrap',
            }}
          >
            {PRODUCT_NAME}
          </Typography>
          {size !== 'sm' ? (
            <Typography
              sx={{
                fontSize: dimensions.subtitle,
                fontWeight: 600,
                color: mutedColor,
                letterSpacing: '0.02em',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {PRODUCT_TAGLINE}
            </Typography>
          ) : null}
          {showByline && size === 'lg' ? (
            <Typography
              sx={{
                fontSize: dimensions.byline,
                fontWeight: 500,
                color: mutedColor,
                mt: 0.25,
              }}
            >
              {COMPANY_BYLINE}
            </Typography>
          ) : null}
        </Box>
      ) : null}
    </Box>
  );
}

/** @deprecated Use CompanyLogo */
export const ProsohmLogo = CompanyLogo;
