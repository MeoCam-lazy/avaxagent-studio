# Frontend image: builds the SPA, then serves it from Caddy, which also proxies
# /api to the control plane and fronts the A2A gateway (deploy/Caddyfile).
# Build context = repo root.

FROM node:20-alpine AS build
RUN corepack enable
WORKDIR /repo
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/frontend/package.json apps/frontend/
RUN pnpm install --frozen-lockfile --filter @avaxagent-studio/frontend
COPY apps/frontend apps/frontend
# Same-origin API path; Caddy forwards it to the api service.
ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=$VITE_API_URL
RUN pnpm --filter @avaxagent-studio/frontend build

FROM caddy:2.8-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /repo/apps/frontend/dist /srv
