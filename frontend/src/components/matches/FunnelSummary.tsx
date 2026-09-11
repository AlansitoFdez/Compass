import type { FunnelCounts } from "@/lib/api";
import { formatCount } from "@/lib/format";

/**
 * The reduction, as numbers, at the top of the screen.
 *
 * This is the product's entire argument -- 3.583 licitaciones down to a handful -- and
 * until 5.3 it appeared nowhere at all: the header said "radar de licitaciones públicas"
 * and the list said "20 resultados del embudo", which was really just the page size
 * (fixed in 5.2). The API now returns the stage counts it was already computing, so the
 * reduction can be shown instead of claimed.
 *
 * Rendered as a sequence with real arrows because the stages are cumulative: each one
 * filters what the previous one left, which is information the reader needs to make sense
 * of why the last number is so much smaller than the first.
 */
export function FunnelSummary({ funnel }: { funnel: FunnelCounts }) {
  const stages = [
    { label: "Ingeridas", value: funnel.total, hint: "Todo el corpus de PLACSP" },
    { label: "En plazo", value: funnel.after_status, hint: "Abiertas a presentación" },
    { label: "Tu CPV", value: funnel.after_cpv, hint: "Comparten algún código contigo" },
    { label: "Tu importe", value: funnel.after_budget, hint: "Dentro de tu rango" },
    { label: "Encajan", value: funnel.after_location, hint: "Lo que llega al ranking" },
  ];

  return (
    <ol className="flex flex-wrap items-stretch gap-x-1 gap-y-2">
      {stages.map((stage, index) => {
        const isLast = index === stages.length - 1;
        return (
          <li key={stage.label} className="flex items-stretch gap-1">
            <div
              className={`rounded-md border px-3 py-2 ${
                isLast
                  ? "border-accent/40 bg-accent-soft"
                  : "border-border bg-surface"
              }`}
            >
              <p
                className={`tabular text-xl font-semibold leading-tight ${
                  isLast ? "text-accent" : "text-foreground"
                }`}
              >
                {formatCount(stage.value)}
              </p>
              <p className="field-label mt-0.5">{stage.label}</p>
              <p className="mt-0.5 text-xs leading-snug text-muted">{stage.hint}</p>
            </div>
            {!isLast ? (
              <span
                className="self-center text-muted"
                // Decorative: the list order already carries the sequence for a screen
                // reader, so the arrow would only add noise.
                aria-hidden="true"
              >
                →
              </span>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
