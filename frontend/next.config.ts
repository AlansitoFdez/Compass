import type { NextConfig } from "next";

/**
 * Response headers the dashboard sends for every route.
 *
 * Compass runs on the machine of whoever uses it, so none of these defends against a
 * hostile internet -- but they are free, and they close the gaps that don't depend on
 * where it is hosted: a browser guessing MIME types, a referrer leaking an expediente to a
 * third-party site the reader clicked through to, and the page being framed by another
 * origin.
 *
 * The Content-Security-Policy waited for the deployment decision (5.4) because a
 * meaningful `connect-src` has to name wherever `NEXT_PUBLIC_API_URL` points, and until
 * that was settled it could only have been guessed. 5.4 settled it -- the API is
 * published on the host and the browser reaches it at that URL -- so 5.8 writes the
 * policy instead of leaving the note pointing at a subphase that already closed.
 *
 * What it is worth here, and what it isn't. `script-src` has to allow `'unsafe-inline'`:
 * Next bootstraps hydration from inline scripts, and the alternative is per-request
 * nonces from middleware, which is a lot of moving parts for a dashboard that runs on
 * localhost. So this does not stop an injection that already got a script onto the page.
 * What it does stop is the step after that one -- the page loading code from another
 * origin, or sending anything to one -- and that is the realistic risk for an app whose
 * whole job is rendering text out of PDFs written by third parties.
 */
const nextConfig: NextConfig = {
  // Traces the files the server actually needs into `.next/standalone`, so the runtime
  // image can drop `node_modules` entirely -- 40 MB instead of ~500. Only used by the
  // Docker build; `npm run dev` ignores it.
  output: "standalone",

  async headers() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    // `next dev` compiles in the browser and its hot reloader opens a websocket back to
    // itself; a production build needs neither, so neither is granted there.
    const isDev = process.env.NODE_ENV !== "production";
    const scriptSrc = isDev
      ? "'self' 'unsafe-inline' 'unsafe-eval'"
      : "'self' 'unsafe-inline'";
    const connectSrc = isDev ? `'self' ${apiUrl} ws: wss:` : `'self' ${apiUrl}`;

    const csp = [
      "default-src 'self'",
      `script-src ${scriptSrc}`,
      // Tailwind v4 and Next both emit style tags, and neither carries a nonce.
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data:",
      "font-src 'self' data:",
      `connect-src ${connectSrc}`,
      // Nothing here embeds, is embedded, or submits anywhere: the dashboard writes
      // through fetch, not through a form post.
      "frame-ancestors 'none'",
      "frame-src 'none'",
      "object-src 'none'",
      "base-uri 'self'",
      "form-action 'self'",
    ].join("; ");

    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          // Redundant with frame-ancestors for any modern browser, kept because it costs
          // one header and covers the ones that never learned CSP level 2.
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};

export default nextConfig;
