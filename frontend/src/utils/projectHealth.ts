const ACTIVE_EXECUTION_STATUSES = new Set([
  'planning',
  'currently_being_worked_on',
  'on_hold',
]);

export function isActiveProjectForHealth(
  executionStatus: string,
  isArchived?: boolean,
): boolean {
  return !isArchived && ACTIVE_EXECUTION_STATUSES.has(executionStatus);
}
