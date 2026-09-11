import Link from "next/link";
import { ProviderForm } from "@/components/provider/ProviderForm";
import { ApiError, getMatches, getProvider } from "@/lib/api";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Tu perfil — Compass",
  description: "Los datos de tu empresa con los que Compass filtra y juzga las licitaciones.",
};

/**
 * Whether the corpus is empty, which decides if saving the profile also kicks off the
 * initial load.
 *
 * Read through the funnel counts rather than a dedicated endpoint: `GET /matches` already
 * reports the whole corpus size, and a 404 there means no profile yet -- which on this
 * screen is the normal case, not a failure.
 */
async function corpusIsEmpty(): Promise<boolean> {
  try {
    const { funnel } = await getMatches(1);
    return funnel.total === 0;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return true;
    throw error;
  }
}

export default async function ProfilePage() {
  const [provider, empty] = await Promise.all([getProvider(), corpusIsEmpty()]);
  const isFirstRun = provider === null;

  return (
    <div>
      {!isFirstRun ? (
        <Link href="/" className="text-sm text-muted hover:text-foreground">
          ← Volver a los matches
        </Link>
      ) : null}

      <header className={isFirstRun ? "mb-6" : "mb-6 mt-3"}>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          {isFirstRun ? "Empecemos por tu empresa" : "Tu perfil"}
        </h1>
        <p className="mt-2 max-w-prose text-sm leading-relaxed text-muted">
          {isFirstRun
            ? "Compass compara cada licitación de PLACSP con esto. Sin ello no hay nada que filtrar ni con qué comparar un pliego, así que es lo primero."
            : "Cambia cualquier cosa y el embudo y los veredictos se recalculan en la siguiente lectura. No hay nada que invalidar a mano."}
        </p>
      </header>

      <ProviderForm initial={provider} corpusIsEmpty={empty} />
    </div>
  );
}
