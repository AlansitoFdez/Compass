"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/Button";
import { API_URL, ApiUnreachableError } from "@/lib/api";

/**
 * The error boundary for every route under `/`.
 *
 * Until 5.3 there was none at all, so the single most likely failure -- the API not
 * running, which is routine when the whole thing runs on the reader's own machine --
 * produced Next's unstyled default error screen, with no explanation and no way forward.
 *
 * The recovery prop is `retry`, not `reset`: Next 16 renamed it.
 */
export default function Error({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  // `ApiUnreachableError` doesn't survive the server/client boundary as a class -- Next
  // replaces a server error with a plain Error carrying a digest in production -- so the
  // name is checked instead, and the message is written to be true either way.
  const unreachable =
    error instanceof ApiUnreachableError || error.name === "ApiUnreachableError";

  return (
    <div className="mx-auto max-w-prose py-12 text-center">
      <p className="field-label">Error</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">
        {unreachable ? "No se puede conectar con la API" : "Algo ha fallado"}
      </h1>
      <div className="mt-3 space-y-3 text-sm text-muted">
        {unreachable ? (
          <>
            <p>
              El dashboard no consigue hablar con la API de Compass en{" "}
              <code className="font-mono text-xs text-foreground">{API_URL}</code>.
            </p>
            <p>
              Comprueba que Docker está levantado y que la API corre con{" "}
              <code className="font-mono text-xs text-foreground">uv run python -m compass</code>{" "}
              desde <code className="font-mono text-xs text-foreground">backend/</code>.
            </p>
          </>
        ) : (
          <p>
            La API respondió con un error inesperado. Si se repite, el log de la API dice
            más que esta pantalla.
          </p>
        )}
      </div>
      <div className="mt-6">
        <Button type="button" onClick={retry}>
          Reintentar
        </Button>
      </div>
    </div>
  );
}
