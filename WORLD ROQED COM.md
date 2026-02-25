# world.roqed.com — Recovery Info

## Overview

| Field | Value |
|-------|-------|
| Subdomain | world.roqed.com |
| CMS | **WordPress** |
| WP DB Version | 60421 (WordPress ~6.4.x) |
| Database | `world` |
| DB Table Prefix | `wp_` |
| Language | (not set — English default) |
| Active Theme | **Essentials Child Theme** (`child_essentials` / parent: `essentials`) |
| DocumentRoot | `/var/www/world.roqed.com` (deleted) |
| Apache Vhost | `/etc/apache2/sites-available/world.roqed.conf` (disabled) |
| SSL Vhost | `/etc/apache2/sites-available/world.roqed-le-ssl.conf` (disabled) |
| SSL Cert | `/etc/letsencrypt/live/world.roqed.com/` (likely expired) |
| Server Admin | m.ipsum@gmail.com |

**Note:** The `world` database has `siteurl` and `home` set to `https://roqed.com`. The current roqed.com wp-config.php also points to this database. This database was likely originally for world.roqed.com and later repurposed for the main domain, or the URLs were changed. The content (portfolios, booking systems, multilingual setup) suggests this was the primary ROQED corporate/product website.

## Files Status

**All files are gone.** The DocumentRoot `/var/www/world.roqed.com` no longer exists. Only the database remains.

## Database Content

This is a substantial, content-rich WordPress site:

| Post Type | Count |
|-----------|-------|
| attachment | 45,943 |
| portfolio | 2,144 |
| pathologies | 134 |
| nav_menu_item | 363 |
| page | 185 |
| revision | 56 |
| post | 32 |
| pixheader | 11 |
| pixfooter | 11 |
| shop_order | 9 |
| popup_theme | 8 |
| elementor_library | 8 |
| pixpopup | 7 |
| wpcf7_contact_form | 6 |
| product | 3 |
| product_variation | 3 |
| bp3d-model-viewer | 3 |
| Other types | ~20 |

## Active Theme

| Role | Theme | Notes |
|------|-------|-------|
| **Active (child)** | `child_essentials` | Essentials Child Theme by pixfort |
| **Parent** | `essentials` | Essentials theme by pixfort |

### Other Installed Themes (in DB)

- bauhaus
- oceanwp
- twentytwenty
- twentytwentyone

## Active Plugins (37)

### Multilingual & Translation (WPML Suite)

| Plugin | Version |
|--------|---------|
| sitepress-multilingual-cms (WPML) | 4.8.2 |
| wpml-string-translation | — |
| wpml-wpforms | — |
| wp-seo-multilingual | — |
| acfml (WPML ACF) | — |
| contact-form-7-multilingual | — |
| woocommerce-multilingual | — |

### Page Builder & Theme Framework

| Plugin | Version |
|--------|---------|
| Elementor | 3.18.3 |
| Elementor Pro | — |
| WPBakery (js_composer) | — |
| pixfort-core | — |
| pixfort-likes | — |

### E-Commerce

| Plugin | Version |
|--------|---------|
| WooCommerce | 10.5.2 |
| WooCommerce PDF Invoices | — |

### Booking Systems (3 different systems installed)

| Plugin | Version | DB Tables |
|--------|---------|-----------|
| Bookly | 21.6 | `wp_bookly_*` (20+ tables) |
| BookingPress | 1.0.80 | `wp_bookingpress_*` (15+ tables) |
| Bookit | — | `wp_bookit_*` (10+ tables) |

### Sliders

| Plugin | DB Tables |
|--------|-----------|
| Revolution Slider (revslider) | `wp_revslider_*` — **23 sliders** |
| Master Slider | `wp_masterslider_*` |

### Forms & Contact

| Plugin |
|--------|
| Contact Form 7 |
| WPForms Lite |
| roqed-form-plugin (**custom**) |

### Performance & Caching

| Plugin |
|--------|
| Autoptimize |
| Redis Cache |
| WP Fastest Cache |

### SEO & Analytics

| Plugin |
|--------|
| MonsterInsights (Google Analytics) |
| Google Site Kit |

### Utilities

| Plugin |
|--------|
| Advanced Custom Fields (ACF) |
| Content Aware Sidebars |
| Custom Post Type UI |
| Font Awesome |
| NoctaSTAPopup |
| PC Robots.txt |
| Simple 301 Redirects |
| Simple Custom CSS |
| UpdraftPlus |
| WP Mail SMTP |
| WP SendPulse (email marketing) |
| WP SendPulse UI |

### Custom Plugins

| Plugin | Notes |
|--------|-------|
| my-plugin/my-plugin.php | Unknown custom plugin |
| roqed-form-plugin/roqed-form.php | Custom ROQED form handler |

## Custom Post Types

| Post Type | Count | Notes |
|-----------|-------|-------|
| `portfolio` | 2,144 | Likely pixfort Essentials portfolio — major content |
| `pathologies` | 134 | Custom post type — domain-specific content |
| `pixheader` | 11 | Pixfort theme headers |
| `pixfooter` | 11 | Pixfort theme footers |
| `pixpopup` | 7 | Pixfort theme popups |
| `bp3d-model-viewer` | 3 | 3D model viewer content |

## Users

| ID | Login | Email |
|----|-------|-------|
| 1 | admin | (empty) |
| 2 | eyewink | vladimir@barinov.pro |
| 3 | magzhan | sng@roqed.com |
| 4 | angelinakenig | angelinakenig2015@gmail.com |
| 5 | mazikk | alex.ovvio@gmail.com |
| 6 | aidina | aidinatt8@gmail.com |
| 8 | Bakhitber | bakhitber.senbay@gmail.com |
| 9 | Zmeyramova | Zmeyramova@gmail.com |
| 10 | Akerke | akerke1999@gmail.com |
| 14 | antonsombra@gmail.com | antonsombra@gmail.com |
| 15 | eye | eye@gmail.com |
| 17 | baglan.orynbaev | baglan.orynbaev@gmail.com |
| 18 | amina | kudabay.amina@gmail.com |
| 19 | alzhan2 | alhanibrajuly@gmail.com |
| 20 | arsenanai | arsenanai@gmail.com |

## Recovery Notes

- **This is the most content-rich site** — 45,943 media attachments, 2,144 portfolio items, 185 pages, 23 Revolution Sliders, and 3 booking systems.
- **Essentials by pixfort** is a premium theme — a valid license and the original theme files are required.
- **Elementor Pro** and **WPBakery** are both installed — both are premium, need licenses.
- **WPML** (7 addon plugins) — commercial multilingual plugin suite, needs license.
- **Three separate booking plugins** (Bookly, BookingPress, Bookit) are installed — unusual, possibly testing different solutions. Check which one was actually active/used.
- **Revolution Slider** with 23 sliders — commercial plugin, needs license.
- **Custom plugins** (`roqed-form-plugin`, `my-plugin`) — source code must be recovered from developers or backups.
- **Custom post type `pathologies`** — likely registered via Custom Post Type UI plugin, definition should be in the DB.
- **3D Model Viewer** (`bp3d-model-viewer`) — 3 models stored, but media files are gone.
- All 45,943 media files (uploads directory) are lost with the DocumentRoot.
- The `siteurl`/`home` in the database is `https://roqed.com` — will need updating to `https://world.roqed.com` if restoring under the subdomain.
