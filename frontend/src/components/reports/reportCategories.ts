export const REPORT_CATEGORIES = [
  {
    id: 'timesheets',
    label: 'Timesheets',
    slugs: ['timesheet-reports'],
  },
  {
    id: 'executive',
    label: 'Executive',
    slugs: ['engineering-suite'],
  },
  {
    id: 'projects',
    label: 'Projects',
    slugs: ['project-hours'],
  },
  {
    id: 'resources',
    label: 'Teams',
    slugs: ['team-reports'],
  },
  {
    id: 'customers',
    label: 'Customers',
    slugs: ['customer-timesheet-pack'],
  },
] as const;

export type ReportCategoryId = (typeof REPORT_CATEGORIES)[number]['id'];
