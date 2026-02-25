# WordPress — Security & Performance

## Security

- Keep WordPress core, themes, and plugins updated. Outdated plugins are the #1 attack vector.
- Remove unused themes and plugins entirely — deactivated code is still exploitable.
- Change the default database table prefix from `wp_` to something unique.
- Disable file editing from the admin panel: `define('DISALLOW_FILE_EDIT', true);` in `wp-config.php`.
- Add security keys/salts in `wp-config.php` — regenerate from `https://api.wordpress.org/secret-key/1.1/salt/` if they look default.
- Restrict `wp-admin` and `wp-login.php` by IP or add HTTP basic auth as an extra layer.
- Block `xmlrpc.php` unless explicitly needed (used for brute force and DDoS amplification):
  - Nginx: `location = /xmlrpc.php { deny all; }`
  - Apache: `<Files xmlrpc.php> Require all denied </Files>`
- Prevent PHP execution in upload directories:
  - Nginx: `location ~* /wp-content/uploads/.*\.php$ { deny all; }`
- Set correct file permissions: directories `755`, files `644`, `wp-config.php` `600`.
- Disable directory browsing and author enumeration.

## Performance

- Install a page caching plugin (WP Super Cache, W3 Total Cache, or LiteSpeed Cache if on LiteSpeed).
- Better yet, use Nginx `fastcgi_cache` to bypass PHP entirely for cached pages.
- Enable object caching with Redis: install `Redis Object Cache` plugin and configure `wp-config.php`:
  ```php
  define('WP_REDIS_HOST', '127.0.0.1');
  define('WP_REDIS_PORT', 6379);
  ```
- Limit post revisions: `define('WP_POST_REVISIONS', 5);`
- Increase memory limit: `define('WP_MEMORY_LIMIT', '256M');`
- Disable WP-Cron and use a real cron job instead:
  ```php
  define('DISABLE_WP_CRON', true);
  ```
  Then add: `*/5 * * * * curl -s https://example.com/wp-cron.php > /dev/null 2>&1`
- Optimize the database periodically — clean transients, spam comments, post revisions, and orphaned metadata.
- Use a CDN for static assets.
