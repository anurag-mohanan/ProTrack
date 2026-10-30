import { Box, Tab, Tabs } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { fetchSkillAccess, skillQueryKeys } from '../api/skills';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { PageContainer } from '../components/common/PageContainer';
import { PageHeader } from '../components/common/PageHeader';
import { MySkillsPanel } from '../components/skills/MySkillsPanel';
import { SkillCandidatePanel } from '../components/skills/SkillCandidatePanel';
import { SkillGapsPanel } from '../components/skills/SkillGapsPanel';
import { SkillMatrixPanel } from '../components/skills/SkillMatrixPanel';
import { SkillPlansPanel } from '../components/skills/SkillPlansPanel';
import { SkillTaxonomyPanel } from '../components/skills/SkillTaxonomyPanel';

type SkillTab = 'mine' | 'matrix' | 'gaps' | 'plans' | 'candidates' | 'taxonomy';

export default function EngineeringSkillsPage() {
  const [params, setParams] = useSearchParams();
  const accessQuery = useQuery({ queryKey: skillQueryKeys.access, queryFn: fetchSkillAccess });

  if (accessQuery.isLoading) return <LoadingState message="Loading engineering skills…" />;
  if (accessQuery.error) return <ErrorState error={accessQuery.error} onRetry={() => void accessQuery.refetch()} />;
  const access = accessQuery.data!;

  const tabs: { value: SkillTab; label: string }[] = [
    { value: 'mine', label: 'My skills' },
    ...(access.can_view_others ? [{ value: 'matrix' as const, label: 'Skills matrix' }, { value: 'gaps' as const, label: 'Gaps & succession' }] : []),
    ...(access.can_view_others || access.can_review ? [{ value: 'plans' as const, label: 'Development plans' }] : []),
    ...(access.can_match_resources ? [{ value: 'candidates' as const, label: 'Candidate finder' }] : []),
    ...(access.can_manage_taxonomy ? [{ value: 'taxonomy' as const, label: 'Taxonomy' }] : []),
  ];
  const requested = params.get('tab') as SkillTab | null;
  const tab = tabs.some((t) => t.value === requested) ? requested! : 'mine';

  return (
    <PageContainer>
      <PageHeader subtitle="Verified engineering skills: self-declared claims, reviewer verification, coverage gaps, development plans and skill-based candidate search." />
      <Tabs
        value={tab}
        onChange={(_, value: SkillTab) => setParams(value === 'mine' ? {} : { tab: value }, { replace: true })}
        variant="scrollable"
        sx={{ mb: 2, minHeight: 40, borderBottom: 1, borderColor: 'divider' }}
      >
        {tabs.map((t) => (
          <Tab key={t.value} value={t.value} label={t.label} sx={{ minHeight: 40 }} />
        ))}
      </Tabs>
      <Box>
        {tab === 'mine' ? <MySkillsPanel /> : null}
        {tab === 'matrix' ? <SkillMatrixPanel access={access} /> : null}
        {tab === 'gaps' ? <SkillGapsPanel /> : null}
        {tab === 'plans' ? <SkillPlansPanel access={access} /> : null}
        {tab === 'candidates' ? <SkillCandidatePanel /> : null}
        {tab === 'taxonomy' ? <SkillTaxonomyPanel /> : null}
      </Box>
    </PageContainer>
  );
}
