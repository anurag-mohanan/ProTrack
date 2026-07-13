export const REPORT_CATEGORIES = [
  {
    id: 'executive',
    label: 'Executive',
    slugs: ['engineering-suite'],
  },
  {
    id: 'projects',
    label: 'Projects',
    slugs: ['project-hours', 'by-stage', 'by-execution-status', 'project-portfolio'],
  },
  {
    id: 'customers',
    label: 'Customers',
    slugs: ['customer-summary', 'customer-timesheet-pack'],
  },
  {
    id: 'resources',
    label: 'Resources',
    slugs: ['designer-utilization', 'billable-utilization', 'team-reports'],
  },
  {
    id: 'timesheets',
    label: 'Timesheets',
    slugs: ['timesheet-reports'],
  },
  {
    id: 'engineering',
    label: 'Engineering KPIs',
    slugs: ['project-hours', 'project-portfolio'],
  },
  {
    id: 'leave',
    label: 'Leave & NP',
    slugs: ['np-hours', 'np-by-designer', 'np-by-month', 'top-np', 'billable-vs-np'],
  },
  {
    id: 'planning',
    label: 'Planning',
    slugs: ['team-reports', 'designer-utilization'],
  },
] as const;

export type ReportCategoryId = (typeof REPORT_CATEGORIES)[number]['id'];
