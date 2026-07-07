import type { ReactNode } from 'react';
import { Box, Breadcrumbs, Link, Typography } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { designTokens } from '../../../theme/designTokens';

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface ModernPageHeaderProps {
  title: string;
  subtitle?: string;
  breadcrumbs?: BreadcrumbItem[];
  actions?: ReactNode;
  summary?: ReactNode;
}

export function ModernPageHeader({
  title,
  subtitle,
  breadcrumbs,
  actions,
  summary,
}: ModernPageHeaderProps) {
  return (
    <Box sx={{ mb: 3 }}>
      {breadcrumbs?.length ? (
        <Breadcrumbs sx={{ mb: 1, '& .MuiBreadcrumbs-li': { fontSize: '0.8125rem' } }}>
          {breadcrumbs.map((item, index) =>
            item.href && index < breadcrumbs.length - 1 ? (
              <Link
                key={item.label}
                component={RouterLink}
                to={item.href}
                underline="hover"
                color="text.secondary"
              >
                {item.label}
              </Link>
            ) : (
              <Typography key={item.label} variant="caption" color="text.secondary">
                {item.label}
              </Typography>
            ),
          )}
        </Breadcrumbs>
      ) : null}
      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 2,
        }}
      >
        <Box>
          <Typography
            variant="h5"
            sx={{ fontWeight: 700, letterSpacing: '-0.02em', lineHeight: 1.2 }}
          >
            {title}
          </Typography>
          {subtitle ? (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, maxWidth: 640 }}>
              {subtitle}
            </Typography>
          ) : null}
        </Box>
        {actions ? (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>{actions}</Box>
        ) : null}
      </Box>
      {summary ? (
        <Box
          sx={{
            mt: 2,
            p: 2,
            borderRadius: `${designTokens.radius.md}px`,
            bgcolor: designTokens.semantic.primarySoft,
            border: '1px solid',
            borderColor: 'divider',
          }}
        >
          {summary}
        </Box>
      ) : null}
    </Box>
  );
}
