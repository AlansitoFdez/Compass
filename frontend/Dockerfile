# Compass dashboard: Next.js built once, served by its own standalone server.
#
# Three stages, and the last one is why: `output: "standalone"` traces exactly the files
# the server needs, so the runtime image carries no `node_modules` and no build toolchain.

FROM node:24-alpine AS deps
WORKDIR /app
# Only the manifests, so this layer survives every change that isn't a dependency change.
COPY package.json package-lock.json ./
# `npm ci` over `npm install`: installs exactly the lockfile and fails if it disagrees
# with package.json -- the same guarantee `uv sync --locked` gives the backend.
RUN npm ci


FROM node:24-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Where the browser will find the API. Not a runtime variable: anything prefixed
# NEXT_PUBLIC_ is inlined into the client bundle at build time, so it is fixed here.
#
# `localhost`, not the compose service name, and that is not a mistake -- this URL is
# resolved by the *browser*, which knows nothing about Docker's internal network. `api`
# would not resolve there. The API publishes its port on the host precisely so this works.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Type-checks as part of the build, so this is the types gate too (see .github/workflows).
RUN npm run build


FROM node:24-alpine AS runtime
WORKDIR /app

ENV NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000

# The traced server, plus the two directories `output: "standalone"` deliberately leaves
# out: static assets are expected to come from a CDN, and there is no CDN here.
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# Not root, same as the backend image. `node` already exists in this base image.
USER node

EXPOSE 3000
CMD ["node", "server.js"]
