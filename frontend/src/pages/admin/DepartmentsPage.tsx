import { useQuery } from '@tanstack/react-query';
import { Box, Chip, Table, TableBody, TableCell, TableHead, TableRow } from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { ContentCard } from '../../components/ui/cards';
import { LoadingState } from '../../components/common/LoadingState';
import { fetchDepartments } from '../../api/settings';
import { formatCellValue } from '../../utils/format';

export default function DepartmentsPage() {
  const query = useQuery({
    queryKey: ['settings', 'departments'],
    queryFn: fetchDepartments,
  });

  if (query.isLoading) return <LoadingState message="Loading departments…" />;

  return (
    <Box>
      <PageHeader title="Departments" subtitle="Organisation structure for users and reporting" />
      <ContentCard title="Departments">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>Code</TableCell>
              <TableCell>Status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(query.data ?? []).map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.name}</TableCell>
                <TableCell>{formatCellValue(row.code)}</TableCell>
                <TableCell>
                  <Chip
                    size="small"
                    label={row.is_active ? 'Active' : 'Inactive'}
                    color={row.is_active ? 'success' : 'default'}
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </ContentCard>
    </Box>
  );
}
