import { Box, Button } from '@mui/material';
import { Link } from 'react-router-dom';
import { PageHeader } from '../components/common/PageHeader';

export function NotFoundPage() {
  return (
    <Box>
      <PageHeader
        title="Page not found"
        subtitle="The page you requested does not exist or you do not have access."
      />
      <Button component={Link} to="/dashboard" variant="contained">
        Go to Dashboard
      </Button>
    </Box>
  );
}
