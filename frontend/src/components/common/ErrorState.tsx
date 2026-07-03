import { Alert, Box, Button } from '@mui/material';
import { getUserFriendlyErrorMessage } from '../../api/client';

interface ErrorStateProps {
  error: unknown;
  title?: string;
  onRetry?: () => void;
}

export function ErrorState({ error, title = 'Unable to load data', onRetry }: ErrorStateProps) {
  return (
    <Box sx={{ py: 2 }}>
      <Alert
        severity="error"
        action={
          onRetry ? (
            <Button color="inherit" size="small" onClick={onRetry}>
              Retry
            </Button>
          ) : undefined
        }
      >
        <strong>{title}:</strong> {getUserFriendlyErrorMessage(error)}
      </Alert>
    </Box>
  );
}
