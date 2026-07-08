import { useMemo } from 'react';
import { Box, Chip, Stack, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { PageHeader } from '../components/common/PageHeader';
import { LoadingState } from '../components/common/LoadingState';
import { fetchEngineeringCalendar, type CalendarEvent } from '../api/calendar';
import { formatDisplayValue } from '../utils/format';

const CATEGORY_LABELS: Record<string, string> = {
  milestone_due: 'Milestone due',
  milestone_overdue: 'Overdue',
  milestone_completed: 'Completed',
  holiday: 'Holiday',
  customer_delivery: 'Customer delivery',
  leave: 'Leave',
  timesheet_deadline: 'Timesheet deadline',
};

export default function EngineeringCalendarPage() {
  const query = useQuery({
    queryKey: ['engineering-calendar'],
    queryFn: fetchEngineeringCalendar,
  });

  const grouped = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>();
    for (const event of query.data ?? []) {
      const list = map.get(event.date) ?? [];
      list.push(event);
      map.set(event.date, list);
    }
    return [...map.entries()];
  }, [query.data]);

  if (query.isLoading) return <LoadingState message="Loading engineering calendar…" />;

  return (
    <Box>
      <PageHeader title="Engineering Calendar" subtitle="Milestones, deliveries, leave, holidays, and timesheet deadlines" />
      <Stack spacing={2}>
        {grouped.map(([day, events]) => (
          <Box key={day} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2, p: 2 }}>
            <Typography variant="subtitle1" sx={{ mb: 1 }}>
              {formatDisplayValue(day)}
            </Typography>
            <Stack spacing={1}>
              {events.map((event) => (
                <Box key={event.id} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Chip size="small" label={CATEGORY_LABELS[event.category] ?? event.category} />
                  <Typography variant="body2">{event.title}</Typography>
                </Box>
              ))}
            </Stack>
          </Box>
        ))}
      </Stack>
    </Box>
  );
}
