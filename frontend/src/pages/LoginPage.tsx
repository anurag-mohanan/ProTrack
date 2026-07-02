import { useState } from 'react';
import {
  Alert,
  Box,
  Card,
  CardContent,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import EngineeringIcon from '@mui/icons-material/Engineering';
import { useNavigate } from 'react-router-dom';
import { getErrorMessage } from '../api/client';
import { CompanyLogo } from '../components/branding/CompanyLogo';
import { ProsohmButton } from '../components/ui/ProsohmButton';
import { PasswordField } from '../components/ui/design-system';
import {
  COMPANY_BYLINE,
  COPYRIGHT_NOTICE,
  PRODUCT_TAGLINE,
  RELEASE_LABEL,
  VERSION_DISPLAY,
} from '../config/appMeta';
import { IS_DEVELOPMENT } from '../config/env';
import { useAuth } from '../context/AuthContext';

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const currentUser = await login({ email, password });
      navigate(currentUser.must_change_password ? '/change-password' : '/dashboard');
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', lg: '1.1fr 1fr' },
        bgcolor: 'background.default',
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
        }}
      >
        <Box
          sx={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            p: { xs: 2, md: 4 },
          }}
        >
          <Card sx={{ width: '100%', maxWidth: 460, borderRadius: 3 }}>
            <CardContent sx={{ p: { xs: 3, md: 4 } }}>
              <Stack spacing={3} component="form" onSubmit={handleSubmit}>
                <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1.5 }}>
                  <CompanyLogo size="lg" showByline />
                </Box>

                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h5" sx={{ fontWeight: 700, mb: 0.5 }}>
                    Welcome to ProTrack
                  </Typography>
                  <Typography color="text.secondary">{PRODUCT_TAGLINE}</Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                    {COMPANY_BYLINE}
                  </Typography>
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
                {IS_DEVELOPMENT ? (
                  <Typography variant="caption" color="text.secondary">
                    Internal release: contact your administrator if you need access credentials.
                  </Typography>
                ) : null}
                <ProsohmButton
                  type="submit"
                  buttonVariant="primary"
                  size="large"
                  loading={submitting}
                  fullWidth
                >
                  Sign In
                </ProsohmButton>

                <Box sx={{ textAlign: 'center', pt: 1 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontWeight: 600 }}>
                    Version: {VERSION_DISPLAY}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                    {RELEASE_LABEL}
                  </Typography>
                </Box>
              </Stack>
            </CardContent>
          </Card>
        </Box>

        <Box sx={{ px: 2, pb: 2, textAlign: 'center' }}>
          <Typography variant="caption" color="text.secondary">
            {COPYRIGHT_NOTICE}
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}
