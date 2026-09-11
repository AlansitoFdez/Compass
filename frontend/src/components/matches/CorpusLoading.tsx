"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { getMatches } from "@/lib/api";
import { formatCount } from "@/lib/format";

// The backfill downloads three ~200MB monthly archives and parses them entry by entry, so
// this runs for minutes. Five seconds is often enough to see the number move, which is the
// whole point: the alternative was a screen that looked broken.
const POLL_INTERVAL_MS = 5000;

/**
 * The corpus filling up, watched while it happens.
 *
 * There is no result backend and no progress API, and none is needed: `funnel.total` is
 * the number of tenders in the database, so it climbs on its own as the load proceeds.
 * Reusing that instead of building a progress endpoint keeps the moving part in one place
 * -- the count is the same one the funnel summary shows once the load is done.
 */
export function CorpusLoading({ initialTotal }: { initialTotal: number }) {
  const router = useRouter();
  const [total, setTotal] = useState(initialTotal);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    const tick = async () => {
      try {
        const { funnel, items } = await getMatches(1);
        if (cancelled) return;
        setTotal(funnel.total);
        // Once something actually matches the profile, the real screen has content to
        // show, so hand back to the server render instead of polling forever.
        if (items.length > 0) {
          router.refresh();
          return;
        }
      } catch {
        // A failed poll says nothing about the load, which runs in the worker. Keep going.
        if (cancelled) return;
      }
      timer = setTimeout(tick, POLL_INTERVAL_MS);
    };

    timer = setTimeout(tick, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [router]);

  return (
    <Card className="p-6" aria-live="polite">
      <div className="flex items-center gap-3">
        <span className="h-2 w-2 animate-pulse rounded-full bg-accent" aria-hidden="true" />
        <p className="text-base font-medium">Descargando licitaciones de PLACSP</p>
      </div>
      <p className="tabular mt-3 text-3xl font-semibold">{formatCount(total)}</p>
      <p className="field-label mt-0.5">Licitaciones ingeridas</p>
      <p className="mt-4 max-w-prose text-sm leading-relaxed text-muted">
        Se están cargando los últimos tres meses del vertical de servicios informáticos.
        Tarda unos minutos y el número sube solo — puedes cerrar esta página, el trabajo
        sigue en el worker.
      </p>
      <p className="mt-2 max-w-prose text-xs leading-relaxed text-muted">
        Si el número no se mueve, comprueba que el worker de Celery está corriendo: es
        quien hace la descarga.
      </p>
    </Card>
  );
}
