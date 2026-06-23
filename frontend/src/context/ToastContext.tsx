import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { Alert, Snackbar } from '@mui/material';

type ToastSeverity = 'success' | 'error' | 'info';

interface ToastState {
  open: boolean;
  message: string;
  severity: ToastSeverity;
}

interface ToastContextValue {
  showSuccess: (message: string) => void;
  showError: (message: string) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

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
    }),
    [show],
  );

  const handleClose = () => {
    setToast((current) => ({ ...current, open: false }));
  };

  return (
    <ToastContext.Provider value={value}>
      {children}
      <Snackbar
        open={toast.open}
        autoHideDuration={4000}
        onClose={handleClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity={toast.severity} onClose={handleClose} variant="filled">
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
