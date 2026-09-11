import { DeadlinePill } from "@/components/tenders/DeadlinePill";
import { Card } from "@/components/ui/Card";
import type { Tender } from "@/lib/api";
import { formatEur, tenderStatusLabel } from "@/lib/format";

/**
 * The tender's own published data.
 *
 * One column on a phone, not two: at 400px the previous `grid-cols-2` squeezed the CPV
 * codes and the procedure name into ~150px tracks, which is narrower than the content.
 */
export function TenderFacts({ tender }: { tender: Tender }) {
  return (
    <Card as="section" className="p-5">
      <dl className="grid grid-cols-1 gap-x-6 gap-y-4 text-sm sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <dt className="field-label">Importe (con IVA)</dt>
          <dd className="tabular mt-0.5 font-medium">{formatEur(tender.budget_with_vat)}</dd>
        </div>
        <div>
          <dt className="field-label">Valor estimado</dt>
          <dd className="tabular mt-0.5">{formatEur(tender.estimated_value)}</dd>
        </div>
        <div>
          <dt className="field-label">Estado</dt>
          <dd className="mt-0.5">{tenderStatusLabel(tender.status)}</dd>
        </div>
        <div>
          <dt className="field-label">Fin de presentación</dt>
          <dd className="mt-1">
            <DeadlinePill iso={tender.submission_deadline} />
          </dd>
        </div>
        <div>
          <dt className="field-label">Lugar</dt>
          <dd className="mt-0.5">{tender.location ?? "No indicado"}</dd>
        </div>
        <div>
          <dt className="field-label">Procedimiento</dt>
          <dd className="mt-0.5">{tender.procedure_type}</dd>
        </div>
        <div className="sm:col-span-2 lg:col-span-3">
          <dt className="field-label">CPV</dt>
          <dd className="mt-1 flex flex-wrap gap-1.5">
            {tender.cpv_codes.map((code) => (
              <span
                key={code}
                className="rounded-sm border border-border bg-surface-muted px-1.5 py-0.5 font-mono text-xs"
              >
                {code}
              </span>
            ))}
          </dd>
        </div>
      </dl>
    </Card>
  );
}
