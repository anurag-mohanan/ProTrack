import { useQuery } from '@tanstack/react-query';
import { Box, Chip, Stack, Typography } from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { ContentCard } from '../../components/ui/cards';
import { LoadingState } from '../../components/common/LoadingState';
import { fetchSecurityPolicy } from '../../api/system';

export default function SecuritySettingsPage() {
  const query = useQuery({ queryKey: ['system', 'security-policy'], queryFn: fetchSecurityPolicy });

  if (query.isLoading) return <LoadingState message="Loading security settings…" />;

  return (
    <Box>
      <PageHeader title="Security" subtitle="Authentication and password policy" />
      <Stack spacing={2}>
        <ContentCard title="Password policy">
          <Typography variant="body1">{query.data?.password_requirements}</Typography>
        </ContentCard>
        <ContentCard title="Session policy">
          <Typography variant="body1">
            Session timeout: {query.data?.session_timeout_minutes} minutes
          </Typography>
          <Chip
            label={query.data?.internal_release_mode ? 'Internal release mode' : 'Production mode'}
            size="small"
            sx={{ mt: 1 }}
          />
        </ContentCard>
      </Stack>
    </Box>
  );
}
