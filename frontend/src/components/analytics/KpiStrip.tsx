import type { ReactNode } from 'react';
import { Grid } from '@mui/material';

interface KpiStripProps {
  children: ReactNode;
  columns?: { xs?: number; sm?: number; md?: number; lg?: number };
}

export function KpiStrip({ children, columns = { xs: 12, sm: 6, md: 4, lg: 3 } }: KpiStripProps) {
  return (
    <Grid container spacing={2}>
      {Array.isArray(children)
        ? children.map((child, index) => (
            <Grid key={index} size={columns}>
              {child}
            </Grid>
          ))
        : (
            <Grid size={columns}>{children}</Grid>
          )}
    </Grid>
  );
}
