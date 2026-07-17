import { useMemo, useState } from 'react';
import { Box, Tab, Tabs, Typography } from '@mui/material';
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
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'quarterly', label: 'Quarterly Reviews' },
  { id: 'annual', label: 'Annual Reviews' },
  { id: 'skills', label: 'Skills Matrix' },
  { id: 'templates', label: 'Templates & Cycles' },
  { id: 'analytics', label: 'Analytics' },
] as const;

type SectionId = (typeof SECTIONS)[number]['id'];

function sectionFromSearch(value: string | null): SectionId {
  if (value === 'reviews' || value === 'history') return 'annual';
  if (value === 'skills') return 'skills';
  if (SECTIONS.some((row) => row.id === value)) return value as SectionId;
  return 'dashboard';
}

export function PerformancePage() {
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

  return (
    <Box>
      <PageHeader subtitle="Review engine, skills matrix, and employee performance insights — one hub for capability and growth." />

      <Typography variant="h5" sx={{ fontWeight: 800, mb: 1 }}>
        Performance
      </Typography>

      <Tabs
        value={SECTIONS.findIndex((row) => row.id === section)}
        onChange={(_, index) => setSectionAndUrl(SECTIONS[index].id)}
        variant="scrollable"
        scrollButtons="auto"
        sx={{ mb: 2, borderBottom: 1, borderColor: 'divider' }}
      >
        {SECTIONS.map((row) => (
          <Tab key={row.id} label={row.label} />
        ))}
      </Tabs>

      {section === 'dashboard' ? (
        <PerformanceDashboardPanel
          onOpenReview={() => setSectionAndUrl('annual')}
        />
      ) : null}

      {section === 'quarterly' ? (
        <PerformanceReviewsPage embedded kind="quarterly" />
      ) : null}

      {section === 'annual' ? <PerformanceReviewsPage embedded kind="annual" /> : null}

      {section === 'skills' ? (
        <Box sx={{ bgcolor: 'background.paper', borderRadius: 2, p: { xs: 1.5, md: 2 } }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            Proficiency uses a four-level industry scale (Learning / Developing / Proficient /
            Expert), colour-coded like your Excel matrix. Assign each person a stream in Users so
            the right skill columns appear (e.g. Mold Design).
          </Typography>
          <TeamSkillMatrixPanel canManage={canManage} />
        </Box>
      ) : null}

      {section === 'templates' ? (
        <PerformanceTemplatesCyclesPanel canManage={canManage} />
      ) : null}

      {section === 'analytics' ? <PerformanceAnalyticsPanel /> : null}
    </Box>
  );
}

export default PerformancePage;
