import type { Match } from "@/lib/api";

/**
 * Why this tender is here at all -- the "motivo de encaje" of the fused ranking.
 *
 * A match found by both recoverers is the strong case; one found only by the vector side
 * is the one a keyword search would have missed entirely, which is the whole argument for
 * the hybrid design (phase 2).
 *
 * The explanation is rendered as text, not as a `title` attribute. A tooltip in `title`
 * appears only on hover with a mouse: it was unreachable by keyboard, and screen readers
 * treat it inconsistently -- so the reason the product most wants to explain was the one
 * piece of copy some readers could never get to.
 */
export function MatchOrigin({ match }: { match: Match }) {
  const lexical = match.lexical_rank !== null;
  const vector = match.vector_rank !== null;

  const label = lexical && vector ? "Léxico + vectorial" : lexical ? "Solo léxico" : "Solo vectorial";
  const explanation =
    lexical && vector
      ? "Coinciden las palabras del título y el significado."
      : lexical
        ? "Coinciden las palabras del título."
        : "Comparte significado sin compartir las palabras.";

  return (
    <span className="inline-flex flex-col items-end gap-0.5 text-right">
      <span
        className={`rounded-sm border px-2 py-0.5 text-xs font-medium ${
          lexical && vector
            ? "border-accent/40 bg-accent-soft text-accent"
            : "border-border bg-surface-muted text-muted"
        }`}
      >
        {label}
      </span>
      <span className="max-w-[18rem] text-xs leading-snug text-muted">{explanation}</span>
    </span>
  );
}
