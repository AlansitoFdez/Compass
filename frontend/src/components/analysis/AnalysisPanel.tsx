"use client";

import { AnalysisProgress } from "@/components/analysis/AnalysisProgress";
import { ExtractionList } from "@/components/analysis/ExtractionList";
import { VerdictCard } from "@/components/analysis/VerdictCard";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useAnalysisPolling } from "@/hooks/useAnalysisPolling";
import type { AnalysisResult } from "@/lib/api";

/**
 * The pliego analysis, in whatever state it is in.
 *
 * Composition only since 5.3: the polling lifecycle moved to `useAnalysisPolling`, and the
 * verdict, the extraction and the progress each became their own component. What is left
 * here is the decision of *which* of them to show, which is the part that actually belongs
 * to a panel.
 *
 * It renders the verdict *above* its own card rather than inside it: once there is an
 * answer, the answer is the thing to lead with. Both live in this component because the
 * verdict arrives through the same polling the panel does -- the server only knows the
 * state at first render, and the run usually finishes minutes later.
 */
export function AnalysisPanel({
  expediente,
  hasPcap,
  initialAnalysis,
  canAnalyze,
}: {
  expediente: string;
  hasPcap: boolean;
  initialAnalysis: AnalysisResult | null;
  /** Whether this installation has an OpenRouter key. See `GET /capabilities`. */
  canAnalyze: boolean;
}) {
  const {
    analysis,
    isRunning,
    elapsedSeconds,
    gaveUp,
    isStarting,
    error,
    start,
  } = useAnalysisPolling(expediente, initialAnalysis);

  // Said before anyone clicks, not after a 503 comes back. The key is optional on
  // purpose (5.5) so Compass runs with nothing configured; this is the one screen where
  // that choice is visible, so it has to explain itself rather than look broken.
  if (!canAnalyze) {
    return (
      <Card as="section" className="p-5">
        <h2 className="text-sm font-semibold">Análisis del pliego</h2>
        <p className="mt-2 max-w-prose text-sm text-muted">
          Para leer el pliego y calcular el veredicto hace falta una clave de OpenRouter,
          que es gratuita. Añade{" "}
          <code className="font-mono text-xs text-foreground">OPENROUTER_API_KEY</code> a{" "}
          <code className="font-mono text-xs text-foreground">backend/.env</code> y reinicia
          Compass. Todo lo demás —la ingesta, el embudo y este listado— funciona sin ella.
        </p>
      </Card>
    );
  }

  if (!hasPcap) {
    return (
      <Card as="section" className="p-5">
        <h2 className="text-sm font-semibold">Análisis del pliego</h2>
        <p className="mt-2 text-sm text-muted">
          Esta licitación no publica un PCAP descargable, así que no hay nada
          que analizar.
        </p>
      </Card>
    );
  }

  // The button appears for every state the reader can act on -- and `gaveUp` is one of
  // them. Before 5.3 it showed only for "never analyzed" and "failed", so a run this page
  // had stopped watching left no way forward at all.
  const canStart = analysis === null || analysis.status === "failed" || gaveUp;
  const buttonLabel = isStarting
    ? "Encolando…"
    : analysis === null
      ? "Analizar pliego"
      : "Reintentar";

  const verdict =
    analysis?.status === "completed" && analysis.verdict !== null
      ? analysis.verdict
      : null;

  return (
    <div className="space-y-4">
      {verdict !== null ? (
        <VerdictCard
          verdict={verdict}
          citationFaithfulness={analysis?.citation_faithfulness ?? null}
        />
      ) : null}

      <Card as="section" className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-semibold">Análisis del pliego</h2>
          {canStart ? (
            <Button type="button" onClick={start} disabled={isStarting}>
              {buttonLabel}
            </Button>
          ) : null}
        </div>

        {error !== null ? (
          <p
            role="alert"
            className="mt-3 rounded-sm border border-verdict-fail/40 bg-verdict-fail-soft px-3 py-2 text-sm text-verdict-fail"
          >
            {error}
          </p>
        ) : null}

        {analysis === null ? (
          <p className="mt-2 max-w-prose text-sm text-muted">
            Nadie ha pedido todavía el análisis de este pliego. El agente lo
            descarga, lo lee y extrae los requisitos con su cita; el veredicto
            lo calcula después el código, comparando con tu perfil.
          </p>
        ) : (
          <div className="mt-4">
            {isRunning ? (
              <AnalysisProgress
                status={analysis.status}
                elapsedSeconds={elapsedSeconds}
              />
            ) : null}

            {gaveUp ? (
              <div className="rounded-md border border-verdict-warn/40 bg-verdict-warn-soft p-4 text-sm">
                <p className="font-medium text-verdict-warn">
                  Este análisis lleva demasiado tiempo en curso
                </p>
                <p className="mt-1 text-muted">
                  Hemos dejado de consultarlo. Lo más probable es que el worker
                  de Celery se haya parado a mitad. Comprueba que sigue
                  corriendo y vuelve a lanzarlo.
                </p>
              </div>
            ) : null}

            {analysis.status === "completed" ? (
              <>
                {analysis.verdict === null ? (
                  <p className="text-sm text-muted">
                    El pliego se leyó correctamente, pero no hay un perfil de
                    proveedor sembrado con el que compararlo, así que no hay
                    veredicto.
                  </p>
                ) : null}
                {analysis.extraction !== null ? (
                  <ExtractionList extraction={analysis.extraction} />
                ) : null}
              </>
            ) : null}

            {(analysis.status === "failed" ||
              analysis.status === "not_analyzable") &&
            !gaveUp ? (
              <div
                className={`rounded-md border p-4 text-sm ${
                  analysis.status === "not_analyzable"
                    ? "border-border bg-surface-muted"
                    : "border-verdict-fail/40 bg-verdict-fail-soft"
                }`}
              >
                <p
                  className={`font-medium ${
                    analysis.status === "not_analyzable"
                      ? ""
                      : "text-verdict-fail"
                  }`}
                >
                  {analysis.status === "not_analyzable"
                    ? "Pliego no analizable"
                    : "El análisis falló"}
                </p>
                <p className="mt-1 text-muted">
                  {analysis.error_message ??
                    "El PDF no tiene capa de texto: es un escaneo, y esta versión no hace OCR a propósito."}
                </p>
              </div>
            ) : null}
          </div>
        )}
      </Card>
    </div>
  );
}
