import type { ReactNode } from 'react';
import { Box, Divider, Paper, Typography } from '@mui/material';
import { HealthChip, ExecutionStatusChip } from '../../common/StatusChip';
import type { ExecutionStatus, ProjectHealth } from '../../../types/common';
import { formatCellValue, formatDate, formatDisplayValue } from '../../../utils/format';

export const APP_TOP_BAR_OFFSET = 64;

interface StickyRecordHeaderProps {
  mode?: 'full' | 'draft';
  toolNumber?: string | null;
  partDescription?: string | null;
  customerName?: string | null;
  executionStatus?: ExecutionStatus | null;
  dueDate?: string | null;
  health?: ProjectHealth | null;
  /** Secondary line for non-project records (e.g. customer name, user name). */
  primaryLabel?: string;
  secondaryLabel?: string;
  meta?: ReactNode;
  stickyTop?: number | string;
  compact?: boolean;
}

export function StickyRecordHeader({
  mode = 'full',
  toolNumber,
  partDescription,
  customerName,
  executionStatus,
  dueDate,
  health,
  primaryLabel,
  secondaryLabel,
  meta,
  stickyTop = 0,
  compact = false,
}: StickyRecordHeaderProps) {
  const isDraft = mode === 'draft';
  const resolvedPrimary =
    primaryLabel ??
    (isDraft
      ? formatDisplayValue(toolNumber, 'Enter tool number…')
      : formatDisplayValue(toolNumber, 'Untitled project'));
  const resolvedSecondary =
    secondaryLabel ??
    (isDraft
      ? formatDisplayValue(partDescription, 'Part description will appear here')
      : formatDisplayValue(partDescription));

  return (
    <Paper
      elevation={0}
      sx={{
        position: 'sticky',
        top: stickyTop,
        zIndex: 3,
        mb: 2,
        px: compact ? 2 : 2.5,
        py: compact ? 1.25 : 1.5,
        borderRadius: 2.5,
        border: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
        boxShadow: (theme) => theme.palette.prosohm.shadowCard,
      }}
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75, minWidth: 0 }}>
        <Typography
          variant={compact ? 'subtitle1' : 'h6'}
          sx={{ fontWeight: 800, lineHeight: 1.2, letterSpacing: '-0.01em' }}
          noWrap
        >
          {resolvedPrimary}
        </Typography>
        {!primaryLabel ? (
          <Typography variant="body2" color="text.secondary" noWrap>
            {resolvedSecondary}
          </Typography>
        ) : secondaryLabel ? (
          <Typography variant="body2" color="text.secondary" noWrap>
            {secondaryLabel}
          </Typography>
        ) : null}

        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
            flexWrap: 'wrap',
            pt: 0.25,
          }}
        >
          {isDraft ? (
            <>
              <MetaItem label="Customer" value={formatDisplayValue(customerName, '—')} />
              <Divider flexItem orientation="vertical" sx={{ display: { xs: 'none', sm: 'block' } }} />
              <MetaItem
                label="Part"
                value={formatDisplayValue(partDescription, '—')}
                hideOnMobile
              />
            </>
          ) : (
            <>
              <MetaItem label="Customer" value={formatDisplayValue(customerName, '—')} />
              {executionStatus ? (
                <>
                  <Divider flexItem orientation="vertical" sx={{ display: { xs: 'none', sm: 'block' } }} />
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                      Status
                    </Typography>
                    <ExecutionStatusChip status={executionStatus} />
                  </Box>
                </>
              ) : null}
              <Divider flexItem orientation="vertical" sx={{ display: { xs: 'none', sm: 'block' } }} />
              <MetaItem label="Due" value={formatDate(dueDate) || '—'} />
              {health ? (
                <>
                  <Divider flexItem orientation="vertical" sx={{ display: { xs: 'none', sm: 'block' } }} />
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                      Health
                    </Typography>
                    <HealthChip health={health} />
                  </Box>
                </>
              ) : null}
            </>
          )}
          {meta}
        </Box>
      </Box>
    </Paper>
  );
}

function MetaItem({
  label,
  value,
  hideOnMobile = false,
}: {
  label: string;
  value: string;
  hideOnMobile?: boolean;
}) {
  return (
    <Box sx={{ display: hideOnMobile ? { xs: 'none', sm: 'flex' } : 'flex', alignItems: 'baseline', gap: 0.75 }}>
      <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
        {label}
      </Typography>
      <Typography variant="body2" sx={{ fontWeight: 600 }}>
        {formatCellValue(value)}
      </Typography>
    </Box>
  );
}
