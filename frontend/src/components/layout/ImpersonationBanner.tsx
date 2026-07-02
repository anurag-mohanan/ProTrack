import { Alert, Box, Button } from '@mui/material';
import { useAuth } from '../../context/AuthContext';
import { userDisplayName } from '../../utils/format';

export function ImpersonationBanner() {
  const { user, isImpersonating, stopImpersonation } = useAuth();

  if (!isImpersonating || !user) {
    return null;
  }

  return (
    <Box sx={{ position: 'sticky', top: 0, zIndex: (theme) => theme.zIndex.drawer + 2 }}>
      <Alert
        severity="warning"
        action={
          <Button color="inherit" size="small" onClick={() => void stopImpersonation()}>
            Return to Administrator
          </Button>
        }
        sx={{ borderRadius: 0 }}
      >
        You are currently impersonating {userDisplayName(user)}
      </Alert>
    </Box>
  );
}
