import { validateRequiredFields } from './formValues';

/**
 * Create/edit required-field validation for ProjectFormDialog.
 * Keep the values bag and field keys in lockstep so a visible selection
 * (e.g. project_classification) is never treated as missing.
 */
export function validateProjectFormRequired(params: {
  tool_number: string;
  part_description: string;
  customer_id: string;
  team_id?: string;
  stream_id?: string;
  project_classification?: string;
  isEdit: boolean;
  referenceLabel: string;
}): string | null {
  const values: Record<string, unknown> = {
    tool_number: params.tool_number,
    part_description: params.part_description,
    customer_id: params.customer_id,
  };
  const fields: Array<{ key: string; label: string }> = [
    { key: 'tool_number', label: params.referenceLabel },
    { key: 'part_description', label: 'Part description' },
    { key: 'customer_id', label: 'Customer' },
  ];

  if (!params.isEdit) {
    values.team_id = params.team_id;
    values.stream_id = params.stream_id;
    values.project_classification = params.project_classification;
    fields.push(
      { key: 'team_id', label: 'Team' },
      { key: 'stream_id', label: 'Engineering stream' },
      { key: 'project_classification', label: 'Project classification' },
    );
  }

  return validateRequiredFields(values, fields);
}
