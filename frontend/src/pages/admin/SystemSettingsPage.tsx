import { Box, Card, CardContent, Typography } from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';

export default function SystemSettingsPage() {
  return (
    <Box>
      <PageHeader
        title="System Settings"
        subtitle="Configure global application settings"
      />

      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            System settings coming soon.
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Global configuration options will be available here in a future release.
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
}
