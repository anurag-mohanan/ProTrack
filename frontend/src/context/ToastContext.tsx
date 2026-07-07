import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { Alert, Snackbar } from '@mui/material';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import ErrorRoundedIcon from '@mui/icons-material/ErrorRounded';
import InfoRoundedIcon from '@mui/icons-material/InfoRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import { designTokens } from '../theme/designTokens';

type ToastSeverity = 'success' | 'error' | 'info' | 'warning';

interface ToastState {
  open: boolean;
  message: string;
  severity: ToastSeverity;
}

interface ToastContextValue {
  showSuccess: (message: string) => void;
  showError: (message: string) => void;
  showInfo: (message: string) => void;
  showWarning: (message: string) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

const SEVERITY_ICONS = {
  success: CheckCircleRoundedIcon,
  error: ErrorRoundedIcon,
  info: InfoRoundedIcon,
  warning: WarningAmberRoundedIcon,
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<ToastState>({
    open: false,
    message: '',
    severity: 'success',
  });

  const show = useCallback((message: string, severity: ToastSeverity) => {
    setToast({ open: true, message, severity });
  }, []);

  const value = useMemo<ToastContextValue>(
    () => ({
      showSuccess: (message) => show(message, 'success'),
      showError: (message) => show(message, 'error'),
      showInfo: (message) => show(message, 'info'),
      showWarning: (message) => show(message, 'warning'),
    }),
    [show],
  );

  const handleClose = () => {
    setToast((current) => ({ ...current, open: false }));
  };

  const Icon = SEVERITY_ICONS[toast.severity];

  return (
    <ToastContext.Provider value={value}>
      {children}
      <Snackbar
        open={toast.open}
        autoHideDuration={4500}
        onClose={handleClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        sx={{ mb: 2 }}
      >
        <Alert
          severity={toast.severity}
          onClose={handleClose}
          variant="filled"
          icon={<Icon fontSize="small" />}
          sx={{
            borderRadius: `${designTokens.radius.md}px`,
            fontWeight: 600,
            boxShadow: designTokens.elevation.cardHover,
            minWidth: 280,
          }}
        >
          {toast.message}
        </Alert>
      </Snackbar>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within ToastProvider');
  }
  return context;
}
