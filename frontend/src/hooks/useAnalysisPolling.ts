"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getAnalysis, triggerAnalysis, type AnalysisResult } from "@/lib/api";

/**
 * The analysis panel's whole lifecycle: start a run, watch it, give up eventually.
 *
 * Extracted from `AnalysisPanel` in 5.3, which had this tangled with five other
 * responsibilities in one 250-line component. It is also where two of the review's
 * findings land, and both are about the loop's shape rather than its logic.
 */

// The API answers 202 and Celery has no result backend (decided in 3.8), so polling GET
// /analysis is the only way to observe the outcome. Five seconds: a real run takes
// 36-338s against the free tier, so anything tighter is just noise on the worker.
const POLL_INTERVAL_MS = 5000;

// After this, stop asking and hand the decision back to the reader. The backend settles an
// abandoned run as failed once its Redis lock expires (5.2, 900s), so a run still claiming
// to be in progress well past that is one this page will never see finish -- and before
// this cap the panel simply polled forever, with the button hidden the whole time because
// it only appears for "never analyzed" or "failed".
const POLL_TIMEOUT_MS = 15 * 60 * 1000;

export type AnalysisPhase = {
  analysis: AnalysisResult | null;
  isRunning: boolean;
  /** Seconds since this page started watching a run -- what the timer shows. */
  elapsedSeconds: number;
  /** The run outlived `POLL_TIMEOUT_MS` and this page stopped asking. */
  gaveUp: boolean;
  isStarting: boolean;
  error: string | null;
  start: () => void;
};

function isActive(analysis: AnalysisResult | null): boolean {
  return analysis?.status === "pending" || analysis?.status === "in_progress";
}

export function useAnalysisPolling(
  expediente: string,
  initialAnalysis: AnalysisResult | null,
): AnalysisPhase {
  const [analysis, setAnalysis] = useState(initialAnalysis);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [gaveUp, setGaveUp] = useState(false);

  const running = isActive(analysis) && !gaveUp;
  // A ref, not state: the loop below reads it to decide whether to schedule the next tick,
  // and putting it in the dependency array would restart the loop on every tick instead.
  const startedAtRef = useRef<number | null>(null);

  useEffect(() => {
    if (!running) {
      startedAtRef.current = null;
      return;
    }
    if (startedAtRef.current === null) startedAtRef.current = Date.now();

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    // A self-rescheduling timeout, not setInterval. An interval fires on the clock
    // regardless of whether the previous request came back, so a poll slower than the
    // interval stacks requests on a worker that is already busy. This waits for each
    // answer before asking again.
    const tick = async () => {
      try {
        const next = await getAnalysis(expediente);
        if (cancelled) return;
        setAnalysis(next);
        if (!isActive(next)) return;
      } catch {
        // A failed poll is not a failed analysis -- the worker keeps going, and the next
        // tick reads the same row again. Surfacing it here would be wrong; the panel stays
        // on "analizando".
        if (cancelled) return;
      }

      const startedAt = startedAtRef.current;
      if (startedAt !== null && Date.now() - startedAt > POLL_TIMEOUT_MS) {
        setGaveUp(true);
        return;
      }
      timer = setTimeout(tick, POLL_INTERVAL_MS);
    };

    timer = setTimeout(tick, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [running, expediente]);

  // Separate from the poll so the timer advances every second while the panel waits five
  // for the next answer -- a counter that only moved on each poll would look stuck.
  useEffect(() => {
    // No reset here when the run ends: setting state synchronously in an effect body
    // cascades a render for nothing, and the counter isn't displayed unless a run is in
    // progress. `start` clears it instead, which is the only moment a stale value could
    // otherwise be seen.
    if (!running) return;
    const started = startedAtRef.current ?? Date.now();
    const ticker = setInterval(
      () => setElapsedSeconds(Math.floor((Date.now() - started) / 1000)),
      1000,
    );
    return () => clearInterval(ticker);
  }, [running]);

  const start = useCallback(() => {
    void (async () => {
      setIsStarting(true);
      setError(null);
      setGaveUp(false);
      setElapsedSeconds(0);
      try {
        await triggerAnalysis(expediente);
        // Show "en cola" immediately instead of waiting for the first poll: the row may
        // not exist yet at all, so a poll right now could still legitimately 404.
        startedAtRef.current = Date.now();
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
          "No se pudo encolar el análisis. Comprueba que la API y el worker de Celery están corriendo.",
        );
      } finally {
        setIsStarting(false);
      }
    })();
  }, [expediente]);

  return {
    analysis,
    isRunning: running,
    elapsedSeconds,
    gaveUp,
    isStarting,
    error,
    start,
  };
}
