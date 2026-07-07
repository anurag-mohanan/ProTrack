import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Grid,
  List,
  ListItem,
  ListItemText,
  Typography,
} from '@mui/material';
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import HelpOutlineRoundedIcon from '@mui/icons-material/HelpOutlineRounded';
import { PageContainer } from '../components/common/PageContainer';
import { ModernPageHeader, KpiMetricCard } from '../components/ui/design-system';
import { KpiStrip } from '../components/analytics/KpiStrip';

const HELP_SECTIONS = [
  {
    title: 'Projects',
    bullets: [
      'Use Tool Number as the unique customer mold/tool identifier.',
      'Project Template auto-creates standard milestones for faster setup.',
      'Quoted Hours are customer estimates; Actual Hours come from approved timesheets.',
    ],
  },
  {
    title: 'Milestones',
    bullets: [
      'Milestones track stage progress and influence health indicators.',
      'Keep due dates realistic to improve dashboard risk insights.',
    ],
  },
  {
    title: 'Resource Planning',
    bullets: [
      'Green = available, Amber = near capacity, Red = overloaded, Grey = leave/unavailable.',
      'Use drag-and-drop timeline bars to rebalance assignments quickly.',
    ],
  },
  {
    title: 'Timesheets',
    bullets: [
      'Billable contributes to customer delivery effort.',
      'Non-billable and Non-productive are tracked separately for analytics.',
      'Leave entries are reported in leave insights and availability summaries.',
    ],
  },
  {
    title: 'Reports',
    bullets: [
      'Use categories and drill-down breadcrumbs to move from summary to detail.',
      'Export CSV/PDF from report panels when permissions allow.',
    ],
  },
  {
    title: 'Imports',
    bullets: [
      'Historical imports expect clean, consistent names for users/projects/tasks.',
      'Validate stream and task mappings before final submission.',
    ],
  },
  {
    title: 'Administration',
    bullets: [
      'Master data updates impact project forms, timesheets, and reporting.',
      'Use delete-check prompts to review impact before destructive actions.',
    ],
  },
];

export default function HelpCenterPage() {
  return (
    <PageContainer>
      <ModernPageHeader
        title="Help Center"
        subtitle="Concise in-app guidance to reduce training and speed up onboarding."
      />
      <Box sx={{ mb: 2.5 }}>
        <KpiStrip columns={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            title="Keyboard Shortcuts"
            value="Ctrl+S"
            subtitle="Save current form"
            icon={HelpOutlineRoundedIcon}
            compact
          />
          <KpiMetricCard title="Quick Create" value="Ctrl+N" subtitle="Open new project" icon={HelpOutlineRoundedIcon} compact />
          <KpiMetricCard title="Quick Search" value="Ctrl+F" subtitle="Focus global search" icon={HelpOutlineRoundedIcon} compact />
          <KpiMetricCard title="Close Dialogs" value="Esc" subtitle="Dismiss open dialogs" icon={HelpOutlineRoundedIcon} compact />
        </KpiStrip>
      </Box>
      <Grid container spacing={2}>
        {HELP_SECTIONS.map((section) => (
          <Grid key={section.title} size={{ xs: 12, md: 6 }}>
            <Accordion defaultExpanded={section.title === 'Projects'}>
              <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
                <Typography sx={{ fontWeight: 700 }}>{section.title}</Typography>
              </AccordionSummary>
              <AccordionDetails>
                <List dense>
                  {section.bullets.map((item) => (
                    <ListItem key={item} disableGutters>
                      <ListItemText primary={item} />
                    </ListItem>
                  ))}
                </List>
              </AccordionDetails>
            </Accordion>
          </Grid>
        ))}
      </Grid>
    </PageContainer>
  );
}
