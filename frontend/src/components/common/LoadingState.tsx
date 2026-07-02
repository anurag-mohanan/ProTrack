import { Box, CircularProgress, Skeleton, Typography } from '@mui/material';

interface LoadingStateProps {
  message?: string;
  variant?: 'spinner' | 'skeleton';
}

export function LoadingState({
  message = 'Loading…',
  variant = 'spinner',
}: LoadingStateProps) {
  if (variant === 'skeleton') {
    return (
      <Box sx={{ py: 2 }}>
        <Skeleton variant="rounded" height={40} sx={{ mb: 2, borderRadius: 2 }} />
        <Skeleton variant="rounded" height={240} sx={{ borderRadius: 2 }} />
        <Typography color="text.secondary" variant="body2" sx={{ mt: 2, textAlign: 'center' }}>
          {message}
        </Typography>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 2,
        py: 8,
      }}
    >
      <CircularProgress size={36} thickness={4} />
      <Typography color="text.secondary" variant="body2">
        {message}
      </Typography>
    </Box>
  );
}
