# Docker — Security & Performance

## Security

- Never run containers as root. Use `USER` directive in Dockerfiles:
  ```dockerfile
  RUN addgroup -S app && adduser -S app -G app
  USER app
  ```
- Don't use `--privileged` flag unless absolutely necessary — it gives the container full host access.
- Don't mount the Docker socket (`/var/run/docker.sock`) into containers unless required — it grants root-equivalent host access.
- Use specific image tags (e.g., `node:20-alpine`), never `latest` — builds must be reproducible.
- Scan images for vulnerabilities: `docker scout cves <image>` or `trivy image <image>`.
- Don't store secrets in images or environment variables visible via `docker inspect`. Use Docker secrets or mount them as read-only files.
- Set `read_only: true` in compose for containers that don't need to write to the filesystem. Use `tmpfs` for temporary write needs.
- Limit container resources to prevent a single container from consuming the entire host:
  ```yaml
  deploy:
    resources:
      limits:
        cpus: '1.0'
        memory: 512M
  ```
- Use non-root, minimal base images (`alpine`, `distroless`) to reduce attack surface.
- Don't expose ports unnecessarily — only expose what the reverse proxy needs to reach.

## Performance

- Use multi-stage builds to keep final images small:
  ```dockerfile
  FROM node:20-alpine AS build
  WORKDIR /app
  COPY package*.json ./
  RUN npm ci
  COPY . .
  RUN npm run build

  FROM nginx:alpine
  COPY --from=build /app/dist /usr/share/nginx/html
  ```
- Order Dockerfile instructions from least to most frequently changing — this maximizes layer cache hits. Dependencies before source code.
- Use `.dockerignore` to exclude `node_modules`, `.git`, logs, and build artifacts from the build context.
- Combine `RUN` commands to reduce layers: `RUN apt-get update && apt-get install -y pkg && rm -rf /var/lib/apt/lists/*`.
- Use `COPY package*.json . && RUN npm ci` before `COPY . .` to cache dependency installation.
- For PHP apps, use `COPY composer.json composer.lock ./ && RUN composer install --no-dev` before copying the full app source.
- Use `docker compose` (v2) health checks to ensure dependent services are ready:
  ```yaml
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
    interval: 10s
    timeout: 5s
    retries: 3
  ```
- Use named volumes for database data (`mysql_data:/var/lib/mysql`) — never store database data in anonymous volumes or container layers.
- Set `restart: unless-stopped` for production services.
- Use `docker system prune` periodically to reclaim disk from unused images, containers, and volumes. On production, be explicit: `docker image prune -a --filter "until=168h"`.
- For logging, use `json-file` driver with rotation:
  ```yaml
  logging:
    driver: json-file
    options:
      max-size: "10m"
      max-file: "3"
  ```
- Pin the Docker Compose version in CI/CD. Use `docker compose` (plugin) over the legacy `docker-compose` binary.
