import Link from "next/link";
import { getMatches, type Match } from "@/lib/api";
import {
  daysUntil,
  formatDate,
  formatEur,
  tenderStatusLabel,
} from "@/lib/format";

// Always rendered against the live API: the funnel's output changes with every daily
// ingestion, and a build-time snapshot of it would be stale the next morning.
export const dynamic = "force-dynamic";

/**
 * Why this tender is here at all -- the "motivo de encaje" of the fused ranking.
 *
 * A match found by both recoverers is the strong case; one found by only the vector
 * side is the one a keyword search would have missed entirely, which is the whole
 * argument for the hybrid design (phase 2).
 */
function MatchOrigin({ match }: { match: Match }) {
  const lexical = match.lexical_rank !== null;
  const vector = match.vector_rank !== null;
  const label = lexical && vector ? "Léxico + vectorial" : lexical ? "Solo léxico" : "Solo vectorial";
  const title =
    lexical && vector
      ? "Lo encontraron los dos recuperadores: coinciden las palabras del título y el significado."
      : lexical
        ? "Solo lo encontró la búsqueda por palabras."
        : "Solo lo encontró la búsqueda semántica: comparte significado sin compartir las palabras.";

  return (
    <span
      title={title}
      className="rounded-full border border-border bg-surface-muted px-2.5 py-1 text-xs text-muted"
    >
      {label}
    </span>
  );
}

function Deadline({ iso }: { iso: string | null }) {
  const days = daysUntil(iso);
  if (days === null) return <span className="text-muted">Sin plazo publicado</span>;
  if (days < 0) return <span className="text-muted">Plazo cerrado</span>;
  return (
    <span className={days <= 7 ? "font-medium text-foreground" : "text-muted"}>
      {formatDate(iso)} · quedan {days} {days === 1 ? "día" : "días"}
    </span>
  );
}

function MatchCard({ match, position }: { match: Match; position: number }) {
  const { tender } = match;
  return (
    <li className="rounded-lg border border-border bg-surface p-5 transition-colors hover:border-accent">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-xs text-muted">
            <span className="font-mono">#{position}</span>
            <span>·</span>
            <span className="truncate font-mono">{tender.expediente}</span>
          </div>
          <h2 className="mt-1 text-base font-semibold leading-snug">
            <Link
              href={`/tenders/${tender.expediente}`}
              className="hover:text-accent"
            >
              {tender.title}
            </Link>
          </h2>
          <p className="mt-1 text-sm text-muted">{tender.contracting_body}</p>
        </div>
        <MatchOrigin match={match} />
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted">Importe</dt>
          <dd>{formatEur(tender.budget_with_vat ?? tender.estimated_value)}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted">Presentación</dt>
          <dd>
            <Deadline iso={tender.submission_deadline} />
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted">Estado</dt>
          <dd>{tenderStatusLabel(tender.status)}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted">Score RRF</dt>
          <dd className="font-mono">{match.rrf_score.toFixed(4)}</dd>
        </div>
      </dl>
    </li>
  );
}

export default async function MatchesPage() {
  const { items, total } = await getMatches(20);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Licitaciones que encajan contigo</h1>
        <p className="mt-1 text-sm text-muted">
          {total} resultados del embudo, ordenados por Reciprocal Rank Fusion sobre la búsqueda
          léxica y la vectorial. Nada de esto ha pasado todavía por un modelo: es determinista.
        </p>
      </div>

      {items.length === 0 ? (
        <p className="rounded-lg border border-border bg-surface p-6 text-sm text-muted">
          El embudo no ha devuelto ninguna licitación. Con el corpus cargado, esto normalmente
          significa que ninguna sigue en plazo de presentación.
        </p>
      ) : (
        <ul className="space-y-3">
          {items.map((match, index) => (
            <MatchCard key={match.tender.expediente} match={match} position={index + 1} />
          ))}
        </ul>
      )}
    </div>
  );
}
