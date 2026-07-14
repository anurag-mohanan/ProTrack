import { Children, type ReactNode } from 'react';
import { Box } from '@mui/material';

interface KpiStripProps {
  children: ReactNode;
  /** Preferred column count at md+ (clamped to child count). Default 4. */
  columns?: number | { xs?: number; sm?: number; md?: number; lg?: number };
}

/**
 * Equal-width KPI row. Always stretches cards so every cell matches page width.
 * Accepts legacy Grid `size` objects for call-site compatibility; only the count matters.
 */
export function KpiStrip({ children, columns = 4 }: KpiStripProps) {
  const items = Children.toArray(children).filter(Boolean);
  const count = Math.max(items.length, 1);

  const preferred =
    typeof columns === 'number'
      ? columns
      : (columns.md ?? columns.lg ?? columns.sm ?? columns.xs ?? count);

  const mdCols = Math.min(Math.max(preferred, 1), count);

  return (
    <Box
      sx={{
        display: 'grid',
        width: '100%',
        alignItems: 'stretch',
        gap: 1.5,
        gridTemplateColumns: {
          xs: '1fr',
          sm: count === 1 ? '1fr' : 'repeat(2, minmax(0, 1fr))',
          md: `repeat(${mdCols}, minmax(0, 1fr))`,
        },
        '& > *': {
          minWidth: 0,
          height: '100%',
        },
      }}
    >
      {items}
    </Box>
  );
}
