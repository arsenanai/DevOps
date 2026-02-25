# Apache — Security & Performance

## Security

- Hide version: `ServerTokens Prod` and `ServerSignature Off`.
- Same security headers as Nginx, set via `Header always set` in the global config or `.htaccess`.
- Disable directory listing: `Options -Indexes` globally.
- Restrict `.htaccess` overrides to only what's needed: `AllowOverride` should not be `All` unless required.
- Disable unused modules (`a2dismod`): `autoindex`, `status`, `cgi`, `env` if not needed.
- Block access to sensitive files: `.env`, `.git`, `composer.json`, `wp-config.php` from web access.
- Use `<FilesMatch>` to deny access to backup files: `.bak`, `.sql`, `.tar.gz`, `.zip`.

## Performance

- Use `mpm_event` over `mpm_prefork` when possible (requires PHP-FPM, not `mod_php`).
- If stuck on `mpm_prefork`, tune `MaxRequestWorkers` to match available RAM (each worker ~30-50MB with PHP).
- Enable `mod_expires` and `mod_deflate` for caching and compression.
- Enable `mod_http2` for HTTP/2 support.
- Use `KeepAlive On` with `KeepAliveTimeout 5` and `MaxKeepAliveRequests 200`.
- Consider migrating from Apache to Nginx as a reverse proxy with PHP-FPM for significantly better resource usage on high-traffic sites.
