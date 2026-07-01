import { Box, Card, CardContent, Typography } from '@mui/material';

interface SystemSettingsPageProps {
  embedded?: boolean;
}

export default function SystemSettingsPage({ embedded = false }: SystemSettingsPageProps) {
  const body = (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {embedded ? 'Configuration' : 'System settings coming soon.'}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Global configuration options will be available here in a future release.
        </Typography>
      </CardContent>
    </Card>
  );

  if (embedded) {
    return body;
  }

  return (
    <Box>
      <Typography variant="sectionTitle" sx={{ mb: 2, display: 'block' }}>
        Current settings
      </Typography>
      {body}
    </Box>
  );
}
