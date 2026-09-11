"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getAnalysis,
  triggerAnalysis,
  type AnalysisResult,
  type PliegoExtraction,
  type Verdict,
} from "@/lib/api";
import { CitationBlock } from "@/components/Citation";
import { analysisStatusLabel, formatEur, verdictLabel } from "@/lib/format";

// The API answers 202 and Celery has no result backend (decided in 3.8), so polling
// GET /analysis is the only way to observe the outcome. Five seconds: a real run takes
// 36-338s against the free tier, so anything tighter is just noise on the worker.
const POLL_INTERVAL_MS = 5000;

const VERDICT_STYLES: Record<Verdict, string> = {
  apto: "border-accent bg-accent-soft text-accent",
  apto_con_reservas: "border-amber-500 bg-amber-500/10 text-amber-600 dark:text-amber-400",
  no_apto: "border-red-500 bg-red-500/10 text-red-600 dark:text-red-400",
};

function ExtractionField({
  label,
  value,
  citation,
}: {
  label: string;
  value: string;
  citation: PliegoExtraction["economic_solvency"]["citation"];
}) {
  return (
    <div className="border-t border-border py-3">
      <h4 className="text-xs uppercase tracking-wide text-muted">{label}</h4>
      <p className="mt-1 text-sm">{value}</p>
      <CitationBlock citation={citation} />
    </div>
  );
}

function Extraction({ extraction }: { extraction: PliegoExtraction }) {
  const price = extraction.award_criteria.criteria.find((criterion) => criterion.is_price);
  return (
    <div className="mt-6">
      <h3 className="text-sm font-semibold">Lo que dice el pliego</h3>
      <ExtractionField
        label="Solvencia económica"
        value={
          extraction.economic_solvency.minimum_annual_turnover_eur !== null
            ? `Cifra de negocio mínima: ${formatEur(extraction.economic_solvency.minimum_annual_turnover_eur)}`
            : extraction.economic_solvency.description || "No se exige una cifra concreta."
        }
        citation={extraction.economic_solvency.citation}
      />
      <ExtractionField
        label="Solvencia técnica"
        value={
          extraction.technical_solvency.minimum_amount_eur !== null
            ? `Importe mínimo en trabajos similares: ${formatEur(extraction.technical_solvency.minimum_amount_eur)}`
            : extraction.technical_solvency.description || "No se exige un importe concreto."
        }
        citation={extraction.technical_solvency.citation}
      />
      <ExtractionField
        label="Certificaciones exigidas"
        value={
          extraction.certifications.length > 0
            ? extraction.certifications.join(" · ")
            : "Ninguna."
        }
        citation={extraction.certifications_citation}
      />
      <ExtractionField
        label="Criterios de adjudicación"
        value={
          price !== undefined
            ? `${extraction.award_criteria.total_points} puntos en total, ${price.points} al precio.`
            : `${extraction.award_criteria.total_points} puntos en total.`
        }
        citation={extraction.award_criteria.citation}
      />
      <ExtractionField
        label="Garantías"
        value={
          extraction.guarantees.description ||
          (extraction.guarantees.provisional_required
            ? "Se exige garantía provisional."
            : "Sin garantía provisional.")
        }
        citation={extraction.guarantees.citation}
      />
      <ExtractionField
        label="Plazo de ejecución"
        value={extraction.execution_deadline.description || "No indicado."}
        citation={extraction.execution_deadline.citation}
      />
      <ExtractionField
        label="Lotes"
        value={
          extraction.lots.divided_into_lots
            ? extraction.lots.description || "Dividido en lotes."
            : "No está dividido en lotes."
        }
        citation={extraction.lots.citation}
      />
    </div>
  );
}

function VerdictCard({ analysis }: { analysis: AnalysisResult }) {
  const verdict = analysis.verdict;
  if (verdict === null) return null;
  return (
    <div className={`rounded-lg border p-4 ${VERDICT_STYLES[verdict.verdict]}`}>
      <p className="text-lg font-semibold tracking-tight">{verdictLabel(verdict.verdict)}</p>
      {verdict.reasons.length === 0 ? (
        <p className="mt-1 text-sm">
          Ningún requisito del pliego bloquea ni condiciona tu candidatura.
        </p>
      ) : (
        <ul className="mt-3 space-y-3">
          {verdict.reasons.map((reason, index) => (
            <li key={index} className="text-sm">
              <p className="font-medium">{reason.detail}</p>
              <CitationBlock citation={reason.citation} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function AnalysisPanel({
  expediente,
  hasPcap,
  initialAnalysis,
}: {
  expediente: string;
  hasPcap: boolean;
  initialAnalysis: AnalysisResult | null;
}) {
  const [analysis, setAnalysis] = useState(initialAnalysis);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isRunning = analysis?.status === "pending" || analysis?.status === "in_progress";

  useEffect(() => {
    if (!isRunning) return;
    const id = setInterval(async () => {
      try {
        setAnalysis(await getAnalysis(expediente));
      } catch {
        // A failed poll is not a failed analysis -- the worker keeps going, and the
        // next tick reads the same row again. Surfacing it as an error here would be
        // wrong; the panel just stays on "analizando".
      }
    }, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [isRunning, expediente]);

  const start = useCallback(async () => {
    setIsStarting(true);
    setError(null);
    try {
      await triggerAnalysis(expediente);
      // Show "en cola" immediately instead of waiting for the first poll: the row may
      // not exist yet at all, so a poll right now could still legitimately 404.
      setAnalysis({
        expediente,
        status: "pending",
        extraction: null,
        citation_faithfulness: null,
        error_message: null,
        verdict: null,
      });
    } catch {
      setError(
        "No se pudo encolar el análisis. ¿Está la API levantada y el worker de Celery corriendo?",
      );
    } finally {
      setIsStarting(false);
    }
  }, [expediente]);

  if (!hasPcap) {
    return (
      <section className="rounded-lg border border-border bg-surface p-5">
        <h2 className="text-sm font-semibold">Análisis del pliego</h2>
        <p className="mt-2 text-sm text-muted">
          Esta licitación no publica un PCAP descargable, así que no hay nada que analizar.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-border bg-surface p-5">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-sm font-semibold">Análisis del pliego</h2>
        {analysis === null || analysis.status === "failed" ? (
          <button
            type="button"
            onClick={start}
            disabled={isStarting}
            className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white disabled:opacity-60"
          >
            {isStarting ? "Encolando…" : analysis === null ? "Analizar pliego" : "Reintentar"}
          </button>
        ) : null}
      </div>

      {error !== null ? <p className="mt-3 text-sm text-red-500">{error}</p> : null}

      {analysis === null ? (
        <p className="mt-2 text-sm text-muted">
          Nadie ha pedido todavía el análisis de este pliego. El agente lo descarga, lo lee y
          extrae los requisitos con su cita; el veredicto lo calcula después el código, comparando
          con tu perfil.
        </p>
      ) : (
        <div className="mt-4">
          {isRunning ? (
            <p className="flex items-center gap-2 text-sm text-muted">
              <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-accent" />
              {analysisStatusLabel(analysis.status)} Un pliego real tarda entre 1 y 5 minutos.
            </p>
          ) : null}

          {analysis.status === "completed" ? (
            <>
              <VerdictCard analysis={analysis} />
              {analysis.citation_faithfulness !== null ? (
                <p className="mt-3 text-xs text-muted">
                  Fidelidad de citas: {(analysis.citation_faithfulness * 100).toFixed(0)}% de las
                  citas se encontraron literalmente en el texto del pliego, comprobado en Python.
                </p>
              ) : null}
              {analysis.extraction !== null ? (
                <Extraction extraction={analysis.extraction} />
              ) : null}
            </>
          ) : null}

          {analysis.status === "failed" || analysis.status === "not_analyzable" ? (
            <div className="rounded-md border border-border bg-surface-muted p-3 text-sm">
              <p className="font-medium">{analysisStatusLabel(analysis.status)}</p>
              <p className="mt-1 text-muted">
                {analysis.status === "not_analyzable"
                  ? "El PDF no tiene capa de texto: es un escaneo, y esta versión no hace OCR a propósito."
                  : (analysis.error_message ?? "Sin detalle del error.")}
              </p>
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}
