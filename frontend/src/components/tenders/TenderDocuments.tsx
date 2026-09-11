import { Card } from "@/components/ui/Card";
import type { Tender } from "@/lib/api";

/**
 * The tender's published documents.
 *
 * The PCAP is marked as the one the agent reads, because that distinction is invisible
 * otherwise: three identical links gave no hint that only one of them is what the whole
 * analysis is based on.
 */
export function TenderDocuments({ tender }: { tender: Tender }) {
  const documents = [
    {
      url: tender.pcap_url,
      label: "Pliego administrativo (PCAP)",
      note: "El que analiza el agente",
    },
    { url: tender.ppt_url, label: "Pliego técnico (PPT)", note: null },
    { url: tender.platform_url, label: "Ficha en PLACSP", note: null },
  ].filter((document): document is { url: string; label: string; note: string | null } =>
    document.url !== null,
  );

  if (documents.length === 0) {
    return null;
  }

  return (
    <Card as="section" className="p-5">
      <h2 className="text-sm font-semibold">Documentos</h2>
      <ul className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-sm">
        {documents.map((document) => (
          <li key={document.url}>
            <a
              className="text-accent underline underline-offset-2 hover:text-accent-strong"
              href={document.url}
              target="_blank"
              rel="noreferrer"
            >
              {document.label}
            </a>
            {document.note !== null ? (
              <span className="ml-2 text-xs text-muted">· {document.note}</span>
            ) : null}
          </li>
        ))}
      </ul>
    </Card>
  );
}
