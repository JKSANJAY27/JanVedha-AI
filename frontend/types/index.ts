export type TicketStatus =
  | "OPEN"
  | "ASSIGNED"
  | "IN_PROGRESS"
  | "PENDING_VERIFICATION"
  | "CLOSED"
  | "CLOSED_UNVERIFIED"
  | "REOPENED"
  | "REJECTED";

export type PriorityLabel = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

export type UserRole =
  | "WARD_OFFICER"
  | "ZONAL_OFFICER"
  | "DEPT_HEAD"
  | "COMMISSIONER"
  | "COUNCILLOR"
  | "SUPER_ADMIN";

export type DeptId =
  | "D01"
  | "D02"
  | "D03"
  | "D04"
  | "D05"
  | "D06"
  | "D07"
  | "D08"
  | "D09"
  | "D10"
  | "D11"
  | "D12"
  | "D13"
  | "D14";

export interface Ticket {
  id: number;
  ticket_code: string;
  source: string;
  description: string;
  dept_id: DeptId;
  dept_name: string;
  ward_id: number;
  ward_name: string;
  priority_score: number;
  priority_label: PriorityLabel;
  status: TicketStatus;
  ai_confidence: number;
  reporter_phone?: string;
  photo_url?: string;
  before_photo_url?: string;
  after_photo_url?: string;
  language_detected: string;
  requires_human_review: boolean;
  sla_deadline: string; // ISO datetime
  created_at: string;
  assigned_at?: string;
  resolved_at?: string;
  assigned_officer_name?: string;
  report_count: number;
}

export interface AuditEvent {
  id: number;
  action: string;
  old_value?: Record<string, unknown>;
  new_value?: Record<string, unknown>;
  actor_role: string;
  created_at: string;
}

export interface Department {
  dept_id: DeptId;
  dept_name: string;
  handles: string;
  sla_days: number;
  is_external: boolean;
}

export interface WardStats {
  ward_id: number;
  ward_name: string;
  score: number;
  rank: number;
  sla_compliance_pct: number;
  avg_resolution_days: number;
  total_tickets_month: number;
}

export interface CityStats {
  total_tickets: number;
  resolved_pct: number;
  avg_resolution_hours: number;
  active_critical: number;
  active_high: number;
  last_updated: string;
}

export interface ClassificationPreview {
  dept_id: DeptId;
  dept_name: string;
  issue_summary: string;
  confidence: number;
  needs_clarification: boolean;
  clarification_question?: string;
}

export interface ComplaintFormData {
  description: string;
  location_text: string;
  lat?: number;
  lng?: number;
  photo_base64?: string;
  reporter_phone: string;
  reporter_name?: string;
  language?: string;
  consent_given: true; // literal true — not optional
}

export interface SubmitComplaintResponse {
  ticket_code: string;
  status: TicketStatus;
  sla_deadline: string;
  dept_name: string;
  message: string;
}

export interface OfficerUser {
  id: number;
  name: string;
  role: UserRole;
  ward_id?: number;
  zone_id?: number;
  dept_id?: DeptId;
  access_token: string;
}

export interface SentimentSnapshot {
  ward_id: number;
  positive_pct: number;
  negative_pct: number;
  neutral_pct: number;
  total_posts: number;
  spike_alert: boolean;
  snapshot_at: string;
}

export interface MisinformationFlag {
  id: string;
  platform: string;
  post_url: string;
  claim_text: string;
  evidence_tickets: number[];
  evidence_summary: string;
  draft_rebuttal: string;
  flagged_at: string;
  status: "PENDING_REVIEW" | "APPROVED" | "DISMISSED";
}

export interface WardPrediction {
  ward_id: number;
  ward_name: string;
  current_score: number;
  predicted_next_month_score: number;
  risk_level: "HIGH_RISK" | "MODERATE_RISK" | "LOW_RISK";
  ai_recommendation: string;
  computed_at: string;
}

export interface ApiError {
  error: string;
  message: string;
  detail?: Record<string, unknown>;
}
