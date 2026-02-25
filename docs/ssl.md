# Let's Encrypt & SSL — Security & Auto-Renewal

## Security

- Use TLS 1.2 and 1.3 only — disable TLS 1.0 and 1.1:
  - Nginx: `ssl_protocols TLSv1.2 TLSv1.3;`
  - Apache: `SSLProtocol all -SSLv3 -TLSv1 -TLSv1.1`
- Use strong cipher suites. For Nginx:
  ```
  ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
  ssl_prefer_server_ciphers on;
  ```
- Enable HSTS: `add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;`
- Enable OCSP stapling:
  ```
  ssl_stapling on;
  ssl_stapling_verify on;
  resolver 1.1.1.1 8.8.8.8 valid=300s;
  ```
- Redirect all HTTP to HTTPS — no exceptions for production sites.
- Generate DH params with at least 2048 bits: `openssl dhparam -out /etc/ssl/dhparams.pem 2048`.

## Auto-Renewal

- Verify Certbot auto-renewal is active: `systemctl status certbot.timer` or check `crontab -l` for a certbot renew entry.
- If neither exists, set up a cron: `0 3 * * * certbot renew --quiet --post-hook "systemctl reload nginx"` (or apache).
- Test renewal works: `certbot renew --dry-run`. Fix any failures before they cause an outage.
- Check certificate expiry proactively: `openssl x509 -enddate -noout -in /etc/letsencrypt/live/<domain>/fullchain.pem`. Flag certificates expiring within 14 days.
- Ensure the `.well-known/acme-challenge` path is accessible and not blocked by redirects or auth.
