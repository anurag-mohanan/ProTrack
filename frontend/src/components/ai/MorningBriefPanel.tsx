import { Grid, Stack, Typography } from '@mui/material';
import type { MorningBrief } from '../../types/Ai';
import { DashboardPanel } from '../ui/design-system/DashboardPanel';
import { designTokens } from '../../theme/designTokens';

interface MorningBriefPanelProps {
  brief: MorningBrief | undefined;
}

function BriefStat({ label, value, accent }: { label: string; value: string | number; accent?: string }) {
  return (
    <Stack spacing={0.25}>
      <Typography variant="h5" sx={{ fontWeight: 800, color: accent ?? 'text.primary', lineHeight: 1.1 }}>
        {value}
      </Typography>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
    </Stack>
  );
}

export function MorningBriefPanel({ brief }: MorningBriefPanelProps) {
  if (!brief) return null;

  return (
    <DashboardPanel title={brief.greeting} subtitle="Your daily engineering operations summary">
      <Grid container spacing={2}>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <BriefStat label="Active Projects" value={brief.active_projects} />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <BriefStat label="Due This Week" value={brief.due_this_week} accent={designTokens.semantic.warning} />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <BriefStat
            label="High Risk"
            value={brief.high_risk_projects}
            accent={brief.high_risk_projects ? designTokens.semantic.warning : undefined}
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <BriefStat label="Engineers Available" value={brief.engineers_available} />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <BriefStat label="Utilization" value={`${brief.utilization_percent}%`} />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <BriefStat
            label="Missing Timesheets"
            value={brief.missing_timesheets}
            accent={brief.missing_timesheets ? designTokens.semantic.warning : undefined}
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <BriefStat label="Over Budget" value={brief.over_budget_projects} />
        </Grid>
        <Grid size={{ xs: 6, sm: 4, md: 2 }}>
          <BriefStat label="Late Milestones" value={brief.late_milestones} />
        </Grid>
      </Grid>
    </DashboardPanel>
  );
}
