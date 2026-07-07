import { Box, Skeleton, Typography } from '@mui/material';

export function DashboardKpiSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <Box sx={{ mb: 1.5 }}>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <Box key={rowIndex} sx={{ mb: 0.75 }}>
          <Typography
            variant="caption"
            sx={{ fontWeight: 700, color: 'text.secondary', fontSize: 10, mb: 0.4, display: 'block' }}
          >
            <Skeleton width={100} />
          </Typography>
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: {
                xs: 'repeat(2, minmax(0, 1fr))',
                sm: 'repeat(3, minmax(0, 1fr))',
                md: 'repeat(4, minmax(0, 1fr))',
                xl: 'repeat(5, minmax(0, 1fr))',
              },
              gap: 0.75,
            }}
          >
            {Array.from({ length: 5 }).map((__, colIndex) => (
              <Skeleton
                key={colIndex}
                variant="rounded"
                height={52}
                sx={{ borderRadius: 1.5 }}
              />
            ))}
          </Box>
        </Box>
      ))}
    </Box>
  );
}

export function DashboardPanelSkeleton({ height = 240 }: { height?: number }) {
  return <Skeleton variant="rounded" height={height} sx={{ borderRadius: 2 }} />;
}
