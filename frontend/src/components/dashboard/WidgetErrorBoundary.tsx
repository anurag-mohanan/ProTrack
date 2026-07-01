import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Paper, Typography } from '@mui/material';

interface WidgetErrorBoundaryProps {
  children: ReactNode;
  title?: string;
}

interface WidgetErrorBoundaryState {
  hasError: boolean;
}

export class WidgetErrorBoundary extends Component<
  WidgetErrorBoundaryProps,
  WidgetErrorBoundaryState
> {
  state: WidgetErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): WidgetErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Dashboard widget failed:', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <Paper variant="outlined" sx={{ borderRadius: 3, p: 2.5 }}>
          <Typography variant="body2" color="text.secondary">
            No data available.
          </Typography>
        </Paper>
      );
    }
    return this.props.children;
  }
}
