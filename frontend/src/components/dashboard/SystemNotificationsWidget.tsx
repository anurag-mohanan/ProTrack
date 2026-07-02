import { useMemo } from 'react';
import type { DashboardActivityItem } from '../../types';
import { RecentActivityWidget } from './RecentActivityWidget';

interface SystemNotificationsWidgetProps {
  activities: DashboardActivityItem[];
}

export function SystemNotificationsWidget({ activities }: SystemNotificationsWidgetProps) {
  const systemActivities = useMemo(
    () =>
      activities.filter((activity) =>
        ['user', 'import'].includes(activity.category),
      ),
    [activities],
  );

  return <RecentActivityWidget activities={systemActivities} />;
}
