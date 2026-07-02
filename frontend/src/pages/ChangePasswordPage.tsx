import { useState } from 'react';
import { Alert, Box, Card, CardContent, Stack, Typography } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { changePassword } from '../api/auth';
import { getErrorMessage } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { PasswordField } from '../components/ui/design-system';
import { ProsohmButton } from '../components/ui/ProsohmButton';
import { validatePasswordStrength, PASSWORD_REQUIREMENTS_MESSAGE } from '../utils/passwordPolicy';

export function ChangePasswordPage() {
  const { refreshUser } = useAuth();
  const navigate = useNavigate();
  const { showSuccess, showError } = useToast();
  const [form, setForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    const policyError = validatePasswordStrength(form.new_password);
    if (policyError) {
      setError(policyError);
      return;
    }
    if (form.new_password !== form.confirm_password) {
      setError('New password and confirmation do not match.');
      return;
    }

    setSubmitting(true);
    try {
      await changePassword(form);
      await refreshUser();
      showSuccess('Password updated successfully.');
      navigate('/dashboard', { replace: true });
    } catch (err) {
      const message = getErrorMessage(err);
      setError(message);
      showError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        p: 2,
        bgcolor: 'background.default',
      }}
    >
      <Card sx={{ width: '100%', maxWidth: 480 }}>
        <CardContent sx={{ p: { xs: 3, md: 4 } }}>
          <Stack spacing={3} component="form" onSubmit={handleSubmit}>
            <Box>
              <Typography variant="pageTitle" gutterBottom>
                Change Password
              </Typography>
              <Typography color="text.secondary">
                You must set a new password before continuing to ProTrack.
              </Typography>
            </Box>

            {error ? <Alert severity="error">{error}</Alert> : null}

            <PasswordField
              label="Current Password"
              value={form.current_password}
              onChange={(event) =>
                setForm((current) => ({ ...current, current_password: event.target.value }))
              }
              required
              autoComplete="current-password"
            />
            <PasswordField
              label="New Password"
              value={form.new_password}
              onChange={(event) =>
                setForm((current) => ({ ...current, new_password: event.target.value }))
              }
              required
              autoComplete="new-password"
              helper={PASSWORD_REQUIREMENTS_MESSAGE}
            />
            <PasswordField
              label="Confirm Password"
              value={form.confirm_password}
              onChange={(event) =>
                setForm((current) => ({ ...current, confirm_password: event.target.value }))
              }
              required
              autoComplete="new-password"
            />
            <ProsohmButton
              type="submit"
              buttonVariant="primary"
              size="large"
              loading={submitting}
              fullWidth
            >
              Update Password
            </ProsohmButton>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
}
