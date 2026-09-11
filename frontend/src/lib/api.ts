/**
 * Typed client for the Compass API.
 *
 * The types mirror the backend's Pydantic schemas by hand (`tenders/schemas.py`,
 * `matching/schemas.py`, `analysis/schemas.py`, `analysis/extraction_schema.py`).
 * Generating them from the OpenAPI document would be the scalable answer; for two
 * screens it would add a build step and a generated-code directory for less clarity
 * than these 80 lines, which are also where the shape is documented for a reader.
 *
 * Runs from both sides: Server Components call it during render, and the analysis
 * panel calls it from the browser while polling. That is why the base URL is a
 * `NEXT_PUBLIC_` variable -- it has to be readable in the bundle, not only on the
 * server.
 */

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type TenderStatus =
  | "prior_notice"
  | "open_for_submission"
  | "pending_award"
  | "awarded"
  | "resolved"
  | "cancelled";

export type Tender = {
  expediente: string;
  contracting_body: string;
  title: string;
  cpv_codes: string[];
  budget_with_vat: string | null;
  budget_without_vat: string | null;
  estimated_value: string | null;
  contract_type: string;
  procedure_type: string;
  status: TenderStatus;
  submission_deadline: string | null;
  location: string | null;
  pcap_url: string | null;
  ppt_url: string | null;
  platform_url: string | null;
  published_at: string;
  updated_at_source: string;
};

/** One fused match: the tender plus which recoverer(s) surfaced it (2.6). */
export type Match = {
  tender: Tender;
  rrf_score: number;
  lexical_rank: number | null;
  lexical_score: number | null;
  vector_rank: number | null;
  vector_distance: number | null;
};

export type Citation = { clause: string; page: number; quote: string };

export type PliegoExtraction = {
  economic_solvency: {
    minimum_annual_turnover_eur: number | null;
    description: string;
    citation: Citation | null;
  };
  technical_solvency: {
    minimum_amount_eur: number | null;
    description: string;
    citation: Citation | null;
  };
  certifications: string[];
  certifications_citation: Citation | null;
  award_criteria: {
    total_points: number;
    criteria: { name: string; points: number; is_price: boolean }[];
    citation: Citation | null;
  };
  guarantees: {
    provisional_required: boolean;
    definitive_percentage: number | null;
    description: string;
    citation: Citation | null;
  };
  execution_deadline: { description: string; citation: Citation | null };
  submission_deadline: { description: string; citation: Citation | null };
  subcontracting: {
    allowed: boolean;
    description: string;
    citation: Citation | null;
  };
  lots: {
    divided_into_lots: boolean;
    can_bid_partial_lots: boolean | null;
    description: string;
    citation: Citation | null;
  };
};

export type AnalysisStatus =
  | "pending"
  | "in_progress"
  | "completed"
  | "failed"
  | "not_analyzable";

export type Verdict = "apto" | "apto_con_reservas" | "no_apto";

export type AnalysisResult = {
  expediente: string;
  status: AnalysisStatus;
  extraction: PliegoExtraction | null;
  citation_faithfulness: number | null;
  error_message: string | null;
  verdict: { verdict: Verdict; reasons: { detail: string; citation: Citation | null }[] } | null;
};

/** Thrown for any non-OK response, carrying the status so callers can tell 404 apart. */
export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    // Never a cached read: this dashboard exists to show what the funnel and the
    // analyst say *right now*, and the analysis panel polls a value that changes
    // between one request and the next.
    cache: "no-store",
    ...init,
  });
  if (!response.ok) {
    throw new ApiError(response.status, `${init?.method ?? "GET"} ${path} -> ${response.status}`);
  }
  return (await response.json()) as T;
}

/** An expediente can contain slashes (`SER/2026/0000006435`), so every segment is encoded. */
function encodeExpediente(expediente: string): string {
  return expediente.split("/").map(encodeURIComponent).join("/");
}

export function getMatches(limit = 20): Promise<{ items: Match[]; total: number; limit: number }> {
  return request(`/matches?limit=${limit}`);
}

export function getTender(expediente: string): Promise<Tender> {
  return request(`/tenders/${encodeExpediente(expediente)}`);
}

/** The current analysis, or `null` when this tender has never been analyzed (a real 404). */
export async function getAnalysis(expediente: string): Promise<AnalysisResult | null> {
  try {
    return await request<AnalysisResult>(`/tenders/${encodeExpediente(expediente)}/analysis`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

/** Enqueues an analysis. The API answers 202 and the result is only observable by polling. */
export function triggerAnalysis(expediente: string): Promise<{ detail: string }> {
  return request(`/tenders/${encodeExpediente(expediente)}/analyze`, { method: "POST" });
}
