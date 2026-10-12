export type Target = "replied" | "interested" | "meeting_booked";
export type Outcome = Target | "disqualified";

export interface Lead {
  id: number;
  external_id: string;
  company: string;
  industry: string;
  employees: number;
  employee_band: string;
  message_variant: string;
  baseline_score: number;
  outcome: Outcome | null;
  created_at: string;
  updated_at: string;
}

export interface SegmentMetric {
  dimension: "industry" | "employee_band" | "message_variant";
  segment: string;
  observations: number;
  successes: number;
  rate: number;
  smoothed_rate: number;
  lift: number;
  eligible: boolean;
  adjustment: number;
  recommendation: string;
}

export interface Analytics {
  target: Target;
  labeled_count: number;
  overall_successes: number;
  overall_rate: number;
  overall_smoothed_rate: number;
  metrics: SegmentMetric[];
}

export interface RankedLead extends Lead {
  baseline_rank: number;
  suggested_rank: number;
  suggested_score: number;
  rank_delta: number;
  drivers: string[];
}

export interface LeadPage {
  items: Lead[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface RankingResponse {
  target: Target;
  items: RankedLead[];
}

export interface ImportResult {
  filename: string;
  total_rows: number;
  created: number;
  updated: number;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail;
    const message = typeof detail === "string" ? detail : detail?.message;
    const errors = Array.isArray(detail?.errors) ? ` ${detail.errors.join(" ")}` : "";
    throw new Error(`${message || "Request failed"}${errors}`);
  }
  return body as T;
}

export const api = {
  leads: () => request<LeadPage>("/api/leads?page=1&page_size=100"),
  analytics: (target: Target) => request<Analytics>(`/api/analytics?target=${target}`),
  rankings: (target: Target) => request<RankingResponse>(`/api/rankings?target=${target}`),
  importLeads: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ImportResult>("/api/imports", { method: "POST", body: form });
  },
  updateOutcome: (leadId: number, outcome: Outcome) =>
    request<Lead>(`/api/leads/${leadId}/outcome`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ outcome })
    })
};
