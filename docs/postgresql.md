# PostgreSQL — Security & Performance

## Security

- Review `pg_hba.conf` — use `scram-sha-256` (not `md5` or `trust`) for all connections.
- Bind to `127.0.0.1` unless remote access is needed (`listen_addresses = 'localhost'`).
- Use separate roles per application with minimal privileges (`GRANT CONNECT`, `GRANT USAGE`, `GRANT SELECT/INSERT/UPDATE/DELETE` on specific schemas).
- Disable superuser access for application roles.
- Set `log_connections = on` and `log_disconnections = on` to audit access.

## Performance

- Set `shared_buffers` to 25% of total RAM.
- Set `effective_cache_size` to 50-75% of total RAM (tells the planner how much OS cache to expect).
- Set `work_mem = 16MB` (adjust per workload — multiply by `max_connections` to estimate peak usage).
- Set `maintenance_work_mem = 256MB` for faster VACUUM and index creation.
- Set `wal_buffers = 64MB`.
- Set `checkpoint_completion_target = 0.9`.
- Set `random_page_cost = 1.1` for SSD storage (default 4.0 assumes spinning disks).
- Enable `pg_stat_statements` extension for query performance monitoring.
- Configure autovacuum aggressively for write-heavy tables:
  ```
  autovacuum_vacuum_scale_factor = 0.05
  autovacuum_analyze_scale_factor = 0.025
  ```
- Run `EXPLAIN ANALYZE` on slow queries before adding indexes blindly.
