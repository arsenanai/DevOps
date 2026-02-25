# partners.roqed.com — Recovery Info

## Overview

| Field | Value |
|-------|-------|
| Subdomain | partners.roqed.com |
| CMS | **Joomla 3.9.22** (same installation as portal.roqed.com) |
| Database | `portal_roqed` (shared with portal.roqed.com) |
| DB Table Prefix | `jos_` |
| DocumentRoot | `/var/www/portal.roqed.com` (deleted — **same path as portal**) |
| Apache Vhost | `/etc/apache2/sites-available/partners.roqed.conf` (disabled) |
| SSL Vhost | `/etc/apache2/sites-available/partners.roqed-le-ssl.conf` (disabled) |
| SSL Cert | `/etc/letsencrypt/live/partners.roqed.com/` (likely expired) |
| Server Admin | m.ipsum@gmail.com |

## Files Status

**All files are gone.** Same situation as portal.roqed.com — they shared the same DocumentRoot.

## Relationship to portal.roqed.com

**partners.roqed.com is NOT a separate application.** Both Apache vhosts point to the exact same DocumentRoot:

```
# portal.roqed.conf
DocumentRoot /var/www/portal.roqed.com

# partners.roqed.conf
DocumentRoot /var/www/portal.roqed.com
```

This means partners.roqed.com was served by the **same Joomla installation** as portal.roqed.com. The differentiation between "portal" and "partners" was likely handled at the Joomla application level (menu items, access levels, or template assignments per domain).

## Relevant Custom Modules

The following modules in the `portal_roqed` database appear to be specifically for the partners interface:

| Module | Version | Description |
|--------|---------|-------------|
| mod_table_accm_partners | 1.0.11 | ACCM partners table |
| mod_table_partners | 1.0.11 | Partners table |
| mod_table_partners_unconf | 1.0.11 | Partners (unconfirmed) table |
| partner_licensetable | 1.0 | Partner license table |

## Relevant Database Tables

| Table | Row Count |
|-------|-----------|
| `jos_partners` | 32 |
| `jos_customers` | 649 |
| `jos_projects` | 1,202 |

## Recovery Notes

- **No separate recovery needed** — restoring portal.roqed.com automatically restores partners.roqed.com.
- The partners-specific behavior was controlled by Joomla's internal routing, not by separate code.
- To fully restore, re-enable both Apache vhosts after restoring the portal Joomla installation.
- See [PORTAL ROQED COM.md](PORTAL%20ROQED%20COM.md) for the full CMS, theme, plugin, and data details.
