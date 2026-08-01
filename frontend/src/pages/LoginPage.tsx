import { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Card,
  CardContent,
  Divider,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import EngineeringIcon from '@mui/icons-material/Engineering';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiClient, getErrorMessage } from '../api/client';
import { CompanyLogo } from '../components/branding/CompanyLogo';
import { ProsohmButton } from '../components/ui/ProsohmButton';
import { PasswordField } from '../components/ui/design-system';
import { COPYRIGHT_NOTICE, PRODUCT_NAME, VERSION_DISPLAY } from '../config/appMeta';
import { getApiBaseUrl, requiresForcedPasswordChange } from '../config/env';
import { useAuth } from '../context/AuthContext';

const SSO_ERROR_MESSAGES: Record<string, string> = {
  no_local_user: 'No ProTrack account matches that Microsoft sign-in. Ask an admin to create your user first.',
  account_inactive: 'Your ProTrack account is inactive.',
  sso_subject_conflict: 'This Microsoft account is linked to a different ProTrack user.',
  sso_disabled: 'SSO is not enabled on this server.',
  missing_code: 'SSO callback was incomplete. Try again.',
  callback_failed: 'SSO sign-in failed. Try again or use email/password.',
};

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const oidcQuery = useQuery({
    queryKey: ['auth', 'oidc-status'],
    queryFn: async () =>
      (await apiClient.get<{ enabled: boolean; testing: boolean }>('/auth/oidc/status')).data,
    staleTime: 60_000,
  });

  useEffect(() => {
    const ssoError = searchParams.get('sso_error');
    if (ssoError) {
      setError(SSO_ERROR_MESSAGES[ssoError] || `SSO error: ${ssoError}`);
    }
  }, [searchParams]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const currentUser = await login({ email, password });
      navigate(
        requiresForcedPasswordChange(currentUser.must_change_password)
          ? '/change-password'
          : '/dashboard',
      );
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const handleSso = () => {
    // Full navigation so cookies/redirects from the API host work.
    window.location.href = `${getApiBaseUrl()}/auth/oidc/login`;
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        '@supports (min-height: 100dvh)': { minHeight: '100dvh' },
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', lg: '1.1fr 1fr' },
        bgcolor: 'background.default',
        maxWidth: '100%',
        overflowX: 'clip',
      }}
    >
      <Box
        sx={{
          display: { xs: 'none', lg: 'flex' },
          flexDirection: 'column',
          justifyContent: 'space-between',
          p: 6,
          color: 'prosohm.sidebarText',
          background: (theme) => theme.palette.prosohm.gradientLogin,
        }}
      >
        <CompanyLogo light size="lg" showByline />
        <Box>
          <Typography variant="h3" sx={{ fontWeight: 700, mb: 2, maxWidth: 520 }}>
            Precision engineering delivery, managed in one workspace.
          </Typography>
          <Typography variant="body1" sx={{ color: 'prosohm.sidebarTextMuted', maxWidth: 540 }}>
            ProTrack connects project delivery, milestones, timesheets, resource planning, and
            system administration for Prosohm engineering teams.
          </Typography>
        </Box>
        <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
          <EngineeringIcon sx={{ color: 'primary.main' }} />
          <Typography variant="captionLabel" sx={{ color: 'prosohm.sidebarTextMuted' }}>
            Mold design · Project tracking · Resource planning
          </Typography>
        </Stack>
      </Box>

      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          minHeight: '100vh',
          '@supports (min-height: 100dvh)': { minHeight: '100dvh' },
        }}
      >
        <Box
          sx={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            p: { xs: 2, md: 4 },
            width: '100%',
            maxWidth: '100%',
          }}
        >
          <Card sx={{ width: '100%', maxWidth: 420, borderRadius: 3 }}>
            <CardContent sx={{ p: { xs: 3, md: 4 } }}>
              <Stack spacing={3} component="form" onSubmit={handleSubmit}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h5" sx={{ fontWeight: 700, mb: 0.5 }}>
                    Welcome to {PRODUCT_NAME}
                  </Typography>
                  <Typography color="text.secondary">Sign in to continue</Typography>
                </Box>

                {error ? <Alert severity="error">{error}</Alert> : null}

                <TextField
                  label="Email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                  fullWidth
                  autoComplete="username"
                />
                <PasswordField
                  label="Password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                  autoComplete="current-password"
                />
                <ProsohmButton
                  type="submit"
                  buttonVariant="primary"
                  size="large"
                  loading={submitting}
                  fullWidth
                >
                  Sign In
                </ProsohmButton>

                {oidcQuery.data?.enabled ? (
                  <>
                    <Divider>
                      <Typography variant="caption" color="text.secondary">
                        or
                      </Typography>
                    </Divider>
                    <ProsohmButton
                      type="button"
                      buttonVariant="outlined"
                      size="large"
                      fullWidth
                      onClick={handleSso}
                    >
                      Sign in with Microsoft
                    </ProsohmButton>
                  </>
                ) : null}
              </Stack>
            </CardContent>
          </Card>
        </Box>

        <Box sx={{ px: 2, pb: 2, textAlign: 'center' }}>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
            {PRODUCT_NAME} {VERSION_DISPLAY}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {COPYRIGHT_NOTICE}
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}
