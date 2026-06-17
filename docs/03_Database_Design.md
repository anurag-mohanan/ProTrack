Projects

- id
- tool_number
- part_description
- customer_id
- customer_contact_id
- stream_id
- parent_project_id

- project_manager_id
- designer_id
- surfacer_id

- original_due_date
- current_due_date

- quoted_hours
- actual_hours

- priority
- health
- delay_reason

- status

- created_by
- created_date

## Milestone Templates

Milestone Templates define the workflow for a Business Stream.

Examples:

### Mold Design Template

1. Feasibility
2. Blockout
3. Roughing
4. Intermediate Review
5. Final Review
6. Manifold Approval
7. File Release
8. BOM Release
9. Engraving Approval
10. Plaques Approval

### Product Design Template

1. Concept Review
2. Design Review
3. Prototype Release
4. Validation
5. Final Release

Milestone Templates are admin-configurable.

### MilestoneTemplate Table

- id
- stream_id
- name
- description
- is_active

### TemplateMilestone Table

- id
- template_id
- sequence_no
- milestone_name
- required

### ProjectTaskType

Purpose:

Allows a project to have multiple task types.

Fields:

- project_id
- task_type_id