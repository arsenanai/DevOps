# academy.roqed.com — Recovery Info

## Overview

| Field | Value |
|-------|-------|
| Subdomain | academy.roqed.com |
| CMS | WordPress |
| WP DB Version | 48748 (WordPress ~5.5.x) |
| Database | `academy_roqed` |
| DB Table Prefix | `wp_` |
| Language | `ru_RU` (Russian) |
| Active Theme | Twenty Twenty (`twentytwenty`) |
| DocumentRoot | `/var/www/academy.roqed.com` (deleted) |
| Apache Vhost | `/etc/apache2/sites-available/academy.roqed.conf` (disabled) |
| SSL Vhost | `/etc/apache2/sites-available/academy.roqed-le-ssl.conf` (disabled) |
| SSL Cert | `/etc/letsencrypt/live/academy.roqed.com/` (likely expired) |
| Server Admin | m.ipsum@gmail.com |

## Files Status

**All files are gone.** The DocumentRoot `/var/www/academy.roqed.com` no longer exists. Only the database remains.

## Database Content

Minimal content — this was a fresh/barely-started WordPress install:

| Post Type | Count |
|-----------|-------|
| page | 2 |
| post | 1 |

### Users

| ID | Login | Email |
|----|-------|-------|
| 1 | admin | m.ipsum@gmail.com |

## Active Plugins

**None** — no plugins were activated (`a:0:{}`).

## Theme

- **Active**: Twenty Twenty (default WordPress theme)
- No child theme or customizations detected in the database.

## Recovery Notes

- This was a barely-initialized WordPress site with default theme, no plugins, and almost no content.
- The `siteurl` and `home` in the database are set to `http://178.128.244.57` (IP address, not the domain) — was likely still in setup phase.
- Recovery would require a fresh WordPress install; the database has minimal value (3 posts/pages, 1 user).
