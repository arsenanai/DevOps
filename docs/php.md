# PHP, PHP Extensions, PHP-FPM & Composer

## PHP — Security

- Hide PHP version: `expose_php = Off` in `php.ini`.
- Disable dangerous functions: `disable_functions = exec,passthru,shell_exec,system,proc_open,popen,curl_multi_exec,parse_ini_file,show_source` — adjust per application needs (Laravel artisan needs some of these).
- Set `open_basedir` to restrict PHP file access to only the site's directory tree.
- Disable `allow_url_fopen` and `allow_url_include` unless specifically required.
- Set `session.cookie_httponly = 1`, `session.cookie_secure = 1`, `session.use_strict_mode = 1`.
- Set `session.cookie_samesite = Lax` (or `Strict` if appropriate).
- Set `display_errors = Off` and `log_errors = On` on production. Never display errors to users.
- Set `error_reporting = E_ALL` in production (log everything, display nothing).

## PHP — Performance

- Enable OPcache (critical for production):
  ```
  opcache.enable=1
  opcache.memory_consumption=256
  opcache.interned_strings_buffer=16
  opcache.max_accelerated_files=20000
  opcache.revalidate_freq=60
  opcache.validate_timestamps=1
  ```
  For fully stable production sites, set `opcache.validate_timestamps=0` and clear cache on deploy.
- Set `realpath_cache_size = 4096K` and `realpath_cache_ttl = 600`.
- Set `memory_limit` appropriately per application — `256M` for most CMS sites, `512M` for heavy apps. Don't set to `-1`.
- Set `max_execution_time = 30` (increase only for specific long-running scripts, not globally).
- Set `max_input_vars = 5000` for complex admin panels (WordPress/Joomla menus).

## PHP Extensions

- Verify required extensions are installed before application setup. Common requirements:
  - **General**: `mbstring`, `xml`, `curl`, `zip`, `gd` or `imagick`, `intl`, `bcmath`
  - **Database**: `mysqlnd`, `pdo_mysql`, `pdo_pgsql`, `pgsql`
  - **Caching**: `redis`, `apcu`, `memcached`
  - **Laravel**: `tokenizer`, `json`, `openssl`, `fileinfo`, `dom`, `pcre`
  - **WordPress**: `exif`, `mysqli`, `imagick` (for image editing)
- Check loaded extensions: `php -m`. Compare against application requirements.
- Disable extensions not in use — each loaded extension consumes memory per PHP-FPM worker.
- Keep `ionCube` or `sourceguardian` loaders only if required by specific software. They slow down OPcache.

## PHP-FPM — Security

- Run each site under its own pool with a dedicated system user — never run all sites under `www-data`.
- Set `security.limit_extensions = .php` to prevent execution of uploaded files with other extensions.
- Restrict pool socket/port permissions to only the web server user.
- Set `php_admin_value[open_basedir]` per pool to isolate sites from each other.

## PHP-FPM — Performance

- Choose the right process manager:
  - `pm = dynamic` for most sites.
  - `pm = ondemand` for low-traffic sites (saves RAM, slightly slower first request).
  - `pm = static` for high-traffic sites with predictable load (pre-forks workers, no spawn overhead).
- Tune pool sizes based on available RAM. Each worker uses ~30-80MB depending on the application. Formula: `pm.max_children = (Available RAM for PHP) / (Average worker memory)`.
- Set `pm.max_requests = 500` to recycle workers and prevent memory leaks from accumulating.
- For `pm = dynamic`:
  ```
  pm.start_servers = 5
  pm.min_spare_servers = 3
  pm.max_spare_servers = 10
  ```
  Adjust based on traffic patterns.
- Enable slow log for debugging: `slowlog = /var/log/php-fpm/slow.$pool.log` and `request_slowlog_timeout = 5s`.
- Monitor FPM status page (`pm.status_path = /fpm-status`) — restrict access to localhost/admin IPs only.

## Composer (PHP Dependency Manager)

- Run `composer install --no-dev --optimize-autoloader` in production — never include dev dependencies.
- Use `--classmap-authoritative` flag for production if the autoload map is complete (no dynamic class loading).
- Lock dependencies with `composer.lock` — never run `composer update` in production, only `composer install`.
- Check for known vulnerabilities: `composer audit`.
- Keep `vendor/` out of version control — deploy via `composer install` instead.
