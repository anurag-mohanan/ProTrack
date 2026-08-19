import { Chip } from '@mui/material';
import BeachAccessRoundedIcon from '@mui/icons-material/BeachAccessRounded';
import type { TimesheetEntry } from '../../types';
import { designTokens } from '../../theme/designTokens';

const NP_CATEGORY_STYLES: Record<string, { bg: string; color: string; label: string }> = {
  leave: { bg: designTokens.semantic.primarySoft, color: designTokens.semantic.primary, label: 'Leave' },
  training: { bg: '#f0fdf4', color: designTokens.semantic.success, label: 'Training' },
  idle: { bg: designTokens.semantic.neutralSoft, color: designTokens.semantic.neutral, label: 'Idle Time' },
  meeting: { bg: '#eef2ff', color: '#6366f1', label: 'Meeting' },
  administration: { bg: designTokens.semantic.warningSoft, color: designTokens.semantic.warning, label: 'Administration' },
  downtime: { bg: designTokens.semantic.dangerSoft, color: designTokens.semantic.danger, label: 'Downtime' },
};

function inferNpCategory(entry: TimesheetEntry): string {
  if ((entry.leave_count ?? 0) > 0 || entry.non_productive_category === 'leave') {
    return 'leave';
  }
  const text = `${entry.non_productive_description ?? ''} ${entry.non_productive_code ?? ''}`.toLowerCase();
  if (text.includes('train')) return 'training';
  if (text.includes('idle')) return 'idle';
  if (text.includes('meet')) return 'meeting';
  if (text.includes('admin')) return 'administration';
  if (text.includes('down')) return 'downtime';
  return 'idle';
}

function BadgeShell({ label, bg, color, icon }: { label: string; bg: string; color: string; icon?: React.ReactNode }) {
  return (
    <Chip
      size="small"
      icon={icon as React.ReactElement | undefined}
      label={label}
      sx={{
        fontWeight: 700,
        fontSize: '0.6875rem',
        bgcolor: bg,
        color,
        '& .MuiChip-icon': { color },
      }}
    />
  );
}

export function BillableBadge({ billable }: { billable: boolean }) {
  return billable ? (
    <BadgeShell label="Billable" bg={designTokens.semantic.successSoft} color={designTokens.semantic.success} />
  ) : (
    <BadgeShell label="Non-Billable" bg={designTokens.semantic.neutralSoft} color={designTokens.semantic.neutral} />
  );
}

export function TimesheetWorkCategoryBadge({ entry }: { entry: TimesheetEntry }) {
  if (entry.post_completion_type) {
    const labels: Record<string, string> = {
      additional_work: 'Additional Work',
      rework: 'Rework',
      customer_change: 'Customer Change',
      internal_correction: 'Internal Correction',
    };
    return (
      <BadgeShell
        label={labels[entry.post_completion_type] ?? 'Post-Completion'}
        bg="#fff7ed"
        color="#c2410c"
      />
    );
  }
  if (entry.work_category === 'non_productive') {
    const category = inferNpCategory(entry);
    const style = NP_CATEGORY_STYLES[category] ?? NP_CATEGORY_STYLES.idle;
    if (category === 'leave') {
      return (
        <BadgeShell
          label="Leave"
          bg={style.bg}
          color={style.color}
          icon={<BeachAccessRoundedIcon sx={{ fontSize: '14px !important' }} />}
        />
      );
    }
    return <BadgeShell label={style.label} bg={style.bg} color={style.color} />;
  }
  return <BillableBadge billable={entry.is_billable} />;
}

export function TimesheetToolCell({ entry }: { entry: TimesheetEntry }) {
  if (entry.post_completion_type) {
    return (
      <span>
        {entry.project_tool_number || '—'}
        {' '}
        <BadgeShell label="Project Completed" bg="#fff7ed" color="#c2410c" />
      </span>
    );
  }
  if (entry.work_category === 'non_productive') {
    const isLeave = (entry.leave_count ?? 0) > 0 || entry.non_productive_category === 'leave';
    if (isLeave) {
      return (
        <BadgeShell
          label="Leave"
          bg={designTokens.semantic.primarySoft}
          color={designTokens.semantic.primary}
          icon={<BeachAccessRoundedIcon sx={{ fontSize: '14px !important' }} />}
        />
      );
    }
    return <span>{entry.non_productive_code || '—'}</span>;
  }
  return <span>{entry.project_tool_number || '—'}</span>;
}
