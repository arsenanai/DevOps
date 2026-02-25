# Joomla — Security & Performance

## Security

- Keep Joomla core and extensions updated. Check the Vulnerable Extensions List (VEL) before installing anything.
- Remove unused extensions completely (not just disabled).
- Rename or protect the `/administrator` path with HTTP basic auth or IP restriction.
- Set correct file permissions: directories `755`, files `644`, `configuration.php` `444`.
- Enable two-factor authentication for admin accounts.
- Set `$force_ssl = 2` in `configuration.php` to force HTTPS on the entire site.
- Disable user registration if not needed: Global Configuration > Users > Allow User Registration = No.
- Block access to sensitive files from web: `htaccess.txt`, `web.config.txt`, `configuration.php-dist`.
- Prevent PHP execution in `/images`, `/tmp`, `/logs`, and `/cache` directories.

## Performance

- Enable Joomla's built-in caching: Global Configuration > System > Cache = ON, Cache Handler = File (or Redis if available).
- Enable page caching via the "System - Page Cache" plugin.
- Enable Gzip compression in Global Configuration.
- Optimize the database through Joomla's admin or directly via SQL — clean sessions table, expired cache, action logs.
- Use Redis for session handling: set `$session_handler = 'redis'` in `configuration.php`.
- Minimize installed extensions — each adds queries and PHP overhead.
- Use a CDN for media files.
