import { redirect } from "next/navigation";
import { CorpusLoading } from "@/components/matches/CorpusLoading";
import { FunnelSummary } from "@/components/matches/FunnelSummary";
import { MatchList } from "@/components/matches/MatchList";
import { EmptyState } from "@/components/ui/EmptyState";
import { ApiError, getMatches } from "@/lib/api";
import { formatCount } from "@/lib/format";

// Always rendered against the live API: the funnel's output changes with every daily
// ingestion, and a build-time snapshot of it would be stale the next morning.
export const dynamic = "force-dynamic";

/**
 * The funnel emptied at some stage, and this says which one.
 *
 * "No hay resultados" is true and useless. The stage counts make the difference between
 * "nothing is open right now" and "your profile filtered everything out" visible, and only
 * the second is something the reader can act on.
 */
function EmptyFunnel({
  funnel,
}: {
  funnel: { total: number; after_status: number; after_cpv: number; after_budget: number };
}) {
  if (funnel.after_status === 0) {
    return (
      <EmptyState title="Ninguna licitación del corpus sigue en plazo">
        Se ingirieron {formatCount(funnel.total)}, pero todas han cerrado ya su plazo de
        presentación. La ingesta diaria trae las nuevas a las 03:00.
      </EmptyState>
    );
  }
  if (funnel.after_cpv === 0) {
    return (
      <EmptyState title="Ninguna de las abiertas comparte tus códigos CPV">
        Hay {formatCount(funnel.after_status)} licitaciones en plazo, pero ninguna coincide
        con los CPV de tu perfil. Ampliarlos en{" "}
        <code className="font-mono text-xs">providers/seed.py</code> es lo que mueve este
        número.
      </EmptyState>
    );
  }
  if (funnel.after_budget === 0) {
    return (
      <EmptyState title="Tu rango de importe deja fuera todo lo demás">
        {formatCount(funnel.after_cpv)} licitaciones encajan por CPV, pero ninguna cae
        dentro del rango de importe que declara tu perfil.
      </EmptyState>
    );
  }
  return (
    <EmptyState title="Tu ámbito geográfico deja fuera todo lo demás">
      {formatCount(funnel.after_budget)} licitaciones encajan por CPV e importe, pero
      ninguna se ejecuta en las provincias que declara tu perfil.
    </EmptyState>
  );
}

export default async function MatchesPage() {
  let matches;
  try {
    matches = await getMatches(20);
  } catch (error) {
    // The one 404 this endpoint returns by design: no provider profile has been seeded.
    // It isn't a failure, it's a setup step, so it gets an explanation rather than the
    // error boundary.
    if (error instanceof ApiError && error.status === 404) {
      // Not a failure: it is what a fresh install looks like, so it leads to the form
      // instead of explaining a command to run (which is what it did until 5.4).
      redirect("/perfil");
    }
    throw error;
  }

  const { items, total, funnel } = matches;

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          Licitaciones que encajan contigo
        </h1>
        <p className="mt-2 max-w-prose text-sm leading-relaxed text-muted">
          De todo lo que PLACSP publica, el embudo deja {formatCount(total)}. Ordenadas por
          Reciprocal Rank Fusion sobre la búsqueda léxica y la vectorial — nada de esto ha
          pasado todavía por un modelo: es determinista.
        </p>
      </header>

      {/* An empty corpus means the first load is still running (or never started), which
          is a different thing from "the funnel filtered everything out" -- and the only
          one of the two where the right answer is to wait. */}
      {funnel.total === 0 ? (
        <CorpusLoading initialTotal={funnel.total} />
      ) : (
        <>
          <div className="mb-8">
            <FunnelSummary funnel={funnel} />
          </div>
          {total === 0 ? <EmptyFunnel funnel={funnel} /> : <MatchList matches={items} />}
        </>
      )}
    </div>
  );
}
