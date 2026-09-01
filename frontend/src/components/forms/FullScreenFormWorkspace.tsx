import type { ReactNode } from 'react';
import {
  Box,
  Breadcrumbs,
  Chip,
  IconButton,
  LinearProgress,
  Link,
  Paper,
  Stack,
  Typography,
  alpha,
} from '@mui/material';
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded';
import CheckCircleOutlineRoundedIcon from '@mui/icons-material/CheckCircleOutlineRounded';
import RadioButtonUncheckedRoundedIcon from '@mui/icons-material/RadioButtonUncheckedRounded';
import { useTheme } from '@mui/material/styles';
import { designTokens } from '../../theme/designTokens';
import { UnsavedChangesBar } from '../common/UnsavedChangesBar';
import { APP_TOP_BAR_OFFSET } from '../ui/design-system/StickyRecordHeader';

export type FormWorkspaceSection = {
  id: string;
  label: string;
  complete?: boolean;
};

export type FormWorkspaceBreadcrumb = {
  label: string;
  onClick?: () => void;
};

interface FullScreenFormWorkspaceProps {
  title: string;
  subject?: string;
  year?: number | string;
  statusLabel?: string;
  statusColor?: 'default' | 'primary' | 'success' | 'warning' | 'error' | 'info';
  readOnly?: boolean;
  progressPercent?: number;
  progressDetail?: string;
  lastSavedLabel?: string;
  breadcrumbs?: FormWorkspaceBreadcrumb[];
  sections?: FormWorkspaceSection[];
  activeSectionId?: string;
  onSectionSelect?: (sectionId: string) => void;
  onBack: () => void;
  backLabel?: string;
  headerActions?: ReactNode;
  footerActions?: ReactNode;
  children: ReactNode;
  dirty?: boolean;
  saving?: boolean;
  onSave?: () => void;
  onDiscard?: () => void;
  saveLabel?: string;
  completionFooter?: ReactNode;
}

export function FullScreenFormWorkspace({
  title,
  subject,
  year,
  statusLabel,
  statusColor = 'default',
  readOnly = false,
  progressPercent,
  progressDetail,
  lastSavedLabel,
  breadcrumbs,
  sections,
  activeSectionId,
  onSectionSelect,
  onBack,
  backLabel = 'Back',
  headerActions,
  footerActions,
  children,
  dirty = false,
  saving = false,
  onSave,
  onDiscard,
  saveLabel = 'Save draft',
  completionFooter,
}: FullScreenFormWorkspaceProps) {
  const theme = useTheme();

  return (
    <Box
      className="form-workspace-root"
      sx={{
        minHeight: `calc(100vh - ${APP_TOP_BAR_OFFSET}px)`,
        display: 'flex',
        flexDirection: 'column',
        mx: { xs: -1, sm: 0 },
      }}
    >
      <Paper
        elevation={0}
        sx={{
          position: 'sticky',
          top: APP_TOP_BAR_OFFSET,
          zIndex: 4,
          borderRadius: 0,
          borderBottom: 1,
          borderColor: 'divider',
          bgcolor: 'background.paper',
          px: { xs: 1.5, md: 2.5 },
          py: 1.5,
        }}
      >
        <Stack spacing={1}>
          {breadcrumbs && breadcrumbs.length > 0 ? (
            <Breadcrumbs sx={{ fontSize: 12 }}>
              {breadcrumbs.map((crumb, index) =>
                crumb.onClick ? (
                  <Link
                    key={`${crumb.label}-${index}`}
                    component="button"
                    variant="body2"
                    underline="hover"
                    onClick={crumb.onClick}
                    sx={{ cursor: 'pointer' }}
                  >
                    {crumb.label}
                  </Link>
                ) : (
                  <Typography key={`${crumb.label}-${index}`} variant="body2" color="text.secondary">
                    {crumb.label}
                  </Typography>
                ),
              )}
            </Breadcrumbs>
          ) : null}

          <Stack
            direction={{ xs: 'column', md: 'row' }}
            spacing={1.5}
            sx={{ alignItems: { md: 'center' }, justifyContent: 'space-between' }}
          >
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center', minWidth: 0, flex: 1 }}>
              <IconButton size="small" onClick={onBack} aria-label={backLabel}>
                <ArrowBackRoundedIcon />
              </IconButton>
              <Box sx={{ minWidth: 0 }}>
                <Typography variant="h6" sx={{ fontWeight: 800, lineHeight: 1.2 }} noWrap>
                  {title}
                </Typography>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                  {subject ? (
                    <Typography variant="body2" color="text.secondary" noWrap>
                      {subject}
                    </Typography>
                  ) : null}
                  {year ? (
                    <Chip size="small" label={year} variant="outlined" sx={{ height: 22 }} />
                  ) : null}
                  {statusLabel ? (
                    <Chip size="small" label={statusLabel} color={statusColor} variant="outlined" />
                  ) : null}
                  {readOnly ? (
                    <Chip size="small" label="Read only" variant="outlined" sx={{ height: 22 }} />
                  ) : (
                    <Chip size="small" label="Editable" color="primary" variant="outlined" sx={{ height: 22 }} />
                  )}
                </Stack>
              </Box>
            </Stack>

            <Stack
              direction="row"
              spacing={1}
              sx={{ alignItems: 'center', flexWrap: 'wrap', justifyContent: { xs: 'flex-start', md: 'flex-end' } }}
            >
              {lastSavedLabel ? (
                <Typography variant="caption" color="text.secondary">{lastSavedLabel}</Typography>
              ) : null}
              {headerActions}
            </Stack>
          </Stack>

          {progressPercent !== undefined ? (
            <Box>
              <Stack direction="row" sx={{ justifyContent: 'space-between', mb: 0.5 }}>
                <Typography variant="caption" sx={{ fontWeight: 600 }}>
                  {progressPercent}% complete
                </Typography>
                {progressDetail ? (
                  <Typography variant="caption" color="text.secondary">{progressDetail}</Typography>
                ) : null}
              </Stack>
              <LinearProgress
                variant="determinate"
                value={progressPercent}
                sx={{ height: 6, borderRadius: 99 }}
              />
            </Box>
          ) : null}
        </Stack>
      </Paper>

      <Box sx={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {sections && sections.length > 0 ? (
          <Paper
            elevation={0}
            className="no-print"
            sx={{
              width: { xs: 0, md: 240 },
              flexShrink: 0,
              display: { xs: 'none', md: 'block' },
              borderRight: 1,
              borderColor: 'divider',
              bgcolor: alpha(theme.palette.background.default, 0.6),
              p: 2,
            }}
          >
            <Typography
              variant="overline"
              sx={{ display: 'block', mb: 1.5, color: 'text.secondary', letterSpacing: 1.1 }}
            >
              Form sections
            </Typography>
            <Stack spacing={0.5}>
              {sections.map((section) => {
                const active = section.id === activeSectionId;
                return (
                  <Box
                    key={section.id}
                    component="button"
                    type="button"
                    onClick={() => onSectionSelect?.(section.id)}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                      width: '100%',
                      textAlign: 'left',
                      border: 0,
                      borderRadius: `${designTokens.radius.md}px`,
                      px: 1.25,
                      py: 0.85,
                      cursor: 'pointer',
                      bgcolor: active ? alpha(theme.palette.primary.main, 0.1) : 'transparent',
                      color: active ? 'primary.main' : 'text.primary',
                      '&:hover': {
                        bgcolor: active
                          ? alpha(theme.palette.primary.main, 0.12)
                          : alpha(theme.palette.action.hover, 0.08),
                      },
                    }}
                  >
                    {section.complete ? (
                      <CheckCircleOutlineRoundedIcon sx={{ fontSize: 18, color: 'success.main' }} />
                    ) : (
                      <RadioButtonUncheckedRoundedIcon sx={{ fontSize: 18, color: 'text.disabled' }} />
                    )}
                    <Typography variant="body2" sx={{ fontWeight: active ? 700 : 500 }}>
                      {section.label}
                    </Typography>
                  </Box>
                );
              })}
            </Stack>
          </Paper>
        ) : null}

        <Box sx={{ flex: 1, minWidth: 0, overflow: 'auto' }}>
          <Box sx={{ px: { xs: 1.5, md: 3 }, py: 2.5, maxWidth: 1200 }}>
            {children}
            {completionFooter ? (
              <Paper
                variant="outlined"
                sx={{ mt: 3, p: 2, borderRadius: 2, bgcolor: alpha(theme.palette.warning.main, 0.04) }}
              >
                {completionFooter}
              </Paper>
            ) : null}
          </Box>
        </Box>
      </Box>

      {footerActions ? (
        <Paper
          elevation={0}
          className="no-print"
          sx={{
            position: 'sticky',
            bottom: 0,
            zIndex: 3,
            borderTop: 1,
            borderColor: 'divider',
            px: { xs: 1.5, md: 2.5 },
            py: 1.25,
            bgcolor: 'background.paper',
          }}
        >
          <Stack direction="row" spacing={1} sx={{ justifyContent: 'flex-end', flexWrap: 'wrap' }}>
            {footerActions}
          </Stack>
        </Paper>
      ) : null}

      {onSave && onDiscard ? (
        <UnsavedChangesBar
          visible={dirty}
          onSave={onSave}
          onDiscard={onDiscard}
          saving={saving}
          saveLabel={saveLabel}
          inset
        />
      ) : null}
    </Box>
  );
}
