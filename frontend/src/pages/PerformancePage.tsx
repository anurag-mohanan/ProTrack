import { useMemo, useState } from 'react';
import { Box, Tab, Tabs, Typography } from '@mui/material';
import { useSearchParams } from 'react-router-dom';
import { PageHeader } from '../components/common/PageHeader';
import { TeamSkillMatrixPanel } from '../components/performance/TeamSkillMatrixPanel';
import { PerformanceReviewsPage } from './PerformanceReviewsPage';
import { useAuth } from '../context/AuthContext';
import { hasRole, ROLES } from '../utils/permissions';

function tabFromSearch(value: string | null): number {
  if (value === 'reviews' || value === 'history') return 1;
  return 0;
}

export function PerformancePage() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [tab, setTab] = useState(() => tabFromSearch(searchParams.get('tab')));

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

  return (
    <Box>
      <PageHeader subtitle="Team skillset charts, annual reviews, and individual performance history — one place for capability and growth." />

      <Typography variant="h5" sx={{ fontWeight: 800, mb: 1 }}>
        Performance
      </Typography>

      <Tabs
        value={tab}
        onChange={(_, next) => {
          setTab(next);
          setSearchParams(next === 1 ? { tab: 'reviews' } : { tab: 'skills' });
        }}
        sx={{ mb: 2, borderBottom: 1, borderColor: 'divider' }}
      >
        <Tab label="Skillset chart" />
        <Tab label="Reviews & history" />
      </Tabs>

      {tab === 0 ? (
        <Box sx={{ bgcolor: 'background.paper', borderRadius: 2, p: { xs: 1.5, md: 2 } }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            Proficiency uses a four-level industry scale (Learning / Developing / Proficient /
            Expert), colour-coded like your Excel matrix. Assign each person a stream in Users so
            the right skill columns appear (e.g. Mold Design).
          </Typography>
          <TeamSkillMatrixPanel canManage={canManage} />
        </Box>
      ) : (
        <PerformanceReviewsPage embedded />
      )}
    </Box>
  );
}

export default PerformancePage;
