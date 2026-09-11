import type { Citation } from "@/lib/api";

/**
 * A quote from the pliego, with the clause and page it came from.
 *
 * Every extracted field carries one of these, and showing it is the point: the whole
 * design rests on an answer being checkable against the document, not trusted because
 * a model said it (phase 3.5's `verify_citation` checks the same quote in Python).
 */
export function CitationBlock({ citation }: { citation: Citation | null }) {
  if (citation === null) {
    return <p className="mt-1 text-xs text-muted">Sin cita: el pliego no lo indica.</p>;
  }
  return (
    <figure className="mt-2 border-l-2 border-accent bg-surface-muted px-3 py-2">
      <blockquote className="text-sm italic leading-relaxed">“{citation.quote}”</blockquote>
      <figcaption className="mt-1 font-mono text-xs text-muted">
        Cláusula {citation.clause} · página {citation.page}
      </figcaption>
    </figure>
  );
}
