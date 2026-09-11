import type { Match } from "@/lib/api";

/**
 * Why this tender is here at all -- the "motivo de encaje" of the fused ranking.
 *
 * A match found by both recoverers is the strong case; one found only by the vector side
 * is the one a keyword search would have missed entirely, which is the whole argument for
 * the hybrid design (phase 2).
 *
 * Just the chip. The sentence explaining what it means lives once, in `MatchOriginLegend`
 * above the list: nearly every match is "léxico + vectorial", so repeating the same
 * explanation on all twenty cards filled the column with text that says nothing new after
 * the first read.
 *
 * It is not a `title` attribute either, which is what it was before 5.3 -- a tooltip there
 * only appears on hover with a mouse, so the reason the product most wants to explain was
 * the one piece of copy a keyboard or screen-reader user could never reach.
 */
export function MatchOrigin({ match }: { match: Match }) {
  const lexical = match.lexical_rank !== null;
  const vector = match.vector_rank !== null;
  const both = lexical && vector;

  return (
    <span
      className={`shrink-0 rounded-sm border px-2 py-0.5 text-xs font-medium ${
        both
          ? "border-accent/40 bg-accent-soft text-accent"
          : "border-border bg-surface-muted text-muted"
      }`}
    >
      {both ? "Léxico + vectorial" : lexical ? "Solo léxico" : "Solo vectorial"}
    </span>
  );
}

/**
 * What the chips on the cards below mean, said once.
 *
 * Placed with the list controls rather than in each card, because the distinction is a
 * property of the ranking as a whole -- and because the vector-only case is the evidence
 * for the hybrid design, which deserves a sentence rather than a repeated caption.
 */
export function MatchOriginLegend() {
  return (
    <p className="max-w-prose text-xs leading-relaxed text-muted">
      <span className="font-medium text-foreground">Léxico + vectorial</span> significa que
      lo encontraron los dos recuperadores: coinciden las palabras del título y el
      significado. <span className="font-medium text-foreground">Solo vectorial</span> es el
      caso interesante — comparte significado sin compartir las palabras, así que una
      búsqueda por palabras clave lo habría perdido.
    </p>
  );
}
