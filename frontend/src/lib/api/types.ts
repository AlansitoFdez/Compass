/**
 * The shapes the Compass API returns, mirrored by hand from the backend's Pydantic
 * schemas (`tenders/schemas.py`, `matching/schemas.py`, `analysis/schemas.py`,
 * `analysis/extraction_schema.py`).
 *
 * Generating these from the OpenAPI document would be the scalable answer, and it is the
 * thing to do the day a third screen appears. For two screens it would add a build step
 * and a generated directory for less clarity than this file, which is also where the
 * shape is documented for a reader.
 *
 * The cost of that choice is real and worth naming: nothing checks these against the
 * server. Phase 5.2 changed `MatchListResponse` -- `total` stopped meaning "how many came
 * back" and a `funnel` object appeared -- and no tool would have caught it here.
 */

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
  /** Decimals arrive as strings: `Decimal` server-side, and JSON has no decimal type. */
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

/**
 * Survivors at each cumulative stage of the funnel's hard filters.
 *
 * This is the product's whole argument as numbers -- the corpus, then what is still open,
 * then CPV, budget and geography -- so the dashboard states the reduction instead of
 * asserting it. `after_location` always equals `MatchList.total`.
 */
export type FunnelCounts = {
  total: number;
  after_status: number;
  after_cpv: number;
  after_budget: number;
  after_location: number;
};

export type MatchList = {
  items: Match[];
  /** Tenders surviving the funnel -- NOT how many came back. That's `returned`. */
  total: number;
  returned: number;
  limit: number;
  funnel: FunnelCounts;
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

export type VerdictReason = { detail: string; citation: Citation | null };

export type VerdictResult = { verdict: Verdict; reasons: VerdictReason[] };

export type AnalysisResult = {
  expediente: string;
  status: AnalysisStatus;
  extraction: PliegoExtraction | null;
  citation_faithfulness: number | null;
  error_message: string | null;
  verdict: VerdictResult | null;
};

/**
 * The supplier's own profile -- what the funnel filters and ranks against, and what the
 * verdict compares a pliego's requirements to.
 *
 * Decimals are strings for the same reason budgets are: they are `Decimal` server-side.
 * The form keeps them as strings end to end rather than round-tripping through a JS
 * number, which cannot represent every decimal exactly.
 */
export type Provider = {
  description: string;
  cpv_codes: string[];
  min_budget: string | null;
  max_budget: string | null;
  annual_revenue: string | null;
  certifications: string[] | null;
  locations: string[] | null;
};

/**
 * What this installation is configured to do.
 *
 * Both keys are optional (5.4, 5.5), so a freshly downloaded Compass runs with neither.
 * The dashboard reads this to say what is missing *before* someone clicks something that
 * would then fail -- never to decide whether a request is allowed, which is the API's job.
 */
export type Capabilities = {
  /** Whether a pliego can be analyzed at all. `false` means no OpenRouter key. */
  analysis: boolean;
  /** Whether runs are traced to Langfuse. Changes nothing a user can see. */
  tracing: boolean;
};
