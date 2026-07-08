import { useState } from 'react';
import { Stack, TextField } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { aiQueryKeys, searchKnowledgeBase } from '../api/ai';
import { PageContainer } from '../components/common/PageContainer';
import { ModernPageHeader } from '../components/ui/design-system';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';
import { OperationalDataTable, StickyHeaderCell, StickyTableCell } from '../components/ui/design-system';
import { TableRow } from '@mui/material';
import { formatCellValue, formatNumber } from '../utils/format';

export function KnowledgeBasePage() {
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');

  const kbQuery = useQuery({
    queryKey: aiQueryKeys.knowledge(search),
    queryFn: () => searchKnowledgeBase(search),
  });

  return (
    <PageContainer>
      <ModernPageHeader
        title="Engineering Knowledge Base"
        subtitle="Searchable history from completed projects"
      />
      <Stack spacing={2}>
        <TextField
          size="small"
          label="Search by tool, customer, type, or keyword"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') setSearch(query);
          }}
          sx={{ maxWidth: 480 }}
        />

        {kbQuery.isLoading ? <LoadingState /> : null}
        {kbQuery.error ? <ErrorState error={kbQuery.error} /> : null}

        {kbQuery.data ? (
          <OperationalDataTable
            maxHeight={560}
            head={
              <TableRow>
                <StickyHeaderCell>Tool</StickyHeaderCell>
                <StickyHeaderCell>Customer</StickyHeaderCell>
                <StickyHeaderCell>Type</StickyHeaderCell>
                <StickyHeaderCell>Designer</StickyHeaderCell>
                <StickyHeaderCell align="right">Quoted</StickyHeaderCell>
                <StickyHeaderCell align="right">Actual</StickyHeaderCell>
                <StickyHeaderCell align="right">Milestones</StickyHeaderCell>
                <StickyHeaderCell align="right">ECs</StickyHeaderCell>
              </TableRow>
            }
          >
            {kbQuery.data.map((row) => (
              <TableRow key={row.id}>
                <StickyTableCell pinned>{row.tool_number}</StickyTableCell>
                <StickyTableCell>{formatCellValue(row.customer_name)}</StickyTableCell>
                <StickyTableCell>{formatCellValue(row.project_type_name)}</StickyTableCell>
                <StickyTableCell>{formatCellValue(row.designer_name)}</StickyTableCell>
                <StickyTableCell align="right">{formatNumber(row.quoted_hours, 1)}</StickyTableCell>
                <StickyTableCell align="right">{formatNumber(row.actual_hours, 1)}</StickyTableCell>
                <StickyTableCell align="right">{row.milestone_count}</StickyTableCell>
                <StickyTableCell align="right">{row.engineering_change_count}</StickyTableCell>
              </TableRow>
            ))}
          </OperationalDataTable>
        ) : null}
      </Stack>
    </PageContainer>
  );
}
