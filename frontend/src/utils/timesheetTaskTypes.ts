import type { TaskType } from '../types';

/** Task types valid for a project's stream (matches backend validation). */
export function taskTypesForProjectStream(
  taskTypes: TaskType[],
  streamId: string | null | undefined,
): TaskType[] {
  const active = taskTypes.filter((task) => task.is_active !== false);
  if (!streamId) return [];
  return active.filter((task) => task.stream_id === streamId);
}

/** Pick a task type for the project stream, preferring a saved or Design default. */
export function resolveTaskTypeIdForProject(
  taskTypes: TaskType[],
  streamId: string | null | undefined,
  preferredTaskTypeId?: string | null,
): string {
  const options = taskTypesForProjectStream(taskTypes, streamId);
  if (
    preferredTaskTypeId &&
    options.some((task) => task.id === preferredTaskTypeId)
  ) {
    return preferredTaskTypeId;
  }
  const design = options.find((task) => task.name.trim().toLowerCase() === 'design');
  return design?.id ?? options[0]?.id ?? '';
}

export function isTaskTypeValidForProjectStream(
  taskTypes: TaskType[],
  streamId: string | null | undefined,
  taskTypeId: string | null | undefined,
): boolean {
  if (!taskTypeId) return false;
  return taskTypesForProjectStream(taskTypes, streamId).some((task) => task.id === taskTypeId);
}
