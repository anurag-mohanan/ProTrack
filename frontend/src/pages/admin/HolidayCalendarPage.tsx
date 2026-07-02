import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Box,
  FormControlLabel,
  IconButton,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import { useState } from 'react';
import { PageHeader } from '../../components/common/PageHeader';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { LoadingState } from '../../components/common/LoadingState';
import { createHoliday, deleteHoliday, fetchHolidays } from '../../api/settings';
import { useToast } from '../../context/ToastContext';
import { formatDisplayValue } from '../../utils/format';
import type { Holiday } from '../../types/Settings';

export default function HolidayCalendarPage() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ['settings', 'holidays'], queryFn: fetchHolidays });
  const [name, setName] = useState('');
  const [holidayDate, setHolidayDate] = useState('');
  const [region, setRegion] = useState('');
  const [isRecurring, setIsRecurring] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Holiday | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      createHoliday({
        name,
        holiday_date: holidayDate,
        region: region || null,
        is_working_day: false,
        is_recurring: isRecurring,
      }),
    onSuccess: () => {
      showSuccess('Holiday added');
      setName('');
      setHolidayDate('');
      void queryClient.invalidateQueries({ queryKey: ['settings', 'holidays'] });
    },
    onError: (error) => showError(String(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteHoliday,
    onSuccess: () => {
      showSuccess('Holiday deleted');
      setDeleteTarget(null);
      void queryClient.invalidateQueries({ queryKey: ['settings', 'holidays'] });
    },
    onError: (error) => showError(String(error)),
  });

  if (query.isLoading) return <LoadingState message="Loading holidays…" />;

  return (
    <Box>
      <PageHeader title="Holiday Calendar" subtitle="Non-working days used for availability planning" />
      <ContentCard title="Add holiday">
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr 1fr auto' }, gap: 2 }}>
          <TextField label="Holiday" value={name} onChange={(e) => setName(e.target.value)} />
          <TextField
            label="Date"
            type="date"
            slotProps={{ inputLabel: { shrink: true } }}
            value={holidayDate}
            onChange={(e) => setHolidayDate(e.target.value)}
          />
          <TextField label="Region" value={region} onChange={(e) => setRegion(e.target.value)} />
          <FormControlLabel
            control={<Switch checked={isRecurring} onChange={(e) => setIsRecurring(e.target.checked)} />}
            label="Recurring"
          />
        </Box>
        <Box sx={{ mt: 2 }}>
          <ProsohmButton
            buttonVariant="primary"
            startIcon={<AddIcon />}
            onClick={() => createMutation.mutate()}
            loading={createMutation.isPending}
          >
            Add Holiday
          </ProsohmButton>
        </Box>
      </ContentCard>

      <Box sx={{ mt: 3 }}>
      <ContentCard title="Holidays">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Holiday</TableCell>
              <TableCell>Date</TableCell>
              <TableCell>Region</TableCell>
              <TableCell>Recurring</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(query.data ?? []).map((row) => (
              <TableRow key={row.id}>
                <TableCell>{formatDisplayValue(row.name)}</TableCell>
                <TableCell>{formatDisplayValue(row.holiday_date)}</TableCell>
                <TableCell>{formatDisplayValue(row.region)}</TableCell>
                <TableCell>{row.is_recurring ? 'Yes' : 'No'}</TableCell>
                <TableCell align="right">
                  <IconButton
                    size="small"
                    color="error"
                    aria-label={`Delete ${row.name}`}
                    onClick={() => setDeleteTarget(row)}
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </ContentCard>
      </Box>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete Holiday"
        recordName={deleteTarget?.name}
        message="This holiday will be permanently removed from the calendar."
        confirmLabel="Delete"
        danger
        loading={deleteMutation.isPending}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
      />
    </Box>
  );
}
