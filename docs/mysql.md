# MySQL — Security & Performance

## Security

- Run `mysql_secure_installation` on new installs — removes test databases, anonymous users, and remote root login.
- Never grant `ALL PRIVILEGES ON *.*` to application users. Grant only what's needed on specific databases.
- Bind to `127.0.0.1` unless remote access is explicitly required (`bind-address = 127.0.0.1`).
- Use separate database users per application/site.
- Disable `LOCAL INFILE`: `local_infile = 0`.
- Audit user grants: `SELECT user, host FROM mysql.user;` — remove any users you don't recognize.

## Performance

- InnoDB buffer pool is the single most impactful setting. Set `innodb_buffer_pool_size` to 50-70% of available RAM on a dedicated DB server, or 25-40% on a shared web/db server.
- Set `innodb_log_file_size = 256M` (or larger for write-heavy workloads).
- Set `innodb_flush_log_at_trx_commit = 2` for better write performance (small durability tradeoff acceptable for most web apps).
- Set `innodb_flush_method = O_DIRECT` to avoid double buffering with OS cache.
- Enable slow query log: `slow_query_log = 1`, `long_query_time = 2`, `log_queries_not_using_indexes = 1`. Review regularly.
- Set `max_connections` to what you actually need (100-300 for most sites), not 1000. Each idle connection consumes RAM.
- Set `query_cache_type = 0` and `query_cache_size = 0` on MySQL 5.7+ / MariaDB 10.2+ (query cache is deprecated and causes contention).
- Use `tmp_table_size = 64M` and `max_heap_table_size = 64M` for in-memory temp tables.
- Set `join_buffer_size = 4M`, `sort_buffer_size = 4M`, `read_rnd_buffer_size = 2M`.
- Run `mysqltuner` or `pt-query-digest` periodically to identify bottlenecks.
