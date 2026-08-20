import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ContentCard } from '../../components/ui/cards';
import { Box, Typography } from '@mui/material';

/** Lightweight placeholders for IT areas scaffolding ownership/migration work. */
export function ITModulePlaceholderPage({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <PageContainer>
      <PageHeader title={title} subtitle={description} />
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
