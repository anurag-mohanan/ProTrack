import type { ReactNode } from 'react';
import { Box, Card, CardContent, Typography, useTheme, type Theme } from '@mui/material';
import type { SvgIconComponent } from '@mui/icons-material';

type AccentColor = 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info' | 'accent';

interface BaseCardProps {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  accent?: AccentColor;
  icon?: SvgIconComponent;
  subtitle?: string;
  value?: string | number;
  onClick?: () => void;
}

function accentColor(theme: Theme, accent: AccentColor) {
  if (accent === 'accent') {
    return theme.palette.accent.main;
  }
  return theme.palette[accent].main;
}

function CardShell({
  title,
  children,
  action,
  accent = 'primary',
  icon: Icon,
  subtitle,
  value,
  onClick,
}: BaseCardProps) {
  const theme = useTheme();
  const color = accentColor(theme, accent);

  return (
    <Card
      onClick={onClick}
      sx={{
        height: '100%',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'transform 0.2s ease, box-shadow 0.2s ease',
        borderLeft: `4px solid ${color}`,
        '&:hover': onClick
          ? {
              transform: 'translateY(-2px)',
              boxShadow: (theme) => theme.palette.prosohm.shadowCardHover,
            }
          : undefined,
      }}
    >
      <CardContent sx={{ p: 3 }}>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: 2,
            mb: value || children ? 1.5 : 0,
          }}
        >
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="cardTitle" color="text.secondary" gutterBottom>
              {title}
            </Typography>
            {value !== undefined ? (
              <Typography variant="h4" sx={{ fontWeight: 700, color: 'text.primary' }}>
                {value}
              </Typography>
            ) : null}
            {subtitle ? (
              <Typography variant="captionLabel" color="text.secondary" sx={{ mt: 0.5 }}>
                {subtitle}
              </Typography>
            ) : null}
          </Box>
          {Icon ? (
            <Box
              sx={{
                width: 44,
                height: 44,
                borderRadius: '12px',
                display: 'grid',
                placeItems: 'center',
                bgcolor: `${color}18`,
                color,
                flexShrink: 0,
              }}
            >
              <Icon fontSize="small" />
            </Box>
          ) : null}
          {action}
        </Box>
        {children}
      </CardContent>
    </Card>
  );
}

export function DashboardCard(props: BaseCardProps) {
  return <CardShell {...props} />;
}

export function InfoCard(props: BaseCardProps) {
  return <CardShell {...props} accent="info" />;
}

export function SummaryCard(props: BaseCardProps) {
  return <CardShell {...props} accent="secondary" />;
}

export function ReportCard(props: BaseCardProps) {
  return <CardShell {...props} accent="accent" />;
}

export function AdministrationCard(props: BaseCardProps) {
  return <CardShell {...props} accent="secondary" />;
}

export function ProjectCard(props: BaseCardProps) {
  return <CardShell {...props} accent="primary" />;
}

interface ContentCardProps {
  children: ReactNode;
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  noPadding?: boolean;
}

export function ContentCard({
  children,
  title,
  subtitle,
  action,
  noPadding = false,
}: ContentCardProps) {
  return (
    <Card>
      {title ? (
        <Box
          sx={{
            px: 3,
            pt: 3,
            pb: noPadding ? 1 : 0,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: 2,
          }}
        >
          <Box>
            <Typography variant="sectionTitle">{title}</Typography>
            {subtitle ? (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                {subtitle}
              </Typography>
            ) : null}
          </Box>
          {action}
        </Box>
      ) : null}
      <CardContent sx={{ p: noPadding ? 0 : 3, '&:last-child': { pb: noPadding ? 0 : 3 } }}>
        {children}
      </CardContent>
    </Card>
  );
}
