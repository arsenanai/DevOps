# ROQED Partners Portal — Management Guide

**URL:** https://partners.roqed.com
**Platform:** Joomla 3.9.22
**Database:** portal_roqed
**Admin panel:** https://partners.roqed.com/administrator

---

## User Roles

| Role | Group ID | Users | Purpose |
|------|----------|-------|---------|
| **Super Users** | 8 | 1 | Full Joomla admin — /administrator access (vkim_bdizophk) |
| **Account Manager** | 15 | 1 | Approves partners & projects (cannot create license keys) |
| **Buhgalter** | 16 | 1 | Financial approval of licenses |
| **PortalAdmin** | 13 | 2 | Can create license keys, manage portal (dmitrii, +1) |
| **Partner** | 12 | 27 | Distributors — see only their own licenses |
| **haveacc** | 10 | 80 | Basic portal access |
| **Customer** | 17 | 585 | End customers — see only their own licenses |
| **Learn** | 14 | 11 | Access to ROQED Academy (LMS) |
| **submittedform** | 11 | 8 | Submitted registration, pending approval |

---

## License Lifecycle (Step by Step)

```
Partner registers project → PortalAdmin approves project →
PortalAdmin creates license → Buhgalter approves financially →
License key delivered to customer
```

### Step 1 — Partner registers a project

- Page: **Project registration** (`/index.php?option=com_content&view=article&id=9`)
- Partner fills in: product, customer details, key count, license type
- Data goes into `jos_projects` table with `tobelicensed = 0`

### Step 2 — PortalAdmin approves the project

- Page: **Approve project** (`/index.php?option=com_content&view=article&id=12`)
- Reviews project details, sets `tobelicensed = 1`

### Step 3 — PortalAdmin creates the license

- Page: **Licensing** (`/index.php?option=com_content&view=article&id=7`)
- Dropdown shows only approved projects (where `tobelicensed = 1`)
- Select project → form auto-fills: product, customer name, email, country, city, phone, partner info
- Fields to set:
  - **Product**: ROQED Science / ROQED Physics Lab
  - **License type**: admin / user
  - **User premium**: user / premium
  - **Keys count**: number of license keys
  - **Devices count**: number of devices per key
  - **Start date / End date**: validity period (auto-calculated: demo = 14 days, standard = 365 days, custom duration overrides)
- Submit → generates license key in `XXXX-XXXX-XXXX-XXXX-XXXX` format
- Stored in `jos_license` with `buh_confirmation = "Not approved"`

### Step 4 — Buhgalter (accountant) approves

- Page: **License approve** (`/index.php?option=com_content&view=article&id=16`)
- Reviews license, changes `buh_confirmation` from "Not approved" → "Approved"

### Step 5 — License is visible to Partner and Customer

- Partners see their licenses on **Licenses** page (filtered by `emdistr = partner's email`)
- Customers see their licenses on their dashboard (filtered by `emzakaz = customer's email`)

---

## Key Pages by Role

### Account Manager

| Page | Description |
|------|-------------|
| Licensing | Create new licenses from approved projects |
| Approve a partner | Approve new partner registrations |
| Approve project | Approve partner-submitted projects |
| Partners List | View all partners |
| Customers | View all customers |
| Projects | View all projects |

### Buhgalter

| Page | Description |
|------|-------------|
| License approve | Financially approve/reject licenses |

### Partner

| Page | Description |
|------|-------------|
| Partner portal | Dashboard |
| Licenses | Their own licenses only |
| Project registration | Submit new projects |
| Your company | Company profile |
| Customer registration | Register new customers |
| Downloads | Software downloads |

### Customer

| Page | Description |
|------|-------------|
| Licenses | Their own licenses only |
| Check license | Verify a license key |
| Support | Get help |

---

## License Stats (as of Feb 2026)

- **1,433** total licenses
- **1,405** approved (1,177 user + 228 admin)
- **28** pending approval (15 user + 13 admin)
- **585** customers, **27** partners

---

## Useful DB Queries

### Check a customer's licenses

```sql
SELECT * FROM jos_license WHERE emzakaz = 'customer@email.com';
```

### Check a partner's licenses

```sql
SELECT * FROM jos_license WHERE emdistr = 'partner@email.com';
```

### List all pending (unapproved) licenses

```sql
SELECT id, product, licenseno, zakazchik, distr, selldate, enddate
FROM jos_license WHERE buh_confirmation = 'Not approved';
```

### Count licenses by partner

```sql
SELECT distr, emdistr, COUNT(*) as total
FROM jos_license GROUP BY distr, emdistr ORDER BY total DESC;
```

### Find a user and their role

```sql
SELECT u.id, u.username, u.email, u.block, ug.title
FROM jos_users u
JOIN jos_user_usergroup_map m ON u.id = m.user_id
JOIN jos_usergroups ug ON m.group_id = ug.id
WHERE u.email = 'user@example.com';
```

---

## Technical Details

### Custom Joomla Modules

| Module | Path | Purpose |
|--------|------|---------|
| mod_licensing | `/modules/mod_licensing/` | License creation form + customer autocomplete |
| partner_licensetable | `/modules/partner_licensetable/` | Partner's license table (filtered by partner email) |
| customer_licensetable | `/modules/customer_licensetable/` | Customer's license table (filtered by customer email) |
| accm_licensetable | `/modules/accm_licensetable/` | Account Manager's license table (all licenses) |

### Database Tables

| Table | Purpose |
|-------|---------|
| `jos_license` | Main license registry (1,433 records) |
| `jos_projects` | Project registrations from partners |
| `jos_users` | Joomla user accounts |
| `jos_user_usergroup_map` | User-to-role assignments |
| `jos_usergroups` | Role definitions |

### Key Files

- `/configuration.php` — Joomla config (DB credentials, site secret, mail settings)
- `/modules/mod_licensing/tmpl/default.php` — License creation form template
- `/modules/mod_licensing/helper.php` — Customer name autocomplete (AJAX)
- `/modules/mod_licensing/helper2.php` — Auto-fill customer email, country, city, phone (AJAX)

---

## Security Notes

- The PHP code in `helper.php`, `helper2.php`, and all `fetch.php` modules contains **SQL injection vulnerabilities** — user input is concatenated directly into queries without parameterized statements.
- The site runs on **Joomla 3.9.22** which is end-of-life. Consider migrating to Joomla 4.x+ for continued security updates.
