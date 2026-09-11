/**
 * Transport for the Compass API: the base URL, the error type, and one `request`.
 *
 * Runs from both sides. Server Components call it during render; the analysis panel calls
 * it from the browser while polling. That is why the base URL is a `NEXT_PUBLIC_`
 * variable -- it has to be readable in the bundle, not only on the server.
 */

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Thrown for any non-OK response, carrying the status so callers can tell 404 apart. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Thrown when the API can't be reached at all -- not running, wrong URL, no network. */
export class ApiUnreachableError extends Error {
  constructor(readonly cause: unknown) {
    super(`No se pudo conectar con la API en ${API_URL}`);
    this.name = "ApiUnreachableError";
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      // Never a cached read: this dashboard exists to show what the funnel and the analyst
      // say *right now*, and the panel polls a value that changes between one request and
      // the next.
      cache: "no-store",
      ...init,
    });
  } catch (cause) {
    // A fetch that never got an answer throws a bare TypeError whose message says nothing
    // a user could act on ("fetch failed"). Distinguishing it here is what lets the error
    // boundary tell "the API is down" apart from "the API said no" -- by far the most
    // likely failure when everything runs on the reader's own machine.
    throw new ApiUnreachableError(cause);
  }

  if (!response.ok) {
    throw new ApiError(
      response.status,
      `${init?.method ?? "GET"} ${path} -> ${response.status}`,
    );
  }
  return (await response.json()) as T;
}
