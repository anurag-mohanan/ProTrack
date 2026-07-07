import { Breadcrumbs, Link, Typography } from '@mui/material';
import type { DrillDownLevel } from '../../hooks/useDrillDown';

interface DrillDownBreadcrumbsProps {
  stack: DrillDownLevel[];
  onNavigate: (index: number) => void;
  onReset: () => void;
}

export function DrillDownBreadcrumbs({ stack, onNavigate, onReset }: DrillDownBreadcrumbsProps) {
  if (!stack.length) return null;

  return (
    <Breadcrumbs sx={{ mb: 2 }}>
      <Link
        component="button"
        underline="hover"
        color="inherit"
        onClick={onReset}
        sx={{ fontSize: '0.8125rem', fontWeight: 600 }}
      >
        All
      </Link>
      {stack.map((level, index) =>
        index < stack.length - 1 ? (
          <Link
            key={`${level.type}-${level.id}`}
            component="button"
            underline="hover"
            color="inherit"
            onClick={() => onNavigate(index)}
            sx={{ fontSize: '0.8125rem' }}
          >
            {level.label}
          </Link>
        ) : (
          <Typography key={`${level.type}-${level.id}`} variant="body2" sx={{ fontWeight: 700 }}>
            {level.label}
          </Typography>
        ),
      )}
    </Breadcrumbs>
  );
}
