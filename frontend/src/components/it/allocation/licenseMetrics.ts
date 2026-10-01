export interface LicenseMetricOption {
  value: string;
  label: string;
  rule: string;
}

/** Stored assignment_model codes; the server maps them to the engine metric. */
export const LICENSE_METRIC_OPTIONS: LicenseMetricOption[] = [
  {
    value: 'named_user',
    label: 'Named user',
    rule: 'One right per named employee, whatever their shift. Cannot be shared between employees.',
  },
  {
    value: 'per_user',
    label: 'Per user',
    rule: 'One right per employee (all their devices). Cannot be shared between employees.',
  },
  {
    value: 'device_bound',
    label: 'Per device',
    rule: 'Licensed to one computer; the right follows the device, not the person.',
  },
  {
    value: 'floating',
    label: 'Concurrent / floating',
    rule: 'Any authorized employee may use it; only as many at the same time as rights owned. Non-overlapping shifts can share one right.',
  },
  {
    value: 'concurrent',
    label: 'Concurrent',
    rule: 'Same as floating: simultaneous use is limited to the rights owned.',
  },
  {
    value: 'network',
    label: 'Network (license server)',
    rule: 'Concurrent rights served by a license server; scheduled use may not overlap beyond the rights owned.',
  },
  { value: 'site', label: 'Site', rule: 'Covers every employee at the site; rights are not counted.' },
  {
    value: 'other',
    label: 'Custom / other',
    rule: 'No sharing rule configured — each assignment consumes one right.',
  },
];

export function metricRule(code: string | null | undefined): string | undefined {
  return LICENSE_METRIC_OPTIONS.find((o) => o.value === code)?.rule;
}

export const COMPLIANCE_COLORS: Record<string, 'success' | 'warning' | 'error' | 'default'> = {
  COMPLIANT: 'success',
  FULLY_ALLOCATED: 'warning',
  OVER_ALLOCATED: 'error',
  EXPIRED: 'error',
};
