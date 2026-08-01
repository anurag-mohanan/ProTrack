import { useEffect, useState } from 'react';
import { Alert, Box, CircularProgress, Stack, Typography } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { requiresForcedPasswordChange } from '../config/env';
import { useAuth } from '../context/AuthContext';
import { resetQueryCache } from '../lib/queryClient';
import { clearAdminToken, setAccessToken } from '../services/authStorage';

/** Completes SSO after IdP redirects here with ``#access_token=...``. */
export function SsoCallbackPage() {
  const navigate = useNavigate();
  const { refreshUser } = useAuth();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const hash = window.location.hash.replace(/^#/, '');
    const params = new URLSearchParams(hash);
    const token = params.get('access_token');
    if (!token) {
      setError('Missing access token from SSO callback.');
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        resetQueryCache();
        clearAdminToken();
        setAccessToken(token);
        const currentUser = await refreshUser();
        if (cancelled) return;
        if (!currentUser) {
          setError('Could not complete SSO sign-in.');
          return;
        }
        navigate(
          requiresForcedPasswordChange(currentUser.must_change_password)
            ? '/change-password'
            : '/dashboard',
          { replace: true },
        );
      } catch {
        if (!cancelled) {
          setError('Could not complete SSO sign-in.');
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [navigate, refreshUser]);

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        p: 2,
      }}
    >
      <Stack spacing={2} sx={{ alignItems: 'center', maxWidth: 420 }}>
        {error ? (
          <Alert severity="error">{error}</Alert>
        ) : (
          <>
            <CircularProgress size={32} />
            <Typography color="text.secondary">Completing Microsoft sign-in…</Typography>
          </>
        )}
      </Stack>
    </Box>
  );
}
