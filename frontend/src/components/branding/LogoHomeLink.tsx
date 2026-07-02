import type { ComponentProps } from 'react';
import { Box, Tooltip } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { CompanyLogo } from './CompanyLogo';

type LogoHomeLinkProps = ComponentProps<typeof CompanyLogo>;

export function LogoHomeLink(props: LogoHomeLinkProps) {
  return (
    <Tooltip title="Go to Dashboard" arrow>
      <Box
        component={RouterLink}
        to="/dashboard"
        aria-label="Go to Dashboard"
        sx={{
          display: 'inline-flex',
          textDecoration: 'none',
          color: 'inherit',
          cursor: 'pointer',
          borderRadius: 2,
          transition: 'transform 0.18s ease, opacity 0.18s ease',
          '&:hover': {
            opacity: 0.9,
            transform: 'translateY(-1px)',
          },
          '&:active': {
            transform: 'translateY(0)',
          },
        }}
      >
        <CompanyLogo {...props} />
      </Box>
    </Tooltip>
  );
}

/** @deprecated Use LogoHomeLink */
export const ProsohmLogoHomeLink = LogoHomeLink;
