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
import { useCompany } from '../context/CompanyContext';
import { CompanyLogo } from '../components/branding/CompanyLogo';
import { ProsohmButton } from '../components/ui/ProsohmButton';
import { PasswordField } from '../components/ui/design-system';
import { useAuth } from '../context/AuthContext';

export function LoginPage() {
  const { login } = useAuth();
  const { company } = useCompany();
  const navigate = useNavigate();
  const companyName = company?.company_name ?? 'your organisation';
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
        <CompanyLogo light size="lg" />
        <Box>
          <Typography variant="h3" sx={{ fontWeight: 700, mb: 2, maxWidth: 480 }}>
            Engineering excellence, delivered.
          </Typography>
          <Typography variant="body1" sx={{ color: 'prosohm.sidebarTextMuted', maxWidth: 520 }}>
            ProTrack connects project delivery, milestones, timesheets, and administration in
            one professional workspace for {companyName}.
          </Typography>
        </Box>
        <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
          <EngineeringIcon sx={{ color: 'primary.main' }} />
          <Typography variant="captionLabel" sx={{ color: 'prosohm.sidebarTextMuted' }}>
            Injection mould design · Project tracking · Resource planning
          </Typography>
        </Stack>
      </Box>

      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          p: { xs: 2, md: 4 },
        }}
      >
        <Card sx={{ width: '100%', maxWidth: 460 }}>
          <CardContent sx={{ p: { xs: 3, md: 4 } }}>
            <Stack spacing={3} component="form" onSubmit={handleSubmit}>
              <Box sx={{ display: { xs: 'flex', lg: 'none' }, justifyContent: 'center' }}>
                <CompanyLogo size="lg" />
              </Box>
              <Box sx={{ textAlign: { xs: 'center', lg: 'left' } }}>
                <Typography variant="pageTitle" gutterBottom>
                  Welcome back
                </Typography>
                <Typography color="text.secondary">
                  Sign in to ProTrack — {companyName}&apos;s engineering management platform.
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
              <Typography variant="caption" color="text.secondary">
                First-time users may sign in with the temporary password Prosohm@2026, then set a new password.
              </Typography>
              <ProsohmButton
                type="submit"
                buttonVariant="primary"
                size="large"
                loading={submitting}
                fullWidth
              >
                Sign In
              </ProsohmButton>
            </Stack>
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
}
