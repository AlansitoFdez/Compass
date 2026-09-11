import type { AnalysisStatus } from "@/lib/api";
import { formatElapsed } from "@/lib/format";

/**
 * What is happening during the one to five minutes an analysis takes.
 *
 * Before 5.3 this was an 8px dot that pulsed, plus a sentence saying it takes a while.
 * With no elapsed time and no sense of progress there was no way to tell "running
 * normally" from "the worker died" -- which is a real state the backend can be in, and the
 * one 5.2's stale-run handling exists for.
 *
 * The phases are the graph's own nodes (`analysis/graph.py`: fetch → check_text_layer →
 * extract → verify). The backend reports only `pending` / `in_progress`, not which node is
 * running, so this does not pretend to know: everything up to `extract` is shown as
 * reached once the run is in progress, and `extract` is marked as the current step because
 * it is where essentially all of the time goes. Claiming per-node precision the API cannot
 * provide would be a worse lie than showing none.
 */
const PHASES = [
  { key: "fetch", label: "Descargar el pliego" },
  { key: "read", label: "Leer el PDF" },
  { key: "extract", label: "Extraer los requisitos" },
  { key: "verify", label: "Verificar las citas" },
] as const;

export function AnalysisProgress({
  status,
  elapsedSeconds,
}: {
  status: AnalysisStatus;
  elapsedSeconds: number;
}) {
  const queued = status === "pending";
  // Everything before `extract` is fast enough that a run reported as in progress has
  // almost certainly passed it; `verify` only happens once the model has answered.
  const currentIndex = queued ? -1 : 2;

  return (
    <div
      // The panel updates itself while the reader watches, so the change has to be
      // announced. "polite" rather than "assertive": it should not interrupt whatever a
      // screen reader is already saying.
      aria-live="polite"
      aria-busy="true"
      className="rounded-md border border-border bg-surface-muted p-4"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="flex items-center gap-2 text-sm font-medium">
          <span className="h-2 w-2 animate-pulse rounded-full bg-accent" aria-hidden="true" />
          {queued ? "En cola" : "Analizando el pliego"}
        </p>
        <p className="tabular font-mono text-sm text-muted">
          {formatElapsed(elapsedSeconds)}
        </p>
      </div>

      <ol className="mt-3 space-y-1.5">
        {PHASES.map((phase, index) => {
          const done = index < currentIndex;
          const current = index === currentIndex;
          return (
            <li
              key={phase.key}
              className={`flex items-center gap-2 text-sm ${
                done || current ? "text-foreground" : "text-muted"
              }`}
            >
              <span
                className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full border text-[10px] ${
                  done
                    ? "border-accent bg-accent text-white"
                    : current
                      ? "border-accent text-accent"
                      : "border-border text-muted"
                }`}
                aria-hidden="true"
              >
                {done ? "✓" : index + 1}
              </span>
              {phase.label}
              {current ? <span className="text-xs text-muted">· en curso</span> : null}
            </li>
          );
        })}
      </ol>

      <p className="mt-3 text-xs leading-relaxed text-muted">
        Un pliego real tarda entre uno y cinco minutos. Puedes cerrar esta página: el
        análisis sigue en el worker y estará aquí al volver.
      </p>
    </div>
  );
}
