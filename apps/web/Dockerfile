# Multi-stage Dockerfile for the React frontend.
# Build from monorepo root:
#   docker compose build frontend
# Or standalone:
#   docker build -t event-ticketing-web -f apps/web/Dockerfile apps/web/

# -- Stage 1: build React app --------------------------------------------
FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json pnpm-lock.yaml* ./
RUN corepack enable && pnpm install --frozen-lockfile || npm install

COPY . .
RUN npm run build

# -- Stage 2: serve with nginx -------------------------------------------
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
