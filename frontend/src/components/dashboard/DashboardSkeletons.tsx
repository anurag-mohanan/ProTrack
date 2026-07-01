import { Box, Skeleton } from '@mui/material';

export function DashboardKpiSkeleton({ count = 4 }: { count?: number }) {
  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: {
          xs: '1fr',
          sm: 'repeat(2, 1fr)',
          lg: `repeat(${Math.min(count, 4)}, 1fr)`,
        },
        gap: 2,
      }}
    >
      {Array.from({ length: count }).map((_, index) => (
        <Skeleton
          key={index}
          variant="rounded"
          height={112}
          sx={{ borderRadius: 3 }}
        />
      ))}
    </Box>
  );
}

export function DashboardPanelSkeleton({ height = 240 }: { height?: number }) {
  return <Skeleton variant="rounded" height={height} sx={{ borderRadius: 3 }} />;
}
