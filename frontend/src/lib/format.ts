/**
 * Display helpers: Spanish labels for the API's closed vocabularies, and number/date
 * formatting in the locale a Spanish procurement officer expects.
 *
 * The backend speaks English identifiers on purpose (see CLAUDE.md); the translation to
 * what a user reads lives here, in one place, instead of being spelled out inline in
 * every component.
 */

import type { AnalysisStatus, TenderStatus, Verdict } from "@/lib/api";

const TENDER_STATUS_LABELS: Record<TenderStatus, string> = {
  prior_notice: "Anuncio previo",
  open_for_submission: "En plazo de presentación",
  pending_award: "Pendiente de adjudicación",
  awarded: "Adjudicada",
  resolved: "Resuelta",
  cancelled: "Anulada",
};

const VERDICT_LABELS: Record<Verdict, string> = {
  apto: "APTO",
  apto_con_reservas: "APTO CON RESERVAS",
  no_apto: "NO APTO",
};

/** What each verdict actually means for the reader, under the label itself. */
const VERDICT_SUMMARIES: Record<Verdict, string> = {
  apto: "Nada en el pliego bloquea ni condiciona tu candidatura.",
  apto_con_reservas:
    "Puedes presentarte, pero hay requisitos que tu perfil no permite verificar.",
  no_apto: "Hay requisitos que tu perfil no cumple.",
};

const ANALYSIS_STATUS_LABELS: Record<AnalysisStatus, string> = {
  pending: "En cola",
  in_progress: "Analizando el pliego",
  completed: "Análisis completado",
  failed: "El análisis falló",
  not_analyzable: "Pliego no analizable",
};

export function tenderStatusLabel(status: TenderStatus): string {
  return TENDER_STATUS_LABELS[status] ?? status;
}

export function verdictLabel(verdict: Verdict): string {
  return VERDICT_LABELS[verdict] ?? verdict;
}

export function verdictSummary(verdict: Verdict): string {
  return VERDICT_SUMMARIES[verdict] ?? "";
}

export function analysisStatusLabel(status: AnalysisStatus): string {
  return ANALYSIS_STATUS_LABELS[status] ?? status;
}

/** Budgets arrive as strings: they are `Decimal` server-side, and JSON has no decimals. */
export function formatEur(amount: string | number | null): string {
  if (amount === null) return "Sin importe publicado";
  const value = typeof amount === "string" ? Number(amount) : amount;
  if (Number.isNaN(value)) return "Sin importe publicado";
  return new Intl.NumberFormat("es-ES", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatDate(iso: string | null): string {
  if (iso === null) return "Sin fecha";
  return new Intl.DateTimeFormat("es-ES", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(iso));
}

/**
 * Thousands separators in the Spanish convention, for the funnel's counts.
 *
 * `useGrouping: "always"` because the default leaves four-digit numbers ungrouped in
 * `es-ES` -- so the corpus rendered as "3583" on screen while every document about this
 * project writes it "3.583".
 */
export function formatCount(value: number): string {
  return new Intl.NumberFormat("es-ES", { useGrouping: "always" }).format(value);
}

/** Days left until `iso`, or `null` when there is no date to count down to. */
export function daysUntil(iso: string | null): number | null {
  if (iso === null) return null;
  const millisecondsPerDay = 1000 * 60 * 60 * 24;
  return Math.ceil((new Date(iso).getTime() - Date.now()) / millisecondsPerDay);
}

/** How urgent a submission deadline is -- what the deadline pill colors itself by. */
export type DeadlineUrgency = "none" | "closed" | "critical" | "soon" | "comfortable";

export function deadlineUrgency(days: number | null): DeadlineUrgency {
  if (days === null) return "none";
  if (days < 0) return "closed";
  if (days <= 3) return "critical";
  if (days <= 7) return "soon";
  return "comfortable";
}

/** "quedan 4 días" / "vence hoy" / "quedó cerrado", said the way a person would. */
export function deadlineText(days: number | null): string {
  if (days === null) return "Sin plazo publicado";
  if (days < 0) return "Plazo cerrado";
  if (days === 0) return "Vence hoy";
  if (days === 1) return "Queda 1 día";
  return `Quedan ${days} días`;
}

/** Elapsed seconds as `m:ss`, for the analysis timer. */
export function formatElapsed(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const rest = Math.floor(seconds % 60);
  return `${minutes}:${rest.toString().padStart(2, "0")}`;
}
