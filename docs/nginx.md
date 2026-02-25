# Nginx — Security & Performance

## Security

- Hide version info: `server_tokens off;` in the `http` block.
- Add security headers in every server block or globally:
  ```
  add_header X-Frame-Options "SAMEORIGIN" always;
  add_header X-Content-Type-Options "nosniff" always;
  add_header X-XSS-Protection "1; mode=block" always;
  add_header Referrer-Policy "strict-origin-when-cross-origin" always;
  add_header Permissions-Policy "geolocation=(), camera=(), microphone=()" always;
  ```
- Restrict access to hidden files: `location ~ /\. { deny all; }` (except `.well-known` for LetsEncrypt).
- Disable unused HTTP methods: return 444 for anything other than GET, POST, HEAD where appropriate.
- Rate-limit login/admin endpoints with `limit_req_zone` to mitigate brute force.
- Block direct IP access — define a default server block that returns 444 so scanners hitting the IP get nothing.

## Performance

- Enable gzip: `gzip on;` with `gzip_types text/plain text/css application/json application/javascript text/xml application/xml image/svg+xml;`
- Set `gzip_comp_level 5;` — good balance between CPU and compression ratio.
- Enable `sendfile on;`, `tcp_nopush on;`, `tcp_nodelay on;`.
- Set `keepalive_timeout 30;` and `keepalive_requests 1000;`.
- Cache static assets with long expiry: `location ~* \.(css|js|jpg|jpeg|png|gif|ico|woff2|svg)$ { expires 1y; add_header Cache-Control "public, immutable"; }`
- Enable `open_file_cache` for frequently accessed files.
- Tune `worker_processes auto;` and `worker_connections 2048;` (or higher depending on server capacity).
- Use `fastcgi_cache` for PHP sites to serve cached pages without hitting PHP at all.
- Enable HTTP/2 (`listen 443 ssl http2;`) for multiplexed connections.
