import { Chip, Stack } from '@mui/material';
import ViewModuleRoundedIcon from '@mui/icons-material/ViewModuleRounded';
import { useWidgetLayout } from '../../hooks/useWidgetLayout';

export function useDashboardWidgets(storageKey: string, widgetIds: string[]) {
  return useWidgetLayout(storageKey, widgetIds);
}

interface DashboardWidgetToolbarProps {
  storageKey: string;
  widgets: Array<{ id: string; label: string }>;
}

export function DashboardWidgetToolbar({ storageKey, widgets }: DashboardWidgetToolbarProps) {
  const { widgets: layout, toggle } = useWidgetLayout(
    storageKey,
    widgets.map((w) => w.id),
  );

  return (
    <Stack direction="row" spacing={1} sx={{ mb: 2, alignItems: 'center', flexWrap: 'wrap' }}>
      <ViewModuleRoundedIcon fontSize="small" color="action" />
      {widgets.map((widget) => {
        const item = layout.find((w) => w.id === widget.id);
        const visible = item?.visible ?? true;
        return (
          <Chip
            key={widget.id}
            size="small"
            label={widget.label}
            color={visible ? 'primary' : 'default'}
            variant={visible ? 'filled' : 'outlined'}
            onClick={() => toggle(widget.id)}
          />
        );
      })}
    </Stack>
  );
}
