import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { AnalysisPanel } from "@/components/analysis/AnalysisPanel";
import { TenderDocuments } from "@/components/tenders/TenderDocuments";
import { TenderFacts } from "@/components/tenders/TenderFacts";
import { ApiError, getAnalysis, getCapabilities, getTender } from "@/lib/api";

// Same reasoning as the list: always live. The analysis status in particular changes while
// the page is being looked at.
export const dynamic = "force-dynamic";

// A catch-all segment, not `[expediente]`: real PLACSP expedientes carry slashes
// (`2026/SSV/000804`), so a single segment would never match their own URL.
function expedienteFrom(segments: string[]): string {
  return segments.map(decodeURIComponent).join("/");
}

/**
 * The tab title and link preview name the tender, not the product.
 *
 * Every page shared the root layout's metadata until 5.3, so a link to a specific
 * licitación previewed as "Compass — radar de licitaciones públicas" and said nothing
 * about which one -- which is most of the value of sharing it.
 */
export async function generateMetadata({
  params,
}: PageProps<"/tenders/[...expediente]">): Promise<Metadata> {
  const { expediente: segments } = await params;
  const expediente = expedienteFrom(segments);

  try {
    const tender = await getTender(expediente);
    return {
      title: `${tender.title} — Compass`,
      description: `${tender.contracting_body} · expediente ${tender.expediente}`,
    };
  } catch {
    // A title is not worth failing a page render over, and `notFound()` from here would
    // pre-empt the page's own handling of the same case.
    return { title: `${expediente} — Compass` };
  }
}

export default async function TenderPage({
  params,
}: PageProps<"/tenders/[...expediente]">) {
  const { expediente: segments } = await params;
  const expediente = expedienteFrom(segments);

  let tender;
  try {
    tender = await getTender(expediente);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }

  // Both read on the server so the panel arrives already knowing the state: no flash of
  // "sin analizar" on a tender that was analyzed days ago, and no button offered on an
  // installation that has no key to honour it with.
  const [analysis, capabilities] = await Promise.all([
    getAnalysis(expediente),
    getCapabilities(),
  ]);

  return (
    <div className="space-y-4">
      <div>
        <Link href="/" className="text-sm text-muted hover:text-foreground">
          ← Volver a los matches
        </Link>
        <h1 className="mt-3 text-2xl font-semibold leading-tight tracking-tight">
          {tender.title}
        </h1>
        <p className="mt-1.5 text-sm text-muted">{tender.contracting_body}</p>
        <p className="mt-1 font-mono text-xs text-muted">{tender.expediente}</p>
      </div>

      {/* The analysis comes before the published data on purpose: once there is a verdict,
          the verdict is the page, and the tender's own fields are the supporting detail. */}
      <AnalysisPanel
        expediente={expediente}
        hasPcap={tender.pcap_url !== null}
        initialAnalysis={analysis}
        canAnalyze={capabilities.analysis}
      />

      <TenderFacts tender={tender} />
      <TenderDocuments tender={tender} />
    </div>
  );
}
