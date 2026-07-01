import { Alert, Box } from '@mui/material';
import { getUserFriendlyErrorMessage } from '../../api/client';

interface ErrorStateProps {
  error: unknown;
  title?: string;
}

export function ErrorState({ error, title = 'Unable to load data' }: ErrorStateProps) {
  return (
    <Box sx={{ py: 2 }}>
      <Alert severity="error">
        <strong>{title}:</strong> {getUserFriendlyErrorMessage(error)}
      </Alert>
    </Box>
  );
}
