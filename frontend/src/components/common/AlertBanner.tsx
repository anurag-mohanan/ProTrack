import { Alert } from '@mui/material';

interface AlertBannerProps {
  message: string | null;
  onClose?: () => void;
}

export default function AlertBanner({ message, onClose }: AlertBannerProps) {
  if (!message) return null;
  return (
    <Alert severity="error" onClose={onClose} sx={{ mb: 2 }}>
      {message}
    </Alert>
  );
}
