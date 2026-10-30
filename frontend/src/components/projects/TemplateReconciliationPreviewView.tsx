import type { ReactNode } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Checkbox,
  Chip,
  FormControlLabel,
  MenuItem,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import type {
  ExistingAction,
  ExistingDecision,
  MatchClassification,
  ReconExistingItem,
  TemplateDecision,
  TemplateReconciliationPreview,
} from '../../services/templateReconciliationService';

const ACTION_LABELS: Record<ExistingAction, string> = {
  retain: 'Keep',
  supersede: 'Supersede',
  archive: 'Archive',
  merge: 'Merge into…',
};

const CLASS_COLORS: Record<MatchClassification, 'success' | 'info' | 'warning' | 'default'> = {
  confirmed: 'success',
  likely: 'info',
  possible: 'warning',
  different: 'default',
};

function formatStatus(value: string | null | undefined): string {
  if (!value) return '—';
  return value.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
}

function formatHours(value: string | number | null | undefined): string {
  const n = Number(value ?? 0);
  return Number.isFinite(n) ? `${n.toFixed(1)} h` : '—';
}

function Section({
  letter,
  title,
  count,
  defaultExpanded,
  children,
}: {
  letter: string;
  title: string;
  count: number;
  defaultExpanded?: boolean;
  children: ReactNode;
}) {
  return (
    <Accordion defaultExpanded={defaultExpanded} disableGutters variant="outlined">
      <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
        <Typography variant="subtitle2">
          {letter}. {title}
        </Typography>
        <Chip size="small" label={count} sx={{ ml: 1 }} />
      </AccordionSummary>
      <AccordionDetails sx={{ display: 'flex', flexDirection: 'column', gap: 1.25 }}>
        {count === 0 ? (
          <Typography variant="body2" color="text.secondary">
            Nothing in this section.
          </Typography>
        ) : (
          children
        )}
      </AccordionDetails>
    </Accordion>
  );
}

function Row({ children }: { children: ReactNode }) {
  return (
    <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1.25 }}>{children}</Box>
  );
}

interface Props {
  preview: TemplateReconciliationPreview;
  disabled?: boolean;
  applyTemplateHours: boolean;
  scheduleNew: boolean;
  onTemplateDecision: (decision: TemplateDecision) => void;
  onExistingDecision: (decision: ExistingDecision) => void;
  onApplyTemplateHours: (value: boolean) => void;
  onScheduleNew: (value: boolean) => void;
}

export function TemplateReconciliationPreviewView({
  preview,
  disabled,
  applyTemplateHours,
  scheduleNew,
  onTemplateDecision,
  onExistingDecision,
  onApplyTemplateHours,
  onScheduleNew,
}: Props) {
  const existingById = new Map(preview.existing.map((e) => [e.id, e]));
  const retained = preview.existing.filter(
    (e) => e.decision === 'retain' && ['completed', 'in_progress'].includes(e.status),
  );
  const counts = preview.counts;

  const mergeTargets = (item: ReconExistingItem) =>
    preview.existing.filter(
      (t) =>
        t.id !== item.id &&
        t.decision === 'retain' &&
        (item.status !== 'completed' || t.status === 'completed'),
    );

  const chooseExisting = (item: ReconExistingItem, action: ExistingAction) => {
    if (action === 'merge') {
      const targets = mergeTargets(item);
      const preferred = targets.find((t) => t.in_new_template) ?? targets[0];
      if (!preferred) return;
      onExistingDecision({ milestone_id: item.id, action, merge_into_id: preferred.id });
      return;
    }
    onExistingDecision({ milestone_id: item.id, action });
  };

  return (
    <Stack spacing={1.5}>
      <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
        <Chip size="small" color="primary" label={`${counts.add} to add`} />
        <Chip size="small" label={`${counts.match} matched`} />
        <Chip size="small" label={`${counts.retain} kept`} />
        {counts.merge ? <Chip size="small" color="warning" label={`${counts.merge} to merge`} /> : null}
        {counts.supersede ? (
          <Chip size="small" color="warning" label={`${counts.supersede} to supersede`} />
        ) : null}
        {counts.archive ? <Chip size="small" color="warning" label={`${counts.archive} to archive`} /> : null}
        {counts.needs_review ? (
          <Chip size="small" color="error" variant="outlined" label={`${counts.needs_review} need your review`} />
        ) : null}
      </Stack>

      {preview.blockers.map((b) => (
        <Alert key={b} severity="error" sx={{ py: 0.25 }}>
          {b}
        </Alert>
      ))}
      {preview.warnings.map((w) => (
        <Alert key={w} severity="warning" sx={{ py: 0.25 }}>
          {w}
        </Alert>
      ))}
      {preview.same_template ? (
        <Alert severity="info" sx={{ py: 0.25 }}>
          This is the project's current template. Applying it adds any milestones that are missing and relinks matches.
        </Alert>
      ) : null}

      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
        <FormControlLabel
          control={
            <Checkbox
              size="small"
              checked={scheduleNew}
              disabled={disabled}
              onChange={(e) => onScheduleNew(e.target.checked)}
            />
          }
          label={<Typography variant="body2">Set due dates on new milestones from template offsets</Typography>}
        />
        <FormControlLabel
          control={
            <Checkbox
              size="small"
              checked={applyTemplateHours}
              disabled={disabled}
              onChange={(e) => onApplyTemplateHours(e.target.checked)}
            />
          }
          label={<Typography variant="body2">Use template hour estimates on new milestones</Typography>}
        />
      </Stack>
      <Typography variant="body2" color="text.secondary">
        Planned hours: {formatHours(preview.planned_hours.before)} → {formatHours(preview.planned_hours.after)}
        {preview.planned_hours.uses_stage_estimates ? ' (stage estimates stay in charge of staged work)' : ''}
      </Typography>

      <Section letter="A" title="Completed and in-progress work kept" count={retained.length} defaultExpanded>
        {retained.map((m) => (
          <Row key={m.id}>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              {m.name}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {formatStatus(m.status)}
              {m.completed_date ? ` on ${m.completed_date}` : ''} · {formatHours(m.actual_hours)} booked
              {m.assigned_user_name ? ` · ${m.assigned_user_name}` : ''} · status, dates, hours and history stay as
              they are
            </Typography>
          </Row>
        ))}
      </Section>

      <Section
        letter="B"
        title="Template milestones matched to existing work"
        count={preview.matches.filter((m) => m.candidates.length > 0).length}
        defaultExpanded={preview.matches.some((m) => m.needs_review)}
      >
        {preview.matches
          .filter((m) => m.candidates.length > 0)
          .map((item) => {
            const confirmed = item.candidates.some((c) => !c.requires_confirmation);
            const value = item.decision === 'match' && item.milestone ? item.milestone.id : 'add';
            return (
              <Row key={item.template_milestone_id}>
                <Stack direction="row" spacing={1} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {item.template_name}
                  </Typography>
                  {item.classification ? (
                    <Chip
                      size="small"
                      color={CLASS_COLORS[item.classification]}
                      label={formatStatus(item.classification)}
                    />
                  ) : null}
                  {item.needs_review ? <Chip size="small" color="error" variant="outlined" label="Choose" /> : null}
                  {item.completion_retained ? <Chip size="small" color="success" variant="outlined" label="Completion kept" /> : null}
                </Stack>
                {confirmed ? (
                  <Typography variant="caption" color="text.secondary" component="div">
                    Matched to “{item.milestone?.name}” ({formatStatus(item.milestone?.status)}): {item.reasons.join('; ')}
                  </Typography>
                ) : (
                  <TextField
                    select
                    size="small"
                    fullWidth
                    sx={{ mt: 1 }}
                    label="Use for this template milestone"
                    value={value}
                    disabled={disabled}
                    onChange={(e) =>
                      onTemplateDecision(
                        e.target.value === 'add'
                          ? { template_milestone_id: item.template_milestone_id, action: 'add' }
                          : {
                              template_milestone_id: item.template_milestone_id,
                              action: 'match',
                              milestone_id: e.target.value,
                            },
                      )
                    }
                  >
                    <MenuItem value="add">Add as a new milestone</MenuItem>
                    {item.candidates.map((c) => (
                      <MenuItem key={c.milestone_id} value={c.milestone_id}>
                        Existing “{c.milestone_name}” · {c.classification_label} · {formatStatus(c.milestone_status)}
                      </MenuItem>
                    ))}
                  </TextField>
                )}
                {!confirmed && item.candidates.length ? (
                  <Typography variant="caption" color="text.secondary" component="div">
                    {item.candidates.map((c) => `${c.milestone_name}: ${c.reasons.join('; ')}`).join(' · ')}
                  </Typography>
                ) : null}
                {item.attribute_changes.map((change) => (
                  <Typography key={change} variant="caption" color="text.secondary" component="div">
                    {change}
                  </Typography>
                ))}
              </Row>
            );
          })}
      </Section>

      <Section letter="C" title="New milestones to add" count={preview.new_milestones.length} defaultExpanded>
        {preview.new_milestones.map((m) => (
          <Row key={m.template_milestone_id}>
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {m.name}
              </Typography>
              {m.is_required ? <Chip size="small" variant="outlined" label="Required" /> : null}
              <Typography variant="caption" color="text.secondary">
                position {m.sort_position}
              </Typography>
            </Stack>
            <Typography variant="caption" color="text.secondary" component="div">
              Due: {m.due_date ?? 'unscheduled'} ({m.due_date_rule}) · Owner: {m.assigned_user_name ?? 'unassigned'} (
              {m.assignment_rule}) · Planned {formatHours(m.planned_hours)}
              {m.depends_on_names.length ? ` · After ${m.depends_on_names.join(', ')}` : ''}
            </Typography>
          </Row>
        ))}
      </Section>

      <Section
        letter="D"
        title="Possible duplicates"
        count={preview.duplicates.length}
        defaultExpanded={preview.duplicates.length > 0}
      >
        {preview.duplicates.map((d) => {
          const current = existingById.get(d.milestone.id);
          const merging = current?.decision === 'merge';
          const canMerge = d.merge_allowed && Boolean(current?.allowed_actions.includes('merge'));
          return (
            <Row key={d.milestone.id}>
              <Stack direction="row" spacing={1} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  “{d.milestone.name}” ({formatStatus(d.milestone.status)}) and “{d.canonical.name}” (
                  {formatStatus(d.canonical.status)})
                </Typography>
                <Chip size="small" color={CLASS_COLORS[d.classification]} label={d.classification_label} />
              </Stack>
              <Typography variant="caption" color="text.secondary" component="div">
                {d.reasons.join('; ')}
              </Typography>
              <ToggleButtonGroup
                size="small"
                exclusive
                sx={{ mt: 1 }}
                value={merging ? 'merge' : 'retain'}
                disabled={disabled}
                onChange={(_e, next: 'merge' | 'retain' | null) => {
                  if (!next) return;
                  onExistingDecision(
                    next === 'merge'
                      ? { milestone_id: d.milestone.id, action: 'merge', merge_into_id: d.canonical.id }
                      : { milestone_id: d.milestone.id, action: 'retain' },
                  );
                }}
              >
                <ToggleButton value="retain">Keep both</ToggleButton>
                <ToggleButton value="merge" disabled={!canMerge}>
                  Merge into “{d.canonical.name}”
                </ToggleButton>
              </ToggleButtonGroup>
              {!d.merge_allowed ? (
                <Typography variant="caption" color="text.secondary" component="div">
                  A completed milestone is never merged into an incomplete one.
                </Typography>
              ) : null}
              {merging ? (
                <Typography variant="caption" color="text.secondary" component="div">
                  Preserved: {d.preserved.join(' ')}
                </Typography>
              ) : null}
            </Row>
          );
        })}
      </Section>

      <Section
        letter="E"
        title="Existing milestones not in the new template"
        count={preview.not_in_template.length}
        defaultExpanded={preview.not_in_template.length > 0}
      >
        <Typography variant="caption" color="text.secondary">
          These are kept unless you choose otherwise. Superseded, archived and merged milestones stay on record
          (history, hours, completion) but stop counting in progress and reports.
        </Typography>
        {preview.not_in_template.map((m) => {
          const targets = mergeTargets(m);
          return (
            <Row key={m.id}>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ alignItems: { sm: 'center' } }}>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {m.name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {formatStatus(m.status)}
                    {m.completed_date ? ` on ${m.completed_date}` : ''} · {formatHours(m.actual_hours)} booked
                  </Typography>
                </Box>
                <TextField
                  select
                  size="small"
                  sx={{ minWidth: 150 }}
                  value={m.decision}
                  disabled={disabled}
                  onChange={(e) => chooseExisting(m, e.target.value as ExistingAction)}
                >
                  {m.allowed_actions.map((a) => (
                    <MenuItem key={a} value={a} disabled={a === 'merge' && targets.length === 0}>
                      {ACTION_LABELS[a]}
                    </MenuItem>
                  ))}
                </TextField>
                {m.decision === 'merge' ? (
                  <TextField
                    select
                    size="small"
                    sx={{ minWidth: 200 }}
                    label="Merge into"
                    value={m.merge_into_id ?? ''}
                    disabled={disabled}
                    onChange={(e) =>
                      onExistingDecision({ milestone_id: m.id, action: 'merge', merge_into_id: e.target.value })
                    }
                  >
                    {targets.map((t) => (
                      <MenuItem key={t.id} value={t.id}>
                        {t.name}
                      </MenuItem>
                    ))}
                  </TextField>
                ) : null}
              </Stack>
            </Row>
          );
        })}
      </Section>

      {preview.dependency_changes.length ? (
        <Accordion disableGutters variant="outlined">
          <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
            <Typography variant="subtitle2">Dependency changes</Typography>
            <Chip size="small" label={preview.dependency_changes.length} sx={{ ml: 1 }} />
          </AccordionSummary>
          <AccordionDetails>
            {preview.dependency_changes.map((c, i) => (
              <Typography key={`${c.milestone_name}-${i}`} variant="caption" component="div" color="text.secondary">
                {c.milestone_name}
                {c.depends_on_name ? ` → after ${c.depends_on_name}` : ''}: {c.detail}
              </Typography>
            ))}
          </AccordionDetails>
        </Accordion>
      ) : null}

      {counts.inactive_untouched ? (
        <Typography variant="caption" color="text.secondary">
          {counts.inactive_untouched} milestone(s) merged, superseded or archived by earlier changes are left untouched.
        </Typography>
      ) : null}
    </Stack>
  );
}
