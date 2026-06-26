import { Box, Skeleton } from '@mui/material';

interface TableSkeletonProps {
  rows?: number;
  columns?: number;
}

export function TableSkeleton({ rows = 8, columns = 6 }: TableSkeletonProps) {
  return (
    <Box sx={{ p: 2 }}>
      <Skeleton variant="rounded" height={48} sx={{ mb: 1 }} />
      {Array.from({ length: rows }, (_, rowIndex) => (
        <Box
          key={rowIndex}
          sx={{
            display: 'grid',
            gridTemplateColumns: `repeat(${columns}, 1fr)`,
            gap: 1.5,
            mb: 1,
          }}
        >
          {Array.from({ length: columns }, (_, colIndex) => (
            <Skeleton key={colIndex} variant="rounded" height={36} />
          ))}
        </Box>
      ))}
    </Box>
  );
}
