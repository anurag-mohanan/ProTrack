import { useMemo, useState } from 'react';
import {
  Box,
  Stack,
  Typography,
  alpha,
  useTheme,
} from '@mui/material';
import DashboardRoundedIcon from '@mui/icons-material/DashboardRounded';
import AssessmentRoundedIcon from '@mui/icons-material/AssessmentRounded';
import HubRoundedIcon from '@mui/icons-material/HubRounded';
import InsightsRoundedIcon from '@mui/icons-material/InsightsRounded';
import SettingsSuggestRoundedIcon from '@mui/icons-material/SettingsSuggestRounded';
import { useSearchParams } from 'react-router-dom';
import { PageHeader } from '../components/common/PageHeader';
import { TeamSkillMatrixPanel } from '../components/performance/TeamSkillMatrixPanel';
import { PerformanceDashboardPanel } from '../components/performance/PerformanceDashboardPanel';
import { PerformanceTemplatesCyclesPanel } from '../components/performance/PerformanceTemplatesCyclesPanel';
import { PerformanceAnalyticsPanel } from '../components/performance/PerformanceAnalyticsPanel';
import { PerformanceReviewsPage } from './PerformanceReviewsPage';
import { useAuth } from '../context/AuthContext';
import { hasRole, ROLES } from '../utils/permissions';

const SECTIONS = [
  { id: 'dashboard', label: 'Dashboard', blurb: 'Ratings, open reviews, skills & utilization', icon: DashboardRoundedIcon },
  { id: 'annual', label: 'Annual Reviews', blurb: 'Template-driven annual review workspace', icon: AssessmentRoundedIcon },
  { id: 'skills', label: 'Skills Matrix', blurb: 'Stream proficiency for allocation decisions', icon: HubRoundedIcon },
  { id: 'templates', label: 'Templates & Cycles', blurb: 'Review templates and cycle orchestration', icon: SettingsSuggestRoundedIcon },
  { id: 'analytics', label: 'Analytics', blurb: 'Progress, overdue, and rating mix', icon: InsightsRoundedIcon },
] as const;

type SectionId = (typeof SECTIONS)[number]['id'];

function sectionFromSearch(value: string | null): SectionId {
  if (value === 'reviews' || value === 'history' || value === 'quarterly') return 'annual';
  if (value === 'skills') return 'skills';
  if (SECTIONS.some((row) => row.id === value)) return value as SectionId;
  return 'dashboard';
}

export function PerformancePage() {
  const theme = useTheme();
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [section, setSection] = useState<SectionId>(() =>
    sectionFromSearch(searchParams.get('section') || searchParams.get('tab')),
  );

  const canManage = useMemo(() => {
    const role = user?.role_name ?? '';
    return hasRole(
      role,
      ROLES.ADMIN,
      ROLES.ENGINEERING_MANAGER,
      ROLES.DESIGN_LEADER,
      ROLES.HR,
      ROLES.OFFICE_ADMINISTRATOR,
    );
  }, [user?.role_name]);

  const setSectionAndUrl = (next: SectionId) => {
    setSection(next);
    setSearchParams({ section: next });
  };

  const active = SECTIONS.find((row) => row.id === section) ?? SECTIONS[0];

  return (
    <Box>
      <PageHeader subtitle="Capability, reviews, and allocation intelligence — skills feed project staffing decisions." />

      <Box
        sx={{
          mb: 2.5,
          p: { xs: 2, md: 2.5 },
          borderRadius: 3,
          background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.08)} 0%, ${alpha(
            theme.palette.info.main,
            0.06,
          )} 55%, ${alpha(theme.palette.background.paper, 0.9)} 100%)`,
          border: 1,
          borderColor: 'divider',
        }}
      >
        <Typography variant="h4" sx={{ fontWeight: 800, letterSpacing: -0.4, mb: 0.5 }}>
          Performance
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 720 }}>
          Annual reviews, skills matrix, and analytics in one place. Skill ratings inform
          project assignment when complexity and proficiency do not align.
        </Typography>
      </Box>

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: '240px 1fr' },
          gap: 2,
          alignItems: 'start',
        }}
      >
        <Stack
          spacing={0.75}
          sx={{
            p: 1,
            borderRadius: 3,
            bgcolor: 'background.paper',
            border: 1,
            borderColor: 'divider',
            position: { md: 'sticky' },
            top: { md: 88 },
          }}
        >
          {SECTIONS.map((row) => {
            const Icon = row.icon;
            const selected = row.id === section;
            return (
              <Box
                key={row.id}
                component="button"
                type="button"
                onClick={() => setSectionAndUrl(row.id)}
                sx={{
                  textAlign: 'left',
                  border: 0,
                  cursor: 'pointer',
                  borderRadius: 2,
                  px: 1.25,
                  py: 1.1,
                  bgcolor: selected ? alpha(theme.palette.primary.main, 0.12) : 'transparent',
                  color: selected ? 'primary.main' : 'text.primary',
                  transition: 'background-color 160ms ease, color 160ms ease',
                  '&:hover': {
                    bgcolor: selected
                      ? alpha(theme.palette.primary.main, 0.16)
                      : alpha(theme.palette.action.hover, 0.6),
                  },
                }}
              >
                <Stack direction="row" spacing={1} sx={{ alignItems: 'flex-start' }}>
                  <Icon sx={{ fontSize: 20, mt: 0.15 }} />
                  <Box>
                    <Typography variant="body2" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                      {row.label}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25 }}>
                      {row.blurb}
                    </Typography>
                  </Box>
                </Stack>
              </Box>
            );
          })}
        </Stack>

        <Box
          sx={{
            minHeight: 420,
            borderRadius: 3,
            bgcolor: 'background.paper',
            border: 1,
            borderColor: 'divider',
            p: { xs: 1.5, md: 2.25 },
          }}
        >
          <Box sx={{ mb: 2 }}>
            <Typography variant="h6" sx={{ fontWeight: 800 }}>
              {active.label}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {active.blurb}
            </Typography>
          </Box>

          {section === 'dashboard' ? (
            <PerformanceDashboardPanel onOpenReview={() => setSectionAndUrl('annual')} />
          ) : null}

          {section === 'annual' ? <PerformanceReviewsPage embedded kind="annual" /> : null}

          {section === 'skills' ? (
            <Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                Proficiency uses Learning → Developing → Proficient → Expert. These ratings drive
                assignment warnings when project complexity outpaces a designer&apos;s Complex Design
                (or Surfacing) level.
              </Typography>
              <TeamSkillMatrixPanel canManage={canManage} />
            </Box>
          ) : null}

          {section === 'templates' ? (
            <PerformanceTemplatesCyclesPanel canManage={canManage} />
          ) : null}

          {section === 'analytics' ? <PerformanceAnalyticsPanel /> : null}
        </Box>
      </Box>
    </Box>
  );
}

export default PerformancePage;
