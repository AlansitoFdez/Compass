import Link from "next/link";
import { notFound } from "next/navigation";
import { AnalysisPanel } from "@/components/AnalysisPanel";
import { ApiError, getAnalysis, getTender } from "@/lib/api";
import { daysUntil, formatDate, formatEur, tenderStatusLabel } from "@/lib/format";

// Same reasoning as the list: always live. The analysis status in particular changes
// while the page is being looked at.
export const dynamic = "force-dynamic";

// A catch-all segment, not `[expediente]`: real PLACSP expedientes carry slashes
// (`SER/2026/0000006435`), so a single segment would never match their own URL.
export default async function TenderPage({ params }: PageProps<"/tenders/[...expediente]">) {
  const { expediente: segments } = await params;
  const expediente = segments.map(decodeURIComponent).join("/");

  let tender;
  try {
    tender = await getTender(expediente);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }

  // Read on the server so the panel arrives already knowing the state: no flash of
  // "sin analizar" on a tender that was analyzed days ago.
  const analysis = await getAnalysis(expediente);
  const days = daysUntil(tender.submission_deadline);

  return (
    <div className="space-y-6">
      <div>
        <Link href="/" className="text-sm text-muted hover:text-foreground">
          ← Volver a los matches
        </Link>
        <h1 className="mt-3 text-2xl font-semibold leading-tight tracking-tight">{tender.title}</h1>
        <p className="mt-1 text-sm text-muted">{tender.contracting_body}</p>
        <p className="mt-1 font-mono text-xs text-muted">{tender.expediente}</p>
      </div>

      <section className="rounded-lg border border-border bg-surface p-5">
        <dl className="grid grid-cols-2 gap-x-6 gap-y-4 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted">Importe (con IVA)</dt>
            <dd className="mt-0.5">{formatEur(tender.budget_with_vat)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted">Valor estimado</dt>
            <dd className="mt-0.5">{formatEur(tender.estimated_value)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted">Estado</dt>
            <dd className="mt-0.5">{tenderStatusLabel(tender.status)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted">Fin de presentación</dt>
            <dd className="mt-0.5">
              {formatDate(tender.submission_deadline)}
              {days !== null && days >= 0 ? (
                <span className="text-muted"> · quedan {days} días</span>
              ) : null}
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted">Lugar</dt>
            <dd className="mt-0.5">{tender.location ?? "No indicado"}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted">Procedimiento</dt>
            <dd className="mt-0.5">{tender.procedure_type}</dd>
          </div>
          <div className="col-span-2 sm:col-span-3">
            <dt className="text-xs uppercase tracking-wide text-muted">CPV</dt>
            <dd className="mt-0.5 font-mono text-xs">{tender.cpv_codes.join(" · ")}</dd>
          </div>
        </dl>

        <div className="mt-5 flex flex-wrap gap-4 border-t border-border pt-4 text-sm">
          {tender.pcap_url !== null ? (
            <a
              className="text-accent underline underline-offset-2"
              href={tender.pcap_url}
              target="_blank"
              rel="noreferrer"
            >
              Pliego administrativo (PCAP)
            </a>
          ) : null}
          {tender.ppt_url !== null ? (
            <a
              className="text-accent underline underline-offset-2"
              href={tender.ppt_url}
              target="_blank"
              rel="noreferrer"
            >
              Pliego técnico (PPT)
            </a>
          ) : null}
          {tender.platform_url !== null ? (
            <a
              className="text-accent underline underline-offset-2"
              href={tender.platform_url}
              target="_blank"
              rel="noreferrer"
            >
              Ficha en PLACSP
            </a>
          ) : null}
        </div>
      </section>

      <AnalysisPanel
        expediente={expediente}
        hasPcap={tender.pcap_url !== null}
        initialAnalysis={analysis}
      />
    </div>
  );
}
