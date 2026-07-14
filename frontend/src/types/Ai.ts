export interface AiInsight {
  id: string;
  module: string;
  category: string;
  severity: 'info' | 'warning' | 'error';
  title: string;
  detail?: string | null;
  href?: string | null;
  confidence: number;
  entity_type?: string | null;
  entity_id?: string | null;
  metadata?: Record<string, unknown>;
}

export interface MorningBrief {
  greeting: string;
  active_projects: number;
  due_this_week: number;
  high_risk_projects: number;
  engineers_available: number;
  utilization_percent: number;
  missing_timesheets: number;
  over_budget_projects: number;
  late_milestones: number;
  insights: AiInsight[];
  generated_at: string;
}

export interface QuoteHourBreakdown {
  design_hours: number;
  surfacing_hours: number;
  checking_hours: number;
  bom_hours: number;
  total_hours: number;
}

export interface SimilarProjectRef {
  project_id: string;
  tool_number: string;
  customer_name?: string | null;
  actual_hours: number;
  quoted_hours: number;
  similarity_score: number;
}

export interface QuoteRecommendation {
  project_id?: string | null;
  tool_number?: string | null;
  customer_name?: string | null;
  project_type_name?: string | null;
  suggested: QuoteHourBreakdown;
  confidence_percent: number;
  similar_projects: SimilarProjectRef[];
  rationale?: string | null;
}

export interface ResourceRecommendation {
  role: string;
  user_id: string;
  user_name: string;
  score: number;
  utilization_percent: number;
  available_hours: number;
  reasoning: string;
  similar_project_count: number;
}

export interface ResourceOptimizationResult {
  project_id?: string | null;
  designers: ResourceRecommendation[];
  surfacers: ResourceRecommendation[];
  design_leaders: ResourceRecommendation[];
}

export interface SchedulePrediction {
  project_id: string;
  tool_number: string;
  predicted_completion?: string | null;
  target_completion?: string | null;
  confidence_percent: number;
  reasons: string[];
  late_milestones: number;
  bottleneck?: string | null;
}

export interface KnowledgeRecord {
  id: string;
  project_id: string;
  tool_number: string;
  customer_name?: string | null;
  project_type_name?: string | null;
  designer_name?: string | null;
  surfacer_name?: string | null;
  quoted_hours: number;
  actual_hours: number;
  milestone_count: number;
  engineering_change_count: number;
  mechanism?: string | null;
  keywords: string[];
  completed_at?: string | null;
}

export interface TimesheetSuggestion {
  entry_date: string;
  project_id?: string | null;
  tool_number?: string | null;
  task_type_id?: string | null;
  task_name?: string | null;
  suggested_hours: number;
  reason: string;
  confidence: number;
}

export interface ChatResponse {
  answer: string;
  insights: AiInsight[];
  data: Record<string, unknown>;
}

export interface WallProjectCard {
  project_id?: string | null;
  tool_number: string;
  customer_name?: string | null;
  designer_name?: string | null;
  surfacer_name?: string | null;
  contributor_names?: string[];
  team_name?: string | null;
  due_date?: string | null;
  health?: string | null;
  execution_status?: string | null;
  project_stage?: string | null;
  current_milestone?: string | null;
  progress_percent?: number;
  quoted_hours?: number;
  actual_hours?: number;
  variance_hours?: number;
  variance_percent?: number | null;
  complexity?: string | null;
  attention_reason?: string | null;
}

export interface WallTeamLiveBlock {
  team_id?: string | null;
  team_name: string;
  engineering_manager_name?: string | null;
  design_leader_name?: string | null;
  active_count: number;
  on_hold_count?: number;
  red_count: number;
  yellow_count: number;
  projects: WallProjectCard[];
}

export interface ExecutiveWallData {
  active_projects: number;
  utilization_percent: number;
  late_milestones: number;
  current_deliveries: Record<string, unknown>[];
  recent_releases: Record<string, unknown>[];
  capacity_hours: number;
  hours_logged_month: number;
  customer_distribution: Record<string, unknown>[];
  health_summary: Record<string, unknown>;
  teams_live?: WallTeamLiveBlock[];
  upcoming_deliveries?: WallProjectCard[];
  late_deliveries?: WallProjectCard[];
  refreshed_at: string;
}

export interface AiOperationsSummary {
  insights: AiInsight[];
  morning_brief?: MorningBrief | null;
  generated_at: string;
}
