import { Box, Skeleton } from '@mui/material';

interface TableSkeletonProps {
  rows?: number;
  columns?: number;
}

export function TableSkeleton({ rows = 8, columns = 6 }: TableSkeletonProps) {
  return (
    <Box
      sx={{
        p: 2,
        borderRadius: 2,
        overflow: 'hidden',
      }}
    >
      <Skeleton
        variant="rounded"
        height={44}
        sx={{ mb: 1.5, borderRadius: 1.5, maxWidth: '100%' }}
      />
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
            <Skeleton
              key={colIndex}
              variant="rounded"
              height={36}
              sx={{
                borderRadius: 1,
                opacity: 1 - rowIndex * 0.06,
              }}
            />
          ))}
        </Box>
      ))}
    </Box>
  );
}
