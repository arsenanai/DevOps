# portal.roqed.com — Recovery Info

## Overview

| Field | Value |
|-------|-------|
| Subdomain | portal.roqed.com |
| CMS | **Joomla 3.9.22** |
| Database | `portal_roqed` |
| DB Table Prefix | `jos_` |
| DocumentRoot | `/var/www/portal.roqed.com` (deleted) |
| Apache Vhost | `/etc/apache2/sites-available/portal.roqed.conf` (disabled) |
| SSL Vhost | `/etc/apache2/sites-available/portal.roqed-le-ssl.conf` (disabled) |
| SSL Cert | `/etc/letsencrypt/live/portal.roqed.com/` (likely expired) |
| Server Admin | m.ipsum@gmail.com |

## Files Status

**All files are gone.** The DocumentRoot `/var/www/portal.roqed.com` no longer exists. Only the database remains.

## Joomla Version

**Joomla 3.9.22** (October 2020 release), confirmed from `jos_extensions` manifest_cache.

## Active Template (Frontend)

| Template | Framework | Version |
|----------|-----------|---------|
| **Shaper Helix Ultimate** | JoomShaper Helix Ultimate Framework | 1.1.2 |

- Logo: `images/roqed_logo_white.svg` (white), mobile: `images/roqed_logo.svg`
- Favicon: `images/roqed_logo_icon.png`
- Contact email: partners@roqed.com
- Custom CSS with portal/lesson-specific styling applied
- Menu type: Mega menu, using `usermenu`

### Admin Template

| Template | Version |
|----------|---------|
| ISIS | Default Joomla admin |

### Other Installed Templates

- Beez3, Hathor, Protostar (Joomla defaults)
- Shaper Helix3 (older version, not active)

## Third-Party Components

| Component | Version | Description |
|-----------|---------|-------------|
| **iJoomla Guru (COM_GURU)** | 5.2.2 | **LMS/course platform** — main business component |
| **SP Page Builder** | 3.6.8 | Visual page builder by JoomShaper |
| **Form Maker** | 3.6.16 | Form builder by Web Dorado |

## Third-Party Plugins (Enabled)

| Plugin | Type | Version | Author |
|--------|------|---------|--------|
| Helix3 - Ajax | ajax | 2.5.6 | JoomShaper |
| AllVideos (JoomlaWorks) | content | — | JoomlaWorks |
| Content - Load Form Maker | content | 3.6.15 | Web Dorado |
| SP PageBuilder System | system | 1.3 | JoomShaper |
| SP Page Builder Pro Updater | system | 1.1 | JoomShaper |
| System - Helix Ultimate Framework | system | 1.1.2 | JoomShaper |
| System - Helix3 Framework | system | 2.5.6 | JoomShaper |
| System - Guru Cron | system | — | iJoomla |
| Guru Teacher Actions | system | 1.0.0 | iJoomla |
| Guru User Update | user | 1.0.0 | iJoomla |
| Payment Processor [PayPal] | gurupayment | — | iJoomla |
| plg_finder_sppagebuilder | finder | 1.6 | JoomShaper |
| plg_search_sppagebuilder | search | 1.5 | JoomShaper |

## Custom Modules (Business-Specific)

These appear to be **custom-developed modules** (author listed as "Unknown" in Russian):

| Module | Version | Description |
|--------|---------|-------------|
| accm_licensetable | 1.0 | ACCM license table |
| accm_projectstable | 1.0 | ACCM projects table |
| customer_licensetable | 1.0 | Customer license table |
| customertable | 1.0 | Customer table |
| mod_table_accm_partners | 1.0.11 | ACCM partners table |
| mod_table_partners | 1.0.11 | Partners table |
| mod_table_partners_unconf | 1.0.11 | Partners (unconfirmed) table |
| mod_user_profile | 1.0.0 | User profile |
| mod_user_profile_cust | 1.0.0 | Customer user profile |
| mod_user_profile1 | 1.0.0 | User profile variant 1 |
| mod_user_profile2 | 1.0.0 | User profile customer variant |
| mod_user_profile3 | 1.0.0 | User profile variant 3 |
| partner_licensetable | 1.0 | Partner license table |
| projectstable | 1.0 | Projects table |

### Other Third-Party Modules

| Module | Version | Author |
|--------|---------|--------|
| Art Table Lite | 1.5.2 | Artetics.com |
| SP Page Builder Admin Menu | 1.3 | JoomShaper |
| SP Page Builder Icons | 1.0.2 | JoomShaper |

## Custom Database Tables

Beyond standard Joomla tables, the database contains custom business tables:

| Table | Row Count | Purpose |
|-------|-----------|---------|
| `jos_partners` | 32 | Partner companies |
| `jos_customers` | 649 | Customer records |
| `jos_projects` | 1,202 | Project records |
| `jos_license` | — | License management |
| `jos_account_manager` | — | Account management |

## iJoomla Guru LMS Data

Extensive LMS tables for course/training management:

| Data | Details |
|------|---------|
| Courses | 3 (How to use Guru, Sales Training, Technical Training) |
| Tables | ~60 Guru-specific tables covering courses, quizzes, certificates, SCORM, subscriptions, media |
| Features used | Quizzes, certificates, SCORM modules, course categories, subscription plans, email notifications, promo codes |

## Users

20+ users including:

| Username | Role (inferred) | Email |
|----------|-----------------|-------|
| vkim_bdizophk (Super User) | Admin | sergey@bolashak-engineering.kz |
| admin | Admin | asdqwe@asdqwe.com |
| accm1 (Anel Maxut) | ACCM user | accm2@roqed.com |
| ijoomla (Roqed Academy) | Teacher | teacher@roqed.com |
| salestest (Sales User) | Sales | sales@test.com |
| techtest (Tech User) | Tech | tech@test.com |
| buh (Buhgalter) | Accounting | buh@roqed.com |

## Recovery Notes

- **This is the most complex subdomain** — a Joomla-based business portal with an LMS, partner/customer management, and custom modules.
- **partners.roqed.com shares the same DocumentRoot** (`/var/www/portal.roqed.com`) — it was an alias or separate entry point into the same Joomla installation.
- The custom modules (accm_*, partner_*, customer_*, mod_user_profile*) are **custom-developed code** — these cannot be reinstalled from public repositories. Recovery requires original source code.
- iJoomla Guru 5.2.2 is a commercial extension — a valid license is needed for reinstallation.
- SP Page Builder 3.6.8 Pro is a commercial extension from JoomShaper.
- Joomla 3.9.22 is **end-of-life** — if recovering, strongly consider migrating to Joomla 4.x or 5.x.
- The database is the most valuable asset here: 649 customers, 1,202 projects, 32 partners, and LMS course data.
