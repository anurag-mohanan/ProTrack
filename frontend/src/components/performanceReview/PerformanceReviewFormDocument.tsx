import type { ReactNode, RefObject } from 'react';
import {
  Box,
  Button,
  Chip,
  Divider,
  Grid,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import PictureAsPdfOutlinedIcon from '@mui/icons-material/PictureAsPdfOutlined';
import { useCompany } from '../../context/CompanyContext';
import { resolveLogoUrl } from '../../config/env';
import { PerformanceReviewRatingPicker } from './PerformanceReviewRatingPicker';
import { PerformanceReviewProjectsPanel, type ReviewProjectRow } from './PerformanceReviewProjectsPanel';
import type { RatingScaleItem } from './performanceReviewConstants';
import { formatScore, ratingLabelForValue } from './performanceReviewConstants';

export type ReviewFormSection = {
  id?: string;
  title: string;
  description?: string | null;
  employee_notes?: string | null;
  reviewer_notes?: string | null;
  employee_notes_label?: string | null;
  average_score?: number | string | null;
  sort_order: number;
  items: Array<{
    id?: string;
    prompt: string;
    guidance?: string | null;
    rating?: number | string | null;
    employee_comment?: string | null;
    manager_comment?: string | null;
    sort_order: number;
  }>;
};

export type ReviewFormModel = {
  id: string;
  employee_name: string;
  employee_department?: string | null;
  employee_designation?: string | null;
  employee_role?: string | null;
  employee_joining_date?: string | null;
  employee_first_job_date?: string | null;
  company_experience?: string | null;
  reviewer_name: string;
  team_name?: string | null;
  period_label: string;
  status: string;
  review_date?: string | null;
  review_period_start?: string | null;
  review_period_end?: string | null;
  total_experience?: string | null;
  industry_experience?: string | null;
  overall_score?: number | string | null;
  overall_score_label?: string | null;
  employee_summary?: string | null;
  manager_summary?: string | null;
  strengths_summary?: string | null;
  improvement_summary?: string | null;
  career_goals?: string | null;
  sections: ReviewFormSection[];
  projects?: ReviewProjectRow[];
};

type EditorState = {
  period_label: string;
  review_date: string;
  due_date: string;
  total_experience: string;
  industry_experience: string;
  overall_score: string;
  employee_summary: string;
  manager_summary: string;
  strengths_summary: string;
  improvement_summary: string;
  career_goals: string;
  sections: ReviewFormSection[];
  projects: ReviewProjectRow[];
};

function cloneSections(sections: ReviewFormSection[]): ReviewFormSection[] {
  return sections.map((section) => ({
    ...section,
    items: section.items.map((item) => ({ ...item })),
  }));
}

type PerformanceReviewFormDocumentProps = {
  review: ReviewFormModel;
  editor: EditorState;
  ratingScale: RatingScaleItem[];
  canManage: boolean;
  formRef: RefObject<HTMLDivElement | null>;
  onChange: (next: EditorState) => void;
  actions?: ReactNode;
};

export function PerformanceReviewFormDocument({
  review,
  editor,
  ratingScale,
  canManage,
  formRef,
  onChange,
  actions,
}: PerformanceReviewFormDocumentProps) {
  const { company, appName } = useCompany();
  const logoUrl = resolveLogoUrl(company?.logo_url, company?.logo_url ?? undefined);

  const setField = (field: keyof EditorState, value: string) =>
    onChange({ ...editor, [field]: value });

  const handleExport = () => {
    window.print();
  };

  return (
    <Box>
      <Stack
        direction="row"
        spacing={1}
        className="no-print"
        sx={{ mb: 1.5, justifyContent: 'flex-end', flexWrap: 'wrap' }}
      >
        <Button
          variant="outlined"
          size="small"
          startIcon={<PictureAsPdfOutlinedIcon />}
          onClick={handleExport}
        >
          Export / Print PDF
        </Button>
        {actions}
      </Stack>

      <Box
        ref={formRef}
        className="performance-review-print-root"
        sx={{
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 1.5,
          bgcolor: 'background.paper',
          p: { xs: 1.5, md: 2 },
          maxWidth: 920,
          mx: 'auto',
        }}
      >
        <Stack direction="row" spacing={2} sx={{ alignItems: 'center', mb: 1.5 }}>
          {logoUrl ? (
            <Box
              component="img"
              src={logoUrl}
              alt={company?.company_name || appName}
              sx={{ height: 48, maxWidth: 140, objectFit: 'contain' }}
            />
          ) : (
            <Box
              sx={{
                height: 48,
                minWidth: 110,
                borderRadius: 1,
                bgcolor: 'grey.100',
                display: 'grid',
                placeItems: 'center',
                px: 1,
              }}
            >
              <Typography sx={{ fontWeight: 800, fontSize: 12 }}>
                {company?.company_short_name || company?.company_name || appName}
              </Typography>
            </Box>
          )}
          <Box sx={{ flex: 1, textAlign: 'center' }}>
            <Typography
              sx={{
                fontWeight: 900,
                letterSpacing: '0.08em',
                fontSize: { xs: 18, md: 22 },
                textTransform: 'uppercase',
              }}
            >
              Performance Review
            </Typography>
            <Typography variant="caption" color="text.secondary">
              PP-HRD-FO-20 · {review.period_label}
            </Typography>
          </Box>
          <Chip size="small" label={review.status} className="no-print" />
        </Stack>

        <Divider sx={{ mb: 1.5 }} />

        <Grid container spacing={1} sx={{ mb: 1.5 }}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Typography variant="caption" color="text.secondary">
              Employee Name
            </Typography>
            <Typography sx={{ fontWeight: 700, fontSize: 13 }}>{review.employee_name}</Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Typography variant="caption" color="text.secondary">
              Designation
            </Typography>
            <Typography sx={{ fontWeight: 700, fontSize: 13 }}>
              {review.employee_designation || review.employee_role || '—'}
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Typography variant="caption" color="text.secondary">
              Department / Team
            </Typography>
            <Typography sx={{ fontWeight: 700, fontSize: 13 }}>
              {review.employee_department || review.team_name || '—'}
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Typography variant="caption" color="text.secondary">
              Exp. in company
            </Typography>
            <Typography sx={{ fontWeight: 700, fontSize: 13 }}>
              {editor.total_experience || review.company_experience || '—'}
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
              From user joining date
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Typography variant="caption" color="text.secondary">
              Exp. in industry
            </Typography>
            <Typography sx={{ fontWeight: 700, fontSize: 13 }}>
              {editor.industry_experience || '—'}
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
              From first job date
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Typography variant="caption" color="text.secondary">
              Reviewer
            </Typography>
            <Typography sx={{ fontWeight: 700, fontSize: 13 }}>{review.reviewer_name}</Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <TextField
              fullWidth
              size="small"
              type="date"
              label="Review date"
              value={editor.review_date}
              onChange={(e) => setField('review_date', e.target.value)}
              disabled={!canManage}
              slotProps={{ inputLabel: { shrink: true } }}
            />
          </Grid>
        </Grid>

        <Box
          sx={{
            display: 'flex',
            gap: 1,
            flexWrap: 'wrap',
            mb: 1,
            p: 0.75,
            bgcolor: 'grey.100',
            borderRadius: 1,
          }}
        >
          {ratingScale.map((row) => (
            <Typography key={row.value} sx={{ fontSize: 11, fontWeight: 600 }}>
              {row.label}={row.short_label}
            </Typography>
          ))}
        </Box>

        {editor.sections.map((section, sectionIndex) => (
          <Box key={section.id ?? section.title} sx={{ mb: 1.5 }}>
            <Box
              sx={{
                px: 1,
                py: 0.6,
                bgcolor: 'grey.900',
                color: 'common.white',
                fontWeight: 800,
                fontSize: 12,
                letterSpacing: '0.04em',
                textTransform: 'uppercase',
                display: 'flex',
                justifyContent: 'space-between',
              }}
            >
              <span>{section.title}</span>
              <span>Avg {formatScore(section.average_score)}</span>
            </Box>
            <Stack spacing={0.75} sx={{ border: '1px solid', borderColor: 'divider', borderTop: 0, p: 1 }}>
              {section.items.map((item, itemIndex) => (
                <Box
                  key={item.id ?? `${item.prompt}-${itemIndex}`}
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: { xs: '1fr', md: '180px 1fr' },
                    gap: 1,
                    alignItems: 'center',
                    py: 0.5,
                    borderBottom: '1px solid',
                    borderColor: 'divider',
                    '&:last-of-type': { borderBottom: 0 },
                  }}
                >
                  <Box>
                    <Typography sx={{ fontWeight: 700, fontSize: 12 }}>{item.prompt}</Typography>
                    {item.guidance ? (
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                        {item.guidance}
                      </Typography>
                    ) : null}
                  </Box>
                  <PerformanceReviewRatingPicker
                    value={item.rating}
                    disabled={!canManage}
                    scale={ratingScale}
                    onChange={(next) => {
                      const sections = cloneSections(editor.sections);
                      sections[sectionIndex].items[itemIndex].rating = next;
                      onChange({ ...editor, sections });
                    }}
                  />
                </Box>
              ))}
              <TextField
                fullWidth
                size="small"
                multiline
                minRows={2}
                label={section.employee_notes_label || 'Notes'}
                value={section.employee_notes ?? ''}
                onChange={(e) => {
                  const sections = cloneSections(editor.sections);
                  sections[sectionIndex].employee_notes = e.target.value;
                  onChange({ ...editor, sections });
                }}
              />
            </Stack>
          </Box>
        ))}

        <PerformanceReviewProjectsPanel
          projects={editor.projects}
          periodStart={review.review_period_start}
          periodEnd={review.review_period_end}
          canManage={canManage}
          onChange={(projects) => onChange({ ...editor, projects })}
        />

        <Grid container spacing={1.25} sx={{ mt: 1.5 }}>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              fullWidth
              size="small"
              multiline
              minRows={2}
              label="Employee comments"
              value={editor.employee_summary}
              onChange={(e) => setField('employee_summary', e.target.value)}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              fullWidth
              size="small"
              multiline
              minRows={2}
              label="Reviewer comments"
              value={editor.manager_summary}
              onChange={(e) => setField('manager_summary', e.target.value)}
              disabled={!canManage}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              fullWidth
              size="small"
              multiline
              minRows={2}
              label="Targets / Goals for upcoming year"
              value={editor.career_goals}
              onChange={(e) => setField('career_goals', e.target.value)}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <Box sx={{ p: 1.25, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
              <Typography variant="caption" color="text.secondary">
                Overall score
              </Typography>
              <Typography sx={{ fontWeight: 900, fontSize: 22 }}>
                {formatScore(review.overall_score)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {review.overall_score_label ||
                  ratingLabelForValue(review.overall_score, ratingScale) ||
                  '—'}
              </Typography>
            </Box>
          </Grid>
        </Grid>

        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: 'block', mt: 1.5, textAlign: 'right' }}
        >
          Form PP-HRD-FO-20 · Single-page annual review
        </Typography>
      </Box>

      <style>{`
        @media print {
          body * { visibility: hidden !important; }
          .performance-review-print-root,
          .performance-review-print-root * { visibility: visible !important; }
          .performance-review-print-root {
            position: absolute !important;
            left: 0 !important;
            top: 0 !important;
            width: 100% !important;
            max-width: 100% !important;
            border: none !important;
            box-shadow: none !important;
            margin: 0 !important;
            padding: 8mm !important;
          }
          .no-print { display: none !important; }
          @page { size: A4; margin: 8mm; }
        }
      `}</style>
    </Box>
  );
}
