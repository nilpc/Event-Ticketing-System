# Multi-stage Dockerfile for the React frontend.
# Build context must be the monorepo root:
#   docker compose build frontend

# -- Stage 1: build React app --------------------------------------------
FROM node:22-alpine AS builder

RUN corepack enable && corepack prepare pnpm@9 --activate

WORKDIR /app

COPY pnpm-workspace.yaml package.json pnpm-lock.yaml .npmrc ./
COPY packages/shared/package.json ./packages/shared/
COPY apps/web/package.json ./apps/web/

RUN pnpm install --frozen-lockfile || pnpm install

COPY packages/shared/ ./packages/shared/
COPY apps/web/ ./apps/web/

ENV PATH="/app/node_modules/.bin:$PATH"
WORKDIR /app/apps/web
RUN tsc -b && vite build

# -- Stage 2: serve with nginx -------------------------------------------
FROM nginx:alpine

COPY --from=builder /app/apps/web/dist /usr/share/nginx/html
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
