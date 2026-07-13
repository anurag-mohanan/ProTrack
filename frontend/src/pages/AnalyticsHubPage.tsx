import { Card, CardContent, Link, Stack, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { Link as RouterLink } from 'react-router-dom';
import { api } from '../api/client';
import { PageHeader } from '../components/common/PageHeader';
import { LoadingState } from '../components/common/LoadingState';

export function AnalyticsHubPage() {
  const query = useQuery({
    queryKey: ['analytics-catalog'],
    queryFn: async () => (await api.get('/analytics/catalog')).data,
  });

  if (query.isLoading) return <LoadingState message="Loading analytics catalog…" />;

  return (
    <Stack spacing={2}>
      <PageHeader
        title="Reports & Analytics"
        subtitle="Cross-module report catalog. Each report is gated by its source module permissions."
      />
      {(query.data?.categories ?? []).map(
        (category: {
          category: string;
          items: Array<{ title: string; path: string }>;
        }) => (
          <Card key={category.category} variant="outlined">
            <CardContent>
              <Typography variant="h6" sx={{ mb: 1 }}>
                {category.category}
              </Typography>
              <Stack spacing={0.75}>
                {category.items.map((item) => (
                  <Link key={`${category.category}-${item.title}`} component={RouterLink} to={item.path}>
                    {item.title}
                  </Link>
                ))}
              </Stack>
            </CardContent>
          </Card>
        ),
      )}
      {!query.data?.categories?.length ? (
        <Typography color="text.secondary">No report categories available for your permissions.</Typography>
      ) : null}
    </Stack>
  );
}

export default AnalyticsHubPage;
