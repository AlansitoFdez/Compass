/**
 * How many of the model's citations were found verbatim in the pliego.
 *
 * A bar rather than the sentence of small grey text it used to be. This number is the
 * evidence behind the project's central claim -- that the answer is auditable by
 * construction rather than trusted -- so burying it in a caption undersold the one thing
 * that distinguishes this from asking a chatbot.
 */
export function FaithfulnessMeter({ value }: { value: number }) {
  const percentage = Math.round(value * 100);

  return (
    <div className="mt-4">
      <div className="flex items-baseline justify-between gap-3">
        <p className="field-label">Fidelidad de citas</p>
        <p className="tabular text-sm font-semibold">{percentage}%</p>
      </div>
      <div
        className="mt-1.5 h-1.5 overflow-hidden rounded-sm bg-surface-muted"
        role="meter"
        aria-valuenow={percentage}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Porcentaje de citas verificadas literalmente en el pliego"
      >
        <div
          className={`h-full rounded-sm ${
            percentage === 100 ? "bg-verdict-pass" : "bg-verdict-warn"
          }`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <p className="mt-1.5 text-xs leading-relaxed text-muted">
        Proporción de citas que se encontraron literalmente en el texto del pliego,
        comprobado en Python — no por el modelo.
      </p>
    </div>
  );
}
