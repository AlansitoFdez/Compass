/**
 * One function per API endpoint. Nothing here knows about transport or rendering.
 */

import { ApiError, request } from "@/lib/api/client";
import type {
  AnalysisResult,
  Capabilities,
  MatchList,
  Provider,
  Tender,
} from "@/lib/api/types";

/**
 * How an expediente is written into a URL.
 *
 * Real PLACSP expedientes carry slashes (`2026/SSV/000804`) and spaces (407 of the
 * corpus), so each segment is encoded while the slashes stay separators -- that is the
 * shape the API's own `{expediente:path}` routes expect. Exported because the same
 * encoding has to be used by every `<Link>` to a tender page: before 5.3 the links
 * interpolated the raw string and only worked because browsers normalize it.
 */
export function tenderPath(expediente: string): string {
  return expediente.split("/").map(encodeURIComponent).join("/");
}

/** The href of a tender's own page. */
export function tenderHref(expediente: string): string {
  return `/tenders/${tenderPath(expediente)}`;
}

export function getMatches(limit = 20): Promise<MatchList> {
  return request(`/matches?limit=${limit}`);
}

export function getTender(expediente: string): Promise<Tender> {
  return request(`/tenders/${tenderPath(expediente)}`);
}

/** The current analysis, or `null` when this tender has never been analyzed (a real 404). */
export async function getAnalysis(
  expediente: string,
): Promise<AnalysisResult | null> {
  try {
    return await request<AnalysisResult>(
      `/tenders/${tenderPath(expediente)}/analysis`,
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

/** Enqueues an analysis. The API answers 202 and the result is only observable by polling. */
export function triggerAnalysis(expediente: string): Promise<{ detail: string }> {
  return request(`/tenders/${tenderPath(expediente)}/analyze`, {
    method: "POST",
  });
}

/** The saved profile, or `null` when nothing has been saved yet (a fresh install). */
export async function getProvider(): Promise<Provider | null> {
  try {
    return await request<Provider>("/provider");
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

/** Saves the whole profile. A PUT: the form always sends every field. */
export function saveProvider(profile: Provider): Promise<Provider> {
  return request("/provider", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });
}

/** Enqueues the initial corpus load. Answers 202; progress is watched via `getMatches`. */
export function triggerBackfill(): Promise<{ detail: string }> {
  return request("/ingestion/backfill", { method: "POST" });
}

/** What this installation can do, given its configuration. */
export function getCapabilities(): Promise<Capabilities> {
  return request("/capabilities");
}
