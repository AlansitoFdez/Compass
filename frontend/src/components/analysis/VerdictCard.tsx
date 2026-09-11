import { CitationBlock } from "@/components/analysis/CitationBlock";
import { FaithfulnessMeter } from "@/components/analysis/FaithfulnessMeter";
import type { Verdict, VerdictResult } from "@/lib/api";
import { verdictLabel, verdictSummary } from "@/lib/format";

/**
 * The verdict, given the weight it earns.
 *
 * This is the product: a deterministic APTO / APTO CON RESERVAS / NO APTO computed in
 * Python from the extraction against the provider's profile, with every reason traceable
 * to the clause that caused it. Until 5.3 it rendered as one more box of the same size as
 * everything around it, inside a panel below the fold.
 *
 * The three colors come from the verdict tokens, not from the accent: the accent means
 * "interactive" everywhere else in the app, and reusing it for APTO would make the two
 * meanings indistinguishable.
 */
const STYLES: Record<Verdict, { frame: string; text: string; dot: string }> = {
  apto: {
    frame: "border-verdict-pass/40 bg-verdict-pass-soft",
    text: "text-verdict-pass",
    dot: "bg-verdict-pass",
  },
  apto_con_reservas: {
    frame: "border-verdict-warn/40 bg-verdict-warn-soft",
    text: "text-verdict-warn",
    dot: "bg-verdict-warn",
  },
  no_apto: {
    frame: "border-verdict-fail/40 bg-verdict-fail-soft",
    text: "text-verdict-fail",
    dot: "bg-verdict-fail",
  },
};

export function VerdictCard({
  verdict,
  citationFaithfulness,
}: {
  verdict: VerdictResult;
  citationFaithfulness: number | null;
}) {
  const style = STYLES[verdict.verdict];

  return (
    <section
      aria-labelledby="verdict-heading"
      className={`rounded-lg border p-5 sm:p-6 ${style.frame}`}
    >
      <p className="field-label">Veredicto contra tu perfil</p>
      <h2
        id="verdict-heading"
        className={`mt-1 flex items-center gap-2.5 text-2xl font-semibold tracking-tight ${style.text}`}
      >
        <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${style.dot}`} aria-hidden="true" />
        {verdictLabel(verdict.verdict)}
      </h2>
      <p className="mt-1.5 text-sm text-foreground">{verdictSummary(verdict.verdict)}</p>

      {verdict.reasons.length > 0 ? (
        <ol className="mt-5 space-y-4">
          {verdict.reasons.map((reason, index) => (
            <li
              key={`${index}-${reason.detail.slice(0, 24)}`}
              className="rounded-md border border-border bg-surface p-4"
            >
              <p className="text-sm font-medium">{reason.detail}</p>
              <CitationBlock citation={reason.citation} />
            </li>
          ))}
        </ol>
      ) : null}

      {citationFaithfulness !== null ? (
        <FaithfulnessMeter value={citationFaithfulness} />
      ) : null}

      <p className="mt-4 border-t border-border pt-3 text-xs leading-relaxed text-muted">
        El modelo sólo extrae lo que dice el pliego. Este veredicto lo calcula el código,
        comparando esos datos con tu perfil — es determinista y se recalcula en cada
        lectura.
      </p>
    </section>
  );
}
