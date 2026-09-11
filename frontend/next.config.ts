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
 * No Content-Security-Policy yet: the dashboard calls the API from the browser at whatever
 * `NEXT_PUBLIC_API_URL` says, so a meaningful `connect-src` has to be built from that
 * value. That belongs with the deployment decision in 5.4, not guessed at here.
 */
const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};

export default nextConfig;
