import { Box, Typography } from '@mui/material';

interface EmptyStateProps {
  title: string;
  description?: string;
}

export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <Box
      sx={{
        py: 6,
        px: 2,
        textAlign: 'center',
        border: '1px dashed',
        borderColor: 'divider',
        borderRadius: 2,
        bgcolor: 'background.paper',
      }}
    >
      <Typography variant="h6" gutterBottom>
        {title}
      </Typography>
      {description ? (
        <Typography color="text.secondary">{description}</Typography>
      ) : null}
    </Box>
  );
}
