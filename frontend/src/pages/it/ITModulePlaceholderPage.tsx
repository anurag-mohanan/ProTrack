import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ITSectionSubnav, IT_REQUEST_TABS } from '../../components/it/ITSectionSubnav';
import { ContentCard } from '../../components/ui/cards';
import { Box, Typography } from '@mui/material';
import { useSearchParams } from 'react-router-dom';

/** Lightweight placeholders for IT areas scaffolding ownership/migration work. */
export function ITModulePlaceholderPage({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  const [searchParams] = useSearchParams();
  const isRepairs = searchParams.get('tab') === 'repairs';
  const heading = isRepairs ? 'Repairs / Downtime' : title;
  const body = isRepairs
    ? 'Repair tickets and downtime will appear here. Until that workflow lands, use IT Requests and the asset maintenance status.'
    : description;

  return (
    <PageContainer>
      <PageHeader title={heading} subtitle={body} />
      <ITSectionSubnav items={IT_REQUEST_TABS} />
      <ContentCard>
        <Box sx={{ py: 3 }}>
          <Typography color="text.secondary">
            This area is scaffolded for the IT Operations expansion. Data model and permissions are
            in place; full workflows will land in a following phase.
          </Typography>
        </Box>
      </ContentCard>
    </PageContainer>
  );
}
