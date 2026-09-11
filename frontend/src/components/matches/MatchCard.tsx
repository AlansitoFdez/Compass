import Link from "next/link";
import { MatchOrigin } from "@/components/matches/MatchOrigin";
import { DeadlinePill } from "@/components/tenders/DeadlinePill";
import { Card } from "@/components/ui/Card";
import { tenderHref, type Match } from "@/lib/api";
import { formatEur, tenderStatusLabel } from "@/lib/format";

/**
 * One tender in the fused ranking.
 *
 * The hierarchy is the point of the 5.3 rework. Before it, the amount, the deadline, the
 * status and the RRF score sat in four identical grid cells at the same size and weight --
 * but only the first two decide whether a supplier opens a tender at all, and the RRF
 * score is internal diagnostics. So the amount and the deadline get their own line at a
 * readable size, and the rest drops to metadata beside the expediente.
 */
export function MatchCard({ match, position }: { match: Match; position: number }) {
  const { tender } = match;
  const amount = tender.budget_with_vat ?? tender.estimated_value;

  return (
    <Card
      as="li"
      className="p-5 transition-shadow hover:border-accent hover:shadow-lifted"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
            <span className="tabular font-mono">#{position}</span>
            <span aria-hidden="true">·</span>
            <span className="truncate font-mono">{tender.expediente}</span>
            <span aria-hidden="true">·</span>
            <span>{tenderStatusLabel(tender.status)}</span>
          </div>

          <h2 className="mt-1.5 text-lg font-semibold leading-snug tracking-tight">
            <Link
              href={tenderHref(tender.expediente)}
              // The whole card is the affordance, but only the title is the link: a
              // stretched overlay would make the text inside it unselectable.
              className="hover:text-accent"
            >
              {tender.title}
            </Link>
          </h2>
          <p className="mt-1 text-sm text-muted">{tender.contracting_body}</p>
        </div>

        <MatchOrigin match={match} />
      </div>

      <div className="mt-4 flex flex-wrap items-baseline gap-x-6 gap-y-3 border-t border-border pt-4">
        <div>
          <p className="field-label">Importe</p>
          <p className="tabular mt-0.5 text-base font-semibold">{formatEur(amount)}</p>
        </div>
        <div>
          <p className="field-label">Presentación</p>
          <div className="mt-1">
            <DeadlinePill iso={tender.submission_deadline} />
          </div>
        </div>
        <div className="ml-auto text-right">
          <p className="field-label">Score RRF</p>
          <p className="tabular mt-0.5 font-mono text-xs text-muted">
            {match.rrf_score.toFixed(4)}
          </p>
        </div>
      </div>
    </Card>
  );
}
