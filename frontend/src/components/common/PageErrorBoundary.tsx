import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Alert, Box, Button, Stack, Typography } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';

interface PageErrorBoundaryProps {
  children: ReactNode;
  title?: string;
}

interface PageErrorBoundaryState {
  error: Error | null;
}

export class PageErrorBoundary extends Component<PageErrorBoundaryProps, PageErrorBoundaryState> {
  state: PageErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): PageErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('PageErrorBoundary caught an error:', error, errorInfo);
  }

  private handleRetry = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      return (
        <Box sx={{ py: 4, px: 2 }}>
          <Alert severity="error" sx={{ maxWidth: 720, mx: 'auto' }}>
            <Stack spacing={2}>
              <Typography variant="h6" component="div">
                {this.props.title ?? 'This section could not be loaded.'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {this.state.error.message || 'An unexpected error occurred while rendering this page.'}
              </Typography>
              <Box>
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<RefreshIcon />}
                  onClick={this.handleRetry}
                >
                  Retry
                </Button>
              </Box>
            </Stack>
          </Alert>
        </Box>
      );
    }

    return this.props.children;
  }
}
