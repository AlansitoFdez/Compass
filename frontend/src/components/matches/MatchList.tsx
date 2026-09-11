"use client";

import { useMemo, useState } from "react";
import { MatchCard } from "@/components/matches/MatchCard";
import { MatchOriginLegend } from "@/components/matches/MatchOrigin";
import { EmptyState } from "@/components/ui/EmptyState";
import type { Match } from "@/lib/api";
import { daysUntil } from "@/lib/format";

/**
 * The ranked list, with the one control it was missing.
 *
 * Sorting happens in the browser over the page the server already sent: the fused ranking
 * is what the funnel is *for*, so re-ranking on the server would mean asking it a
 * different question. Reordering twenty rows the reader already has costs nothing and
 * answers the question they actually have next ("which of these closes first?").
 *
 * The RRF order is kept as the default and named as such, so the reordering never hides
 * what the product's own ranking said.
 */
type SortKey = "rrf" | "deadline" | "amount";

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: "rrf", label: "Mejor encaje" },
  { key: "deadline", label: "Cierra antes" },
  { key: "amount", label: "Mayor importe" },
];

function amountOf(match: Match): number {
  const raw = match.tender.budget_with_vat ?? match.tender.estimated_value;
  if (raw === null) return -1;
  const value = Number(raw);
  return Number.isNaN(value) ? -1 : value;
}

/** Days to the deadline, with "no deadline" sorted last rather than first. */
function deadlineOf(match: Match): number {
  const days = daysUntil(match.tender.submission_deadline);
  return days === null ? Number.POSITIVE_INFINITY : days;
}

export function MatchList({ matches }: { matches: Match[] }) {
  const [sort, setSort] = useState<SortKey>("rrf");

  const sorted = useMemo(() => {
    if (sort === "rrf") return matches;
    const copy = [...matches];
    if (sort === "deadline") {
      // Already-closed tenders (negative days) go last: they sort before everything else
      // numerically, but they are the least useful thing to put at the top.
      return copy.sort((a, b) => {
        const left = deadlineOf(a);
        const right = deadlineOf(b);
        if (left < 0 && right >= 0) return 1;
        if (right < 0 && left >= 0) return -1;
        return left - right;
      });
    }
    return copy.sort((a, b) => amountOf(b) - amountOf(a));
  }, [matches, sort]);

  if (matches.length === 0) {
    return (
      <EmptyState title="El ranking no ha devuelto ninguna licitación">
        Sobreviven licitaciones al embudo, pero ninguna comparte vocabulario ni significado
        con la descripción de tu perfil. Ajustar esa descripción es lo que mueve este
        resultado.
      </EmptyState>
    );
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted">
          {matches.length} {matches.length === 1 ? "licitación" : "licitaciones"} en pantalla
        </p>
        <div className="flex items-center gap-1.5">
          <span id="sort-label" className="field-label">
            Ordenar por
          </span>
          <div role="group" aria-labelledby="sort-label" className="flex gap-1">
            {SORT_OPTIONS.map((option) => (
              <button
                key={option.key}
                type="button"
                onClick={() => setSort(option.key)}
                aria-pressed={sort === option.key}
                className={`rounded-sm border px-2.5 py-1 text-xs font-medium transition-colors ${
                  sort === option.key
                    ? "border-accent bg-accent-soft text-accent"
                    : "border-border bg-surface text-muted hover:border-accent"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="mb-4">
        <MatchOriginLegend />
      </div>

      <ul className="space-y-3">
        {sorted.map((match, index) => (
          <MatchCard
            key={match.tender.expediente}
            match={match}
            // The position follows the displayed order, not the RRF rank: a "#1" that
            // stayed pinned to a card halfway down the list after sorting would be
            // reporting something the reader can't see.
            position={index + 1}
          />
        ))}
      </ul>
    </div>
  );
}
