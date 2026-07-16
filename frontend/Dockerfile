# Frontend build stage: produces the static export in /app/out.
# Task 12 wires this into a multi-stage build that copies `out/` into the
# backend image's STATIC_DIR. Standalone usage: build then copy out/.
FROM node:20-slim AS build

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ ./
# Same-origin in production -> no API base needed.
ENV NEXT_PUBLIC_API_BASE=""
RUN npm run build

# The static site is in /app/out. Serve with any static server for standalone test.
FROM nginx:alpine AS serve
COPY --from=build /app/out /usr/share/nginx/html
EXPOSE 80
