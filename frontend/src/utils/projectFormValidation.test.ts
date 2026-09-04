import { validateProjectFormRequired } from './projectFormValidation';

const baseCreate = {
  tool_number: 'T-100',
  part_description: 'Mold cavity',
  customer_id: 'cust-1',
  team_id: 'team-1',
  stream_id: 'stream-1',
  isEdit: false,
  referenceLabel: 'Tool number',
};

describe('validateProjectFormRequired', () => {
  it('rejects create when project classification is empty', () => {
    const error = validateProjectFormRequired({
      ...baseCreate,
      project_classification: '',
    });
    expect(error).toBe('Project classification is required.');
  });

  it('accepts create when Full Design is selected', () => {
    const error = validateProjectFormRequired({
      ...baseCreate,
      project_classification: 'full_design',
    });
    expect(error).toBeNull();
  });

  it('accepts create when Small Task is selected', () => {
    const error = validateProjectFormRequired({
      ...baseCreate,
      project_classification: 'small_task',
    });
    expect(error).toBeNull();
  });

  it('does not require classification on edit', () => {
    const error = validateProjectFormRequired({
      tool_number: 'T-100',
      part_description: 'Mold cavity',
      customer_id: 'cust-1',
      isEdit: true,
      referenceLabel: 'Tool number',
    });
    expect(error).toBeNull();
  });

  it('rejects create when classification key is omitted from values (regression)', () => {
    // Guarantees the helper always puts project_classification in the bag
    // so UI selection and validation cannot diverge.
    const error = validateProjectFormRequired({
      ...baseCreate,
      project_classification: undefined,
    });
    expect(error).toBe('Project classification is required.');
  });
});
