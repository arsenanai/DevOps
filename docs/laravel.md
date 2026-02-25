# Laravel — Security & Performance

## Security

- Never set `APP_DEBUG=true` in production — it exposes environment variables, database credentials, and full stack traces.
- Set `APP_ENV=production` in `.env`.
- Ensure `.env` is not web-accessible — verify web server config blocks it.
- Use `php artisan key:generate` — check that `APP_KEY` is set and not the default.
- Use CSRF protection (enabled by default) — don't disable `VerifyCsrfToken` middleware.
- Use parameterized queries / Eloquent (default) — never concatenate user input into raw queries.
- Validate all input with Form Requests or inline validation. Never trust user data.
- Set proper CORS configuration in `config/cors.php` — don't use `'*'` for `allowed_origins` in production.
- Run `php artisan config:cache` and `php artisan route:cache` in production to lock config and prevent `.env` from being read at runtime.
- Use `Hash::make()` (bcrypt/argon2) for passwords — never store plaintext or MD5.

## Performance

- Run these in production deployments:
  ```
  php artisan config:cache
  php artisan route:cache
  php artisan view:cache
  php artisan event:cache
  ```
- Use Redis for cache, session, and queue drivers:
  ```
  CACHE_DRIVER=redis
  SESSION_DRIVER=redis
  QUEUE_CONNECTION=redis
  ```
- Enable OPcache (see [PHP docs](php.md)).
- Use eager loading (`with()`) to prevent N+1 query problems. Enable strict mode in development:
  ```php
  Model::preventLazyLoading(! app()->isProduction());
  ```
- Use database indexes on columns that appear in `WHERE`, `ORDER BY`, and `JOIN` clauses.
- Use queue workers for long-running tasks (email, image processing, API calls) — never do these in a web request.
- Use `php artisan optimize` on deployment as a shortcut for caching config, routes, and views.
- Configure Supervisor to manage queue workers reliably:
  ```ini
  [program:laravel-worker]
  command=php /path/to/artisan queue:work redis --sleep=3 --tries=3 --max-time=3600
  numprocs=2
  autostart=true
  autorestart=true
  ```
