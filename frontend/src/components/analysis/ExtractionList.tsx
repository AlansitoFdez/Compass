import { CitationBlock } from "@/components/analysis/CitationBlock";
import type {
  CertificationRole,
  Citation,
  PliegoExtraction,
  RequiredCertification,
} from "@/lib/api";
import { formatEur } from "@/lib/format";

/**
 * What the pliego says, field by field, each with the quote it came from.
 *
 * Split out of `AnalysisPanel` in 5.3. Presentation only -- the mapping from extraction to
 * the readable rows lives in `rows()` below, so the component itself stays a list.
 *
 * Certifications are the one row that isn't a single value with a single quote, and 5.8 is
 * why: a pliego names them in three different roles and only one of them can block the bid,
 * so the role has to be on screen. A reader looking at a NO APTO needs to see *which*
 * certification caused it, and a reader looking at an APTO needs to see that the ISO the
 * pliego mentions was only worth points.
 */

const ROLE_LABELS: Record<CertificationRole, string> = {
  required_to_bid: "Exigida para licitar",
  award_criterion: "Solo puntúa",
  administrative_paperwork: "Papeleo de licitación",
};

type ValueRow = { kind: "value"; label: string; value: string; citation: Citation | null };
type CertificationsRow = { kind: "certifications"; label: string; items: RequiredCertification[] };
type Row = ValueRow | CertificationsRow;

function deadlineValue(deadline: PliegoExtraction["execution_deadline"]): string {
  const base = deadline.description || "No indicado.";
  if (deadline.extensions_allowed === true) {
    return `${base} Prórrogas: ${deadline.extensions_description ?? "previstas en el pliego."}`;
  }
  if (deadline.extensions_allowed === false) {
    return `${base} Sin prórrogas.`;
  }
  return `${base} El pliego no dice nada sobre prórrogas.`;
}

function rows(extraction: PliegoExtraction): Row[] {
  const price = extraction.award_criteria.criteria.find((criterion) => criterion.is_price);

  return [
    {
      kind: "value",
      label: "Solvencia económica",
      value:
        extraction.economic_solvency.minimum_annual_turnover_eur !== null
          ? `Cifra de negocio mínima: ${formatEur(extraction.economic_solvency.minimum_annual_turnover_eur)}`
          : extraction.economic_solvency.description || "No se exige una cifra concreta.",
      citation: extraction.economic_solvency.citation,
    },
    {
      kind: "value",
      label: "Solvencia técnica",
      value:
        extraction.technical_solvency.minimum_amount_eur !== null
          ? `Importe mínimo en trabajos similares: ${formatEur(extraction.technical_solvency.minimum_amount_eur)}`
          : extraction.technical_solvency.description || "No se exige un importe concreto.",
      citation: extraction.technical_solvency.citation,
    },
    {
      kind: "certifications",
      label: "Certificaciones",
      items: extraction.certifications,
    },
    {
      kind: "value",
      label: "Criterios de adjudicación",
      value:
        price !== undefined
          ? `${extraction.award_criteria.total_points} puntos en total, ${price.points} al precio.`
          : `${extraction.award_criteria.total_points} puntos en total.`,
      citation: extraction.award_criteria.citation,
    },
    {
      kind: "value",
      label: "Garantías",
      value:
        extraction.guarantees.description ||
        (extraction.guarantees.provisional_required
          ? "Se exige garantía provisional."
          : "Sin garantía provisional."),
      citation: extraction.guarantees.citation,
    },
    {
      kind: "value",
      label: "Plazo de ejecución",
      value: deadlineValue(extraction.execution_deadline),
      citation: extraction.execution_deadline.citation,
    },
    {
      kind: "value",
      label: "Lotes",
      value: extraction.lots.divided_into_lots
        ? extraction.lots.description || "Dividido en lotes."
        : "No está dividido en lotes.",
      citation: extraction.lots.citation,
    },
  ];
}

function CertificationItem({ certification }: { certification: RequiredCertification }) {
  const blocking = certification.role === "required_to_bid";
  return (
    <li className="mt-3 first:mt-0">
      <span className="text-sm">{certification.name}</span>
      <span
        className={`ml-2 rounded-sm px-1.5 py-0.5 align-middle text-[0.6875rem] font-medium ${
          blocking ? "bg-accent-soft text-accent-strong" : "bg-surface-muted text-muted"
        }`}
      >
        {ROLE_LABELS[certification.role]}
      </span>
      <CitationBlock citation={certification.citation} />
    </li>
  );
}

export function ExtractionList({ extraction }: { extraction: PliegoExtraction }) {
  return (
    <div className="mt-6">
      <h3 className="text-sm font-semibold">Lo que dice el pliego</h3>
      <dl className="mt-1">
        {rows(extraction).map((row) => (
          <div key={row.label} className="border-t border-border py-3">
            <dt className="field-label">{row.label}</dt>
            <dd className="mt-1 text-sm">
              {row.kind === "value" ? (
                <>
                  {row.value}
                  <CitationBlock citation={row.citation} />
                </>
              ) : row.items.length === 0 ? (
                "El pliego no menciona ninguna."
              ) : (
                <ul>
                  {row.items.map((certification) => (
                    <CertificationItem key={certification.name} certification={certification} />
                  ))}
                </ul>
              )}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
