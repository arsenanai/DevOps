# Server Operations Guidelines

Rules for AI agents and operators working on servers via terminal.

---

## Phase 1: Before You Touch Anything

### Environment Identification
Before performing any work, determine the context:
- What OS and distro is this? (`cat /etc/os-release`)
- What is the role of this server? (web, database, mail, proxy, etc.)
- Is this production, staging, or development? This changes the risk level of every action.
- Which user are you operating as? (`whoami`, `id`) — avoid unnecessary `sudo`.
- What is the current server load? (`uptime`, `df -h`, `free -h`)

### Read Before You Write
Before modifying any config file, read and understand it fully. Don't append to a file without knowing what's already in it — you might create duplicate or conflicting directives.

### Filesystem Awareness
Always be aware of what you are inspecting — whether it's an actual directory, a symbolic link, a mount, or something else. Use `ls -la`, `stat`, `readlink -f`, and `mountpoint` to verify.

### Security First
Before making any other changes, scan for security red flags and address them:
- SSH root login enabled (`PermitRootLogin yes`)
- Passwords or API keys in plaintext in config files
- World-writable directories or files (`chmod 777`)
- Outdated packages with known CVEs (`apt list --upgradable`, `yum check-update`)
- Firewall with no rules or everything open (`iptables -L`, `ufw status`)
- Unattended services listening on public interfaces

---

## Phase 2: Backups & Safety Nets

### Safe Deletion
Move unneeded files or folders to `~/.Trash` instead of deleting them, to avoid data loss. Create the Trash directory in the home folder if it doesn't exist.

### Backups Before Changes
Before making any changes, make sure you have a backup of your data:
- For databases: dump using the appropriate tool (`mysqldump`, `pg_dump`, `mongodump`).
- For websites: back up the document root and any related config.
- For config files: copy the original with a timestamped suffix (e.g., `cp nginx.conf nginx.conf.bak.20260224`).
- Analyze the `~/backups` folder to understand existing backup structure.
- **Verify the backup is valid** — not zero-byte, readable, and restorable. A backup you can't restore isn't a backup.

### Periodic Backups
Ensure the server has scheduled backups in place. Check `crontab -l` and `/etc/cron.*` for existing jobs. The following should be backed up periodically:
- **Databases**: Daily dumps (e.g., `mysqldump --all-databases`, `pg_dumpall`) rotated and compressed, retained for at least 7 days.
- **Website files**: Daily or weekly archive of document roots (e.g., `/var/www`, `/home/*/public_html`).
- **Critical configs**: Daily backup of `/etc/nginx`, `/etc/apache2`, `/etc/mysql`, `/etc/php`, `/etc/letsencrypt`, and any application-specific config directories.
- **Backup storage**: Backups should be stored in `~/backups` with date-stamped subdirectories, and ideally replicated off-server.
- If periodic backups are not configured, flag this to the user and offer to set them up.

### Rollback Strategy
If a change breaks something, revert the config from the `.bak` copy and restart the affected service before investigating further. Fix under stable conditions, not under an outage.

---

## Phase 3: Operational Rules

### Process & Service Safety
- Before restarting or stopping a service, check what depends on it (`systemctl list-dependencies --reverse`) and who's connected.
- Never kill processes by PID without first confirming what the process is (`ps -p <pid> -o args=`). PIDs can be reused.
- Check if a service is managed by systemd, supervisord, docker, etc. before manipulating it directly.

### Filesystem & Disk
- Check available disk space (`df -h`) before writing large files, extracting archives, or running backups.
- Never follow or modify files under `/proc`, `/sys`, or `/dev` unless explicitly instructed.
- Before running resource-heavy commands (compilation, compression, large `find` operations), consider the server's current load. Saturating CPU or RAM on a shared or production server affects all services.

### Log Management
Ensure log files don't grow unbounded and consume disk space:
- Verify `logrotate` is installed and active (`logrotate --version`, `cat /etc/logrotate.conf`).
- Check that all major services have logrotate configs in `/etc/logrotate.d/` (nginx, apache, mysql, php-fpm, application logs).
- Logs should be rotated daily, compressed, and retained for a reasonable period (7-30 days).
- Scan for oversized log files: look in `/var/log`, application log directories, and mail logs for files exceeding expected size.
- If a service is missing logrotate configuration, flag it and offer to create one.
- For `journald`, ensure `SystemMaxUse` is set in `/etc/systemd/journald.conf` to cap journal size.

### Networking
- Before changing firewall rules or SSH config, confirm you won't lock yourself (or the user) out. On remote servers, this is unrecoverable without console access.
- Check listening ports (`ss -tlnp`) before binding new services to avoid conflicts.
- Before touching DNS records or SSL certificates, verify current state and expiry (`dig`, `openssl s_client -connect host:443`). A bad DNS change can take hours to propagate back, and an expired cert takes a site down instantly.

### User & Permission Context
- Always check which user you're operating as before running commands. Avoid unnecessary `sudo`.
- Be aware of file ownership implications — files created as root in a user's directory can break applications.

### Credentials & Secrets
- Use passwordless commands. Don't use any secret keys. If this is not possible, provide guidance depending on the situation.
- Never hardcode credentials in scripts.
- Never pass passwords as command-line arguments — they are visible in `ps` output.
- Prefer SSH keys over password authentication.
- Check that `.bash_history` doesn't contain leaked secrets.

### Cron & Scheduled Tasks
- Before making changes, check `crontab -l` (for current user and root) and `/etc/cron.*` directories.
- A cron job might be running backups, log rotations, or deployments. Editing files mid-run or disabling a service that cron depends on causes silent failures.
- Never modify a crontab without understanding every entry in it first.

### Containers & Virtualization
- Distinguish between the host system and containers/VMs. A `docker exec` context is not the host.
- Before removing containers or images, check if volumes hold persistent data.
- Check `docker-compose.yml` or equivalent before modifying containers individually.
- Don't `docker stop` a container managed by compose, swarm, or Kubernetes — use the orchestrator.
- Check if containers have restart policies that will respawn them.

### Logging & Audit Trail
- Before troubleshooting, check relevant logs first (`journalctl -u <service>`, application logs). Diagnose before acting.
- When making changes, briefly note what was changed and why (e.g., append a comment with date to config files).

---

## General Discipline
- Prefer dry-run or check modes when available (`rsync --dry-run`, `ansible --check`, `rm -i`).
- Never pipe untrusted URLs directly to `sh` or `bash` without the user reviewing the script first.
- When running destructive or broad commands (e.g., `chmod -R`, `chown -R`, `find ... -delete`), double-check the path scope — one wrong `/` can be catastrophic.

---

## Stack-Specific Security & Performance Docs

Detailed security hardening and performance tuning for each technology:

| Topic | Document |
|-------|----------|
| Nginx | [docs/nginx.md](docs/nginx.md) |
| Apache | [docs/apache.md](docs/apache.md) |
| Let's Encrypt & SSL | [docs/ssl.md](docs/ssl.md) |
| PHP, PHP-FPM, Extensions & Composer | [docs/php.md](docs/php.md) |
| MySQL | [docs/mysql.md](docs/mysql.md) |
| PostgreSQL | [docs/postgresql.md](docs/postgresql.md) |
| Redis | [docs/redis.md](docs/redis.md) |
| WordPress | [docs/wordpress.md](docs/wordpress.md) |
| Joomla | [docs/joomla.md](docs/joomla.md) |
| Laravel | [docs/laravel.md](docs/laravel.md) |
| Vue.js | [docs/vuejs.md](docs/vuejs.md) |
| Vite | [docs/vite.md](docs/vite.md) |
| Docker | [docs/docker.md](docs/docker.md) |
