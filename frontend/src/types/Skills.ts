export type SkState = 'no_record' | 'claimed' | 'verified' | 'reassessment' | 'rejected' | 'archived';
export type SkDecision = 'verify' | 'reject' | 'request_reassessment';
export type SkMethod = 'manager_assessment' | 'independent_assessment';
export type SkPlanStatus = 'planned' | 'in_progress' | 'completed' | 'cancelled';

export interface SkOption {
  value: string;
  label: string;
}

export interface SkLevel {
  level: number;
  name: string;
  description: string | null;
}

export interface SkAccess {
  can_manage_taxonomy: boolean;
  can_view_others: boolean;
  can_review: boolean;
  can_match_resources: boolean;
}

export interface SkSkill {
  id: string;
  name: string;
  category: string | null;
  kind: string | null;
  kind_label: string | null;
  description: string | null;
  aliases: string[];
  discipline_id: string | null;
  discipline_name: string | null;
  customer_id: string | null;
  customer_name: string | null;
  is_critical: boolean;
  min_verified_coverage: number | null;
  specialist_level: number | null;
  reassessment_months: number | null;
  sort_order: number;
  is_active: boolean;
  holder_count: number;
}

export interface SkRelationship {
  id: string;
  from_skill_id: string;
  from_skill_name: string | null;
  to_skill_id: string;
  to_skill_name: string | null;
  relation_type: string;
  relation_label: string;
  note: string | null;
}

export interface SkTaxonomy {
  skills: SkSkill[];
  categories: string[];
  kinds: SkOption[];
  relation_types: SkOption[];
  relationships: SkRelationship[];
  proficiency_levels: SkLevel[];
  disciplines: { id: string; name: string }[];
  verification_methods: SkOption[];
}

export interface SkSkillWrite {
  name: string;
  category: string | null;
  kind: string | null;
  description: string | null;
  aliases: string[];
  discipline_id: string | null;
  customer_id: string | null;
  is_critical: boolean;
  min_verified_coverage: number | null;
  specialist_level: number | null;
  reassessment_months: number | null;
  sort_order: number;
  is_active: boolean;
}

export interface SkEvidence {
  id: string;
  project_id: string | null;
  tool_number: string | null;
  part_description: string | null;
  execution_status: string | null;
  hours_total: number | null;
  visible: boolean;
  note: string | null;
  added_at: string;
}

export interface SkEvent {
  id: string;
  action: string;
  from_status: string | null;
  to_status: string | null;
  from_declared_level: number | null;
  to_declared_level: number | null;
  from_verified_level: number | null;
  to_verified_level: number | null;
  verification_method: string | null;
  actor_name: string | null;
  occurred_at: string;
  feedback: string | null;
  confidential_note: string | null;
  detail: string | null;
}

export interface SkRecord {
  id: string;
  user_id: string;
  skill_id: string;
  skill_name: string;
  category: string | null;
  kind: string | null;
  skill_is_active: boolean;
  status: string;
  state: SkState;
  state_label: string;
  origin: string;
  origin_label: string;
  declared_level: number | null;
  verified_level: number | null;
  claim_pending: boolean;
  reassessment_due: boolean;
  legacy_proficiency: string | null;
  verification_method: string | null;
  verification_method_label: string | null;
  verified_at: string | null;
  verified_by_name: string | null;
  last_assessed_at: string | null;
  last_assessed_by_name: string | null;
  years_experience: number | null;
  last_used_on: string | null;
  employee_note: string | null;
  assessment_feedback: string | null;
  confidential_notes: string | null;
  confidential_hidden: boolean;
  updated_at: string;
  evidence: SkEvidence[];
  history: SkEvent[];
}

export interface SkProfile {
  user_id: string;
  name: string;
  designation: string | null;
  teams: string[];
  is_self: boolean;
  can_review: boolean;
  can_declare: boolean;
  records: SkRecord[];
  proficiency_levels: SkLevel[];
}

export interface SkExperienceProject {
  project_id: string;
  tool_number: string;
  part_description: string | null;
  customer_name: string | null;
  stream_name: string | null;
  tool_type: string | null;
  complexity: string | null;
  project_stage: string | null;
  execution_status: string | null;
  completed_at: string | null;
  roles: string[];
  timesheet_only: boolean;
  hours_total: number;
  hours_by_status: Record<string, number>;
  first_booked: string | null;
  last_booked: string | null;
  cad_software: null;
}

export interface SkExperience {
  subject_user_id: string;
  projects: SkExperienceProject[];
  hidden_project_count: number;
  limitations: string[];
}

export interface SkMatrixCell {
  record_id: string | null;
  state: SkState;
  verified_level: number | null;
  declared_level: number | null;
  claim_pending: boolean;
  last_verified_at: string | null;
  matches: boolean;
}

export interface SkMatrixPerson {
  user_id: string;
  name: string;
  designation: string | null;
  team_name: string | null;
  training_plans_open: number;
  can_review: boolean;
  cells: Record<string, SkMatrixCell>;
}

export interface SkMatrix {
  skills: { id: string; name: string; category: string | null; kind: string | null; is_critical: boolean }[];
  people: SkMatrixPerson[];
  proficiency_levels: SkLevel[];
  state_labels: Record<string, string>;
  legend: string[];
}

export interface SkMatrixParams {
  team_id?: string;
  category?: string;
  kind?: string;
  software_skill_id?: string;
  min_level?: number;
  state?: string[];
  q?: string;
  critical_only?: boolean;
}

export interface SkQueueItem {
  record_id: string;
  user_id: string;
  name: string | null;
  skill_id: string;
  skill_name: string;
  status: string;
  origin: string;
  declared_level: number | null;
  verified_level: number | null;
  reason: string;
  since: string | null;
}

export interface SkGapSkill {
  skill_id: string;
  skill_name: string;
  category: string | null;
  kind: string | null;
  is_critical: boolean;
  specialist_level: number;
  specialist_level_name: string | null;
  min_verified_coverage: number | null;
  verified_count: number;
  verified_at_min_level: number;
  verified_specialists: number;
  specialist_names: string[];
  claimed_unverified: number;
  reassessment_due: number;
  rejected: number;
  no_record: number;
  population: number;
  flags: string[];
}

export interface SkGapFinding {
  code: string;
  severity: 'high' | 'medium' | 'info';
  skill_id: string;
  skill_name: string;
  explanation: string;
  evidence: Record<string, number>;
}

export interface SkGapReport {
  method_version: string;
  as_of: string;
  population: number;
  skills: SkGapSkill[];
  findings: SkGapFinding[];
  team_depth: {
    team_id: string;
    team_name: string;
    skill_id: string;
    skill_name: string;
    members: number;
    verified_specialists: number;
    depth: 'none' | 'single' | 'adequate';
  }[];
  training: {
    plan_id: string;
    user_id: string;
    name: string;
    skill_id: string;
    skill_name: string | null;
    baseline_verified_level: number | null;
    target_level: number;
    training_required: boolean;
    training_requirement: string | null;
    is_knowledge_transfer: boolean;
    mentor_name: string | null;
    target_review_date: string | null;
    overdue: boolean;
    status: SkPlanStatus;
  }[];
  reassessment: {
    record_id: string;
    user_id: string;
    name: string;
    skill_id: string;
    skill_name: string;
    verified_level: number | null;
    verified_at: string | null;
    reason: string;
  }[];
  project_requirements: {
    project_id: string;
    tool_number: string;
    part_description: string | null;
    requirement_id: string;
    skill_id: string;
    skill_name: string;
    is_critical: boolean;
    min_level: number;
    is_mandatory: boolean;
    verified_holders: number;
    claimed_unverified: number;
    reassessment_due: number;
    status: 'no_verified_coverage' | 'single_verified_holder' | 'covered';
  }[];
  rules: string[];
}

export interface SkGapParams {
  team_id?: string;
  category?: string;
  kind?: string;
  critical_only?: boolean;
  min_level?: number;
}

export interface SkPlan {
  id: string;
  user_id: string;
  user_name: string | null;
  skill_id: string;
  skill_name: string | null;
  baseline_verified_level: number | null;
  current_verified_level: number | null;
  verification_outcome: SkState;
  target_level: number;
  objective: string | null;
  training_required: boolean;
  training_requirement: string | null;
  is_knowledge_transfer: boolean;
  mentor_id: string | null;
  mentor_name: string | null;
  mentor_verified_level: number | null;
  target_review_date: string | null;
  status: SkPlanStatus;
  progress_note: string | null;
  completed_at: string | null;
  updated_at: string;
}

export interface SkPlanWrite {
  user_id?: string;
  skill_id: string;
  target_level: number;
  objective: string | null;
  training_required: boolean;
  training_requirement: string | null;
  is_knowledge_transfer: boolean;
  mentor_id: string | null;
  target_review_date: string | null;
  status: SkPlanStatus;
  progress_note: string | null;
}

export interface SkRequirement {
  id: string;
  skill_id: string;
  skill_name: string | null;
  skill_is_active: boolean;
  min_level: number;
  min_level_name: string | null;
  is_mandatory: boolean;
  note: string | null;
}

export interface SkRequirements {
  project_id: string;
  can_edit: boolean;
  requirements: SkRequirement[];
}

export interface SkRequirementSpec {
  skill_id: string;
  min_level: number;
  is_mandatory: boolean;
}

export interface SkMatchRequest {
  project_id?: string;
  requirements?: SkRequirementSpec[];
  team_id?: string;
  start?: string;
  granularity: 'week' | 'month';
  periods: number;
}

export type SkSuitability = 'confirmed' | 'unconfirmed' | 'below_requirement';
export type SkAvailability = 'capacity_indicated' | 'uncertain' | 'committed' | 'unavailable';

export interface SkCandidate {
  user_id: string;
  name: string;
  team_name: string | null;
  suitability: SkSuitability;
  suitability_label: string;
  requirements: {
    skill_id: string;
    skill_name: string;
    min_level: number;
    is_mandatory: boolean;
    state: string;
    state_label: string;
    verified_level: number | null;
    declared_level: number | null;
  }[];
  verified_matches: number;
  availability: SkAvailability;
  availability_label: string;
  availability_reason: string;
  allocatable_hours: number;
  approved_remaining_hours: number;
  open_assignments: number;
  open_assignments_without_estimate: number;
  explanation: string[];
}

export interface SkMatchResult {
  method_version: string;
  generated_for: string;
  horizon_start: string;
  horizon_end: string;
  requirements: (SkRequirementSpec & { skill_name: string; min_level_name: string | null })[];
  candidates: SkCandidate[];
  summary: {
    candidates: number;
    confirmed: number;
    confirmed_with_capacity_indicated: number;
    unconfirmed: number;
    below_requirement: number;
  };
  capacity_status: string;
  capacity_limitations: string[];
  rules: string[];
}
