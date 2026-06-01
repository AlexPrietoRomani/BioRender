# ── Etapa 1: Build ──────────────────────────────────────────
FROM node:22-slim AS builder

# Habilitar pnpm via corepack (incluido en Node 22)
RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

# CI=true evita que pnpm pida confirmación interactiva en entorno sin TTY
ENV CI=true

# Copiar manifiestos de dependencias primero para aprovechar el cache de capas
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
RUN pnpm install --frozen-lockfile

# Copiar el resto del código fuente
COPY . .

# PUBLIC_GATEWAY_HTTP_URL se inyecta en tiempo de build (Astro SSG bake).
# El navegador del usuario accede al gateway en localhost:8080.
ARG PUBLIC_GATEWAY_HTTP_URL=http://localhost:8080
ENV PUBLIC_GATEWAY_HTTP_URL=${PUBLIC_GATEWAY_HTTP_URL}

RUN pnpm run build

# ── Etapa 2: Servidor nginx ──────────────────────────────────
FROM nginx:alpine

# Copiar la configuración de nginx personalizada
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copiar el output estático de Astro desde el builder
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
