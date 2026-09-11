import { CitationBlock } from "@/components/analysis/CitationBlock";
import type { Citation, PliegoExtraction } from "@/lib/api";
import { formatEur } from "@/lib/format";

/**
 * What the pliego says, field by field, each with the quote it came from.
 *
 * Split out of `AnalysisPanel` in 5.3. Presentation only -- the mapping from extraction to
 * the seven readable rows lives in `rows()` below, so the component itself stays a list.
 */

type Row = { label: string; value: string; citation: Citation | null };

function rows(extraction: PliegoExtraction): Row[] {
  const price = extraction.award_criteria.criteria.find((criterion) => criterion.is_price);

  return [
    {
      label: "Solvencia económica",
      value:
        extraction.economic_solvency.minimum_annual_turnover_eur !== null
          ? `Cifra de negocio mínima: ${formatEur(extraction.economic_solvency.minimum_annual_turnover_eur)}`
          : extraction.economic_solvency.description || "No se exige una cifra concreta.",
      citation: extraction.economic_solvency.citation,
    },
    {
      label: "Solvencia técnica",
      value:
        extraction.technical_solvency.minimum_amount_eur !== null
          ? `Importe mínimo en trabajos similares: ${formatEur(extraction.technical_solvency.minimum_amount_eur)}`
          : extraction.technical_solvency.description || "No se exige un importe concreto.",
      citation: extraction.technical_solvency.citation,
    },
    {
      label: "Certificaciones exigidas",
      value:
        extraction.certifications.length > 0
          ? extraction.certifications.join(" · ")
          : "Ninguna.",
      citation: extraction.certifications_citation,
    },
    {
      label: "Criterios de adjudicación",
      value:
        price !== undefined
          ? `${extraction.award_criteria.total_points} puntos en total, ${price.points} al precio.`
          : `${extraction.award_criteria.total_points} puntos en total.`,
      citation: extraction.award_criteria.citation,
    },
    {
      label: "Garantías",
      value:
        extraction.guarantees.description ||
        (extraction.guarantees.provisional_required
          ? "Se exige garantía provisional."
          : "Sin garantía provisional."),
      citation: extraction.guarantees.citation,
    },
    {
      label: "Plazo de ejecución",
      value: extraction.execution_deadline.description || "No indicado.",
      citation: extraction.execution_deadline.citation,
    },
    {
      label: "Lotes",
      value: extraction.lots.divided_into_lots
        ? extraction.lots.description || "Dividido en lotes."
        : "No está dividido en lotes.",
      citation: extraction.lots.citation,
    },
  ];
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
              {row.value}
              <CitationBlock citation={row.citation} />
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
