import { Fragment, useState } from 'react';
import {
  Box,
  Button,
  Collapse,
  IconButton,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import ExpandLessRoundedIcon from '@mui/icons-material/ExpandLessRounded';
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';
import type { SkExperienceProject, SkLevel, SkRecord } from '../../types/Skills';
import { formatDate, formatDateTime, formatNumber } from '../../utils/format';
import { FilterSelect } from '../ui/design-system/FilterSelect';
import { levelText } from './skillFormat';
import { StateChip } from './skillUi';

const ACTION_LABELS: Record<string, string> = {
  declared: 'Declared',
  redeclared: 'Declared again',
  claim_updated: 'Claim updated',
  submitted: 'Submitted for verification',
  verified: 'Verified',
  rejected: 'Not confirmed',
  reassessment_requested: 'Reassessment requested',
  archived: 'Archived',
  legacy_recorded: 'Recorded (legacy settings)',
  legacy_updated: 'Updated (legacy settings)',
};

interface Props {
  records: SkRecord[];
  levels: SkLevel[];
  isSelf: boolean;
  canReview: boolean;
  /** Projects the viewer may cite as evidence for this person. */
  evidenceProjects?: SkExperienceProject[];
  busy?: boolean;
  onSubmit?: (record: SkRecord) => void;
  onArchive?: (record: SkRecord) => void;
  onAssess?: (record: SkRecord) => void;
  onAddEvidence?: (record: SkRecord, projectId: string, note: string | null) => void;
  onRemoveEvidence?: (evidenceId: string) => void;
}

export function SkillRecordList({
  records,
  levels,
  isSelf,
  canReview,
  evidenceProjects = [],
  busy,
  onSubmit,
  onArchive,
  onAssess,
  onAddEvidence,
  onRemoveEvidence,
}: Props) {
  const [open, setOpen] = useState<string | null>(null);
  const [evidenceProject, setEvidenceProject] = useState('');
  const [evidenceNote, setEvidenceNote] = useState('');

  if (!records.length) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
        No skills recorded. A missing record means the skill is unknown, not that the person lacks it.
      </Typography>
    );
  }

  return (
    <Table size="small">
      <TableHead>
        <TableRow>
          <TableCell />
          <TableCell>Skill</TableCell>
          <TableCell>Status</TableCell>
          <TableCell>Claimed</TableCell>
          <TableCell>Verified</TableCell>
          <TableCell>Last verified</TableCell>
          <TableCell>Experience</TableCell>
          <TableCell align="right">Actions</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {records.map((r) => {
          const expanded = open === r.id;
          const canEditEvidence = (isSelf || canReview) && r.state !== 'archived';
          const cited = new Set(r.evidence.map((e) => e.project_id));
          return (
            <Fragment key={r.id}>
              <TableRow hover sx={{ '& > td': { borderBottom: expanded ? 'none' : undefined } }}>
                <TableCell padding="checkbox">
                  <IconButton size="small" onClick={() => setOpen(expanded ? null : r.id)} aria-label="Show details">
                    {expanded ? <ExpandLessRoundedIcon fontSize="small" /> : <ExpandMoreRoundedIcon fontSize="small" />}
                  </IconButton>
                </TableCell>
                <TableCell>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {r.skill_name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {[r.category, r.origin_label, r.skill_is_active ? null : 'inactive skill'].filter(Boolean).join(' · ')}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Stack spacing={0.5} sx={{ alignItems: 'flex-start' }}>
                    <StateChip state={r.state} label={r.state_label} />
                    {r.claim_pending ? (
                      <Typography variant="caption" color="info.main">
                        New claim awaiting review
                      </Typography>
                    ) : null}
                  </Stack>
                </TableCell>
                <TableCell>{levelText(levels, r.declared_level)}</TableCell>
                <TableCell>
                  {levelText(levels, r.verified_level)}
                  {r.verification_method_label ? (
                    <Typography variant="caption" color="text.secondary" component="div">
                      {r.verification_method_label}
                    </Typography>
                  ) : null}
                </TableCell>
                <TableCell>
                  {r.verified_at ? formatDate(r.verified_at) : '—'}
                  {r.verified_by_name ? (
                    <Typography variant="caption" color="text.secondary" component="div">
                      by {r.verified_by_name}
                    </Typography>
                  ) : null}
                </TableCell>
                <TableCell>
                  {r.years_experience !== null ? `${formatNumber(r.years_experience, 1)} yr` : '—'}
                  {r.last_used_on ? (
                    <Typography variant="caption" color="text.secondary" component="div">
                      last used {formatDate(r.last_used_on)}
                    </Typography>
                  ) : null}
                </TableCell>
                <TableCell align="right">
                  <Stack direction="row" spacing={0.5} sx={{ justifyContent: 'flex-end' }}>
                    {isSelf && onSubmit && (r.status === 'self_declared' || r.status === 'rejected') ? (
                      <Button size="small" disabled={busy} onClick={() => onSubmit(r)}>
                        Submit
                      </Button>
                    ) : null}
                    {canReview && onAssess && r.state !== 'archived' ? (
                      <Button size="small" variant="outlined" disabled={busy} onClick={() => onAssess(r)}>
                        Assess
                      </Button>
                    ) : null}
                    {onArchive && r.state !== 'archived' && (canReview || (isSelf && r.verified_level === null)) ? (
                      <Button size="small" color="inherit" disabled={busy} onClick={() => onArchive(r)}>
                        Archive
                      </Button>
                    ) : null}
                  </Stack>
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell colSpan={8} sx={{ py: 0 }}>
                  <Collapse in={expanded} unmountOnExit>
                    <Stack spacing={2} sx={{ py: 2 }}>
                      {r.employee_note ? <Detail label="Employee note" value={r.employee_note} /> : null}
                      {r.assessment_feedback ? <Detail label="Reviewer feedback" value={r.assessment_feedback} /> : null}
                      {r.confidential_notes ? <Detail label="Confidential reviewer note" value={r.confidential_notes} /> : null}
                      {r.confidential_hidden ? (
                        <Typography variant="caption" color="text.secondary">
                          A confidential reviewer note exists and is visible to authorised reviewers only.
                        </Typography>
                      ) : null}
                      {r.legacy_proficiency && r.origin === 'legacy' ? (
                        <Detail label="Legacy proficiency (not verified)" value={r.legacy_proficiency} />
                      ) : null}

                      <Box>
                        <Typography variant="subtitle2" gutterBottom>
                          Project evidence
                        </Typography>
                        {r.evidence.length ? (
                          <Stack spacing={0.5}>
                            {r.evidence.map((e) => (
                              <Stack key={e.id} direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                                <Typography variant="body2">
                                  {e.visible
                                    ? `${e.tool_number}${e.part_description ? ` — ${e.part_description}` : ''}${
                                        e.hours_total !== null ? ` · ${formatNumber(e.hours_total, 1)} h booked` : ''
                                      }${e.note ? ` · ${e.note}` : ''}`
                                    : 'A project you do not have access to'}
                                </Typography>
                                {canEditEvidence && onRemoveEvidence ? (
                                  <Tooltip title="Remove evidence">
                                    <IconButton size="small" onClick={() => onRemoveEvidence(e.id)} disabled={busy}>
                                      <DeleteOutlineRoundedIcon fontSize="small" />
                                    </IconButton>
                                  </Tooltip>
                                ) : null}
                              </Stack>
                            ))}
                          </Stack>
                        ) : (
                          <Typography variant="body2" color="text.secondary">
                            None cited. Evidence supports a review; it never verifies a skill by itself.
                          </Typography>
                        )}
                        {canEditEvidence && onAddEvidence && evidenceProjects.length ? (
                          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ mt: 1, maxWidth: 720 }}>
                            <FilterSelect
                              label="Cite a project"
                              value={evidenceProject}
                              onChange={(e) => setEvidenceProject(e.target.value)}
                            >
                              <MenuItem value="">Select a project</MenuItem>
                              {evidenceProjects
                                .filter((p) => !cited.has(p.project_id))
                                .map((p) => (
                                  <MenuItem key={p.project_id} value={p.project_id}>
                                    {p.tool_number}
                                    {p.part_description ? ` — ${p.part_description}` : ''}
                                  </MenuItem>
                                ))}
                            </FilterSelect>
                            <TextField
                              size="small"
                              label="Note"
                              value={evidenceNote}
                              onChange={(e) => setEvidenceNote(e.target.value)}
                              fullWidth
                            />
                            <Button
                              variant="outlined"
                              size="small"
                              disabled={!evidenceProject || busy}
                              onClick={() => {
                                onAddEvidence(r, evidenceProject, evidenceNote.trim() || null);
                                setEvidenceProject('');
                                setEvidenceNote('');
                              }}
                            >
                              Add
                            </Button>
                          </Stack>
                        ) : null}
                      </Box>

                      <Box>
                        <Typography variant="subtitle2" gutterBottom>
                          History
                        </Typography>
                        <Stack spacing={0.75}>
                          {r.history.map((e) => (
                            <Box key={e.id}>
                              <Typography variant="body2">
                                <strong>{ACTION_LABELS[e.action] ?? e.action}</strong>
                                {e.actor_name ? ` by ${e.actor_name}` : ''} · {formatDateTime(e.occurred_at)}
                                {e.to_verified_level !== e.from_verified_level && e.to_verified_level
                                  ? ` · verified ${levelText(levels, e.to_verified_level)}`
                                  : ''}
                                {e.to_declared_level !== e.from_declared_level && e.to_declared_level
                                  ? ` · claim ${levelText(levels, e.to_declared_level)}`
                                  : ''}
                              </Typography>
                              {[e.detail, e.feedback, e.confidential_note ? `Confidential: ${e.confidential_note}` : null]
                                .filter(Boolean)
                                .map((line) => (
                                  <Typography key={line} variant="caption" color="text.secondary" component="div">
                                    {line}
                                  </Typography>
                                ))}
                            </Box>
                          ))}
                        </Stack>
                      </Box>
                    </Stack>
                  </Collapse>
                </TableCell>
              </TableRow>
            </Fragment>
          );
        })}
      </TableBody>
    </Table>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
        {value}
      </Typography>
    </Box>
  );
}
