import { daysUntil, deadlineText, deadlineUrgency, formatDate } from "@/lib/format";
import type { DeadlineUrgency } from "@/lib/format";

// Urgency is encoded in color as well as in the number, because "quedan 3 días" and
// "quedan 30 días" look identical when both are plain grey text -- and which of the two
// it is, is the single thing that decides whether this tender is worth opening today.
const STYLES: Record<DeadlineUrgency, string> = {
  critical: "border-verdict-fail/40 bg-verdict-fail-soft text-verdict-fail",
  soon: "border-verdict-warn/40 bg-verdict-warn-soft text-verdict-warn",
  comfortable: "border-border bg-surface-muted text-foreground",
  closed: "border-border bg-surface-muted text-muted",
  none: "border-border bg-surface-muted text-muted",
};

/** The submission deadline, as an urgency-colored pill with the date beside it. */
export function DeadlinePill({
  iso,
  showDate = true,
}: {
  iso: string | null;
  showDate?: boolean;
}) {
  const days = daysUntil(iso);
  const urgency = deadlineUrgency(days);

  return (
    <span className="inline-flex flex-wrap items-baseline gap-x-2 gap-y-1">
      <span
        className={`tabular rounded-sm border px-2 py-0.5 text-xs font-medium ${STYLES[urgency]}`}
      >
        {deadlineText(days)}
      </span>
      {showDate && iso !== null ? (
        // <time>, not plain text: the machine-readable value is what lets a screen reader
        // and any other tool read the date without parsing the Spanish rendering.
        <time dateTime={iso} className="text-xs text-muted">
          {formatDate(iso)}
        </time>
      ) : null}
    </span>
  );
}
