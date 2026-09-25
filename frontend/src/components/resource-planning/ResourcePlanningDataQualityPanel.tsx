import { useMemo, useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Chip,
  Stack,
  Typography,
} from '@mui/material';
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import FactCheckRoundedIcon from '@mui/icons-material/FactCheckRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import ErrorOutlineRoundedIcon from '@mui/icons-material/ErrorOutlineRounded';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link as RouterLink } from 'react-router-dom';
import {
  fetchResourceDataQuality,
  resourcePlanningQueryKeys,
  type DataQualityIssue,
  type DataQualityReport,
} from '../../api/resourcePlanning';
import { getErrorMessage } from '../../api/client';
import { itOperationsKeys, reconcileOrphanAssignedComputers } from '../../api/itOperations';
import { LoadingState } from '../common/LoadingState';
import { ErrorState } from '../common/ErrorState';
import { DashboardPanel, KpiMetricCard } from '../ui/design-system';
import { KpiStrip } from '../analytics/KpiStrip';
import { ProsohmButton } from '../ui/ProsohmButton';
import { QUERY_STALE_TIMES } from '../../config/queryConfig';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { accessContextFromUser, canManageItAssets } from '../../utils/permissions';

type Props = {
  /** When true, show repair actions that need manage_it_assets. */
  showRepairs?: boolean;
};

function severityIcon(severity: string) {
  if (severity === 'error') return ErrorOutlineRoundedIcon;
  if (severity === 'warning') return WarningAmberRoundedIcon;
  return InfoOutlinedIcon;
}

function severityIconColor(
  severity: string,
): 'error' | 'warning' | 'info' | 'inherit' {
  if (severity === 'error') return 'error';
  if (severity === 'warning') return 'warning';
  if (severity === 'info') return 'info';
  return 'inherit';
}

function severityChipColor(severity: string): 'error' | 'warning' | 'info' | 'default' {
  if (severity === 'error') return 'error';
  if (severity === 'warning') return 'warning';
  if (severity === 'info') return 'info';
  return 'default';
}

function sampleLabel(sample: Record<string, unknown>): string {
  const name =
    sample.computer_name ||
    sample.user_name ||
    sample.full_name ||
    sample.software_name ||
    sample.asset_number ||
    sample.address ||
    sample.hostname;
  if (typeof name === 'string' && name.trim()) return name;
  return String(sample.detail || sample.code || 'Item');
}

function IssueAccordion({ issue }: { issue: DataQualityIssue }) {
  const Icon = severityIcon(issue.severity);
  return (
    <Accordion disableGutters elevation={0} sx={{ border: 1, borderColor: 'divider', borderRadius: 1, '&:before': { display: 'none' } }}>
      <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
        <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center', width: '100%', pr: 1 }}>
          <Icon color={severityIconColor(issue.severity)} fontSize="small" />
          <Typography sx={{ fontWeight: 600, flex: 1 }}>{issue.title}</Typography>
          <Chip size="small" label={issue.count} color={severityChipColor(issue.severity)} />
          <Chip size="small" label={issue.domain} variant="outlined" />
        </Stack>
      </AccordionSummary>
      <AccordionDetails>
        {issue.samples.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            Count only — open the related IT module to review records.
          </Typography>
        ) : (
          <Stack spacing={0.75}>
            {issue.samples.slice(0, 20).map((sample, index) => {
              const href = typeof sample.href === 'string' ? sample.href : null;
              const label = `${sampleLabel(sample)}${
                sample.detail ? ` — ${String(sample.detail)}` : ''
              }${
                sample.field && sample.value
                  ? ` — duplicate ${String(sample.field).replace('_', ' ')} ${String(sample.value)}`
                  : ''
              }${
                sample.seat_shortfall != null
                  ? ` (shortfall ${String(sample.seat_shortfall)})`
                  : ''
              }`;
              return href ? (
                <Typography
                  key={`${issue.code}-${index}`}
                  variant="body2"
                  component={RouterLink}
                  to={href}
                  sx={{ color: 'primary.main', textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}
                >
                  {label}
                </Typography>
              ) : (
                <Typography key={`${issue.code}-${index}`} variant="body2" color="text.secondary">
                  {label}
                </Typography>
              );
            })}
            {issue.samples.length > 20 ? (
              <Typography variant="caption" color="text.secondary">
                +{issue.samples.length - 20} more in API sample
              </Typography>
            ) : null}
          </Stack>
        )}
      </AccordionDetails>
    </Accordion>
  );
}

export function ResourcePlanningDataQualityPanel({ showRepairs = true }: Props) {
  const { user } = useAuth();
  const access = accessContextFromUser(user);
  const canRepair = canManageItAssets(access);
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [domainFilter, setDomainFilter] = useState<string>('all');

  const query = useQuery({
    queryKey: resourcePlanningQueryKeys.dataQuality(),
    queryFn: fetchResourceDataQuality,
    staleTime: QUERY_STALE_TIMES.dashboard,
  });

  const repairMutation = useMutation({
    mutationFn: reconcileOrphanAssignedComputers,
    onSuccess: (data) => {
      showSuccess(
        data.repaired_count
          ? `Repaired ${data.repaired_count} orphan assigned status(es).`
          : 'No orphan assigned statuses found.',
      );
      void queryClient.invalidateQueries({ queryKey: resourcePlanningQueryKeys.dataQuality() });
      void queryClient.invalidateQueries({ queryKey: itOperationsKeys.all });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const report: DataQualityReport | undefined = query.data;
  const openIssues = useMemo(() => {
    const rows = report?.open_issues ?? [];
    if (domainFilter === 'all') return rows;
    return rows.filter((row) => row.domain === domainFilter);
  }, [report, domainFilter]);

  const domains = useMemo(() => {
    const set = new Set((report?.issues ?? []).map((row) => row.domain));
    return ['all', ...Array.from(set).sort()];
  }, [report]);

  if (query.isLoading) return <LoadingState message="Loading data quality…" />;
  if (query.error) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  if (!report) return null;

  const orphanRepair = (report.repairs ?? []).find((row) => row.code === 'repair_orphan_assigned');

  return (
    <Stack spacing={2}>
      <Alert severity={report.totals.error > 0 ? 'warning' : 'info'} icon={<FactCheckRoundedIcon />}>
        Inventory integrity check — missing links are flagged for review. Nothing is invented or
        auto-linked.
      </Alert>

      <KpiStrip columns={4}>
        <KpiMetricCard
          compact
          title="Open issue types"
          value={String(report.totals.issue_types)}
          icon={FactCheckRoundedIcon}
          accent={report.totals.issue_types > 0 ? 'warning' : 'success'}
        />
        <KpiMetricCard
          compact
          title="Errors"
          value={String(report.totals.error)}
          icon={ErrorOutlineRoundedIcon}
          accent={report.totals.error > 0 ? 'error' : 'success'}
        />
        <KpiMetricCard
          compact
          title="Warnings"
          value={String(report.totals.warning)}
          icon={WarningAmberRoundedIcon}
          accent={report.totals.warning > 0 ? 'warning' : 'success'}
        />
        <KpiMetricCard
          compact
          title="Computers scanned"
          value={String(report.totals.computers_total)}
          icon={InfoOutlinedIcon}
          accent="primary"
        />
      </KpiStrip>

      {showRepairs && canRepair && orphanRepair?.available ? (
        <DashboardPanel
          title="Safe repairs"
          subtitle="Only confident status consistency fixes — no invented assignees"
        >
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ alignItems: 'flex-start' }}>
            <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
              Reset computers marked Assigned with no open employee assignment → Available.
            </Typography>
            <ProsohmButton
              buttonVariant="primary"
              loading={repairMutation.isPending}
              onClick={() => repairMutation.mutate()}
            >
              Fix orphan assigned
            </ProsohmButton>
          </Stack>
        </DashboardPanel>
      ) : null}

      <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
        {domains.map((domain) => (
          <Chip
            key={domain}
            label={domain === 'all' ? 'All domains' : domain}
            color={domainFilter === domain ? 'primary' : 'default'}
            variant={domainFilter === domain ? 'filled' : 'outlined'}
            onClick={() => setDomainFilter(domain)}
          />
        ))}
      </Stack>

      <DashboardPanel
        title="Open issues"
        subtitle={
          openIssues.length
            ? `${openIssues.length} issue type(s) need review`
            : 'No open integrity issues for this filter'
        }
      >
        {openIssues.length === 0 ? (
          <Typography color="text.secondary">All clear for the selected domain.</Typography>
        ) : (
          <Stack spacing={1}>
            {openIssues.map((issue) => (
              <IssueAccordion key={issue.code} issue={issue} />
            ))}
          </Stack>
        )}
      </DashboardPanel>

      <Box>
        <Typography variant="caption" color="text.secondary">
          Generated {report.generated_at}
        </Typography>
      </Box>
    </Stack>
  );
}
