import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Alert, Box } from '@mui/material';

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
        <Box sx={{ mb: 2 }}>
          <Alert severity="warning">
            {this.props.title ? `Unable to load ${this.props.title}.` : 'Unable to load widget.'}
          </Alert>
        </Box>
      );
    }
    return this.props.children;
  }
}
