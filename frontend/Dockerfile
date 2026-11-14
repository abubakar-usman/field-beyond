# Next.js standalone image. BACKEND_URL is baked into the /api rewrite at build time.
FROM node:24-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:24-slim AS build
WORKDIR /app
ARG BACKEND_URL=http://backend:8000
ARG NEXT_PUBLIC_ENABLE_EOX=false
ENV BACKEND_URL=${BACKEND_URL} NEXT_PUBLIC_ENABLE_EOX=${NEXT_PUBLIC_ENABLE_EOX} NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:24-slim
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
# Standalone output omits public/; it holds the MapLibre web worker (copied by prebuild).
COPY --from=build /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
