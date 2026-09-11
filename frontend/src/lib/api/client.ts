/**
 * Transport for the Compass API: the base URL, the error type, and one `request`.
 *
 * Runs from both sides, and that is the only complication here: Server Components call it
 * during render, on the server, while the analysis panel calls it from the browser. In
 * Docker those two are not the same network, so there are two base URLs -- see `baseUrl`.
 */

/**
 * Where the *browser* reaches the API. Also what error messages quote, since that is the
 * address the reader would type themselves.
 */
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Where *this process* reaches the API, which is not always the same place.
 *
 * Server Components fetch during render, and in Docker they run inside the dashboard's own
 * container -- where `localhost:8000` is that container, not the API. The browser has the
 * opposite problem: it cannot resolve `api`, the compose service name. So the two need
 * different addresses, and the only one that can be inlined into the client bundle is the
 * browser's.
 *
 * `COMPASS_INTERNAL_API_URL` is deliberately not `NEXT_PUBLIC_`: it must stay server-side,
 * and in client code that lookup simply comes back undefined and falls through to the
 * public URL -- which is the right answer there anyway.
 */
function baseUrl(): string {
  if (typeof window !== "undefined") return API_URL;
  return process.env.COMPASS_INTERNAL_API_URL ?? API_URL;
}

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
    response = await fetch(`${baseUrl()}${path}`, {
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
