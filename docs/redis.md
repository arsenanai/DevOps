# Redis — Security & Performance

## Security

- Bind to `127.0.0.1` — never expose Redis to the public internet (`bind 127.0.0.1 ::1`).
- Set a strong password: `requirepass <password>` in `redis.conf`.
- Disable dangerous commands in production:
  ```
  rename-command FLUSHALL ""
  rename-command FLUSHDB ""
  rename-command CONFIG ""
  rename-command DEBUG ""
  rename-command KEYS ""
  ```
- Run Redis as a non-root user with its own system account.
- Disable `protected-mode no` only if you have explicit firewall rules.

## Performance

- Set `maxmemory` to a reasonable limit (e.g., `256mb` or `512mb`). Without this, Redis grows until OOM kills it.
- Set `maxmemory-policy allkeys-lru` for cache workloads (evicts least recently used keys when full).
- Use `lazyfree-lazy-eviction yes` and `lazyfree-lazy-expire yes` to free memory in background threads.
- Disable persistence (`save ""`, `appendonly no`) if using Redis purely as a cache — saves disk I/O.
- If persistence is needed, prefer `appendonly yes` with `appendfsync everysec` over RDB snapshots for durability.
- Monitor memory usage: `redis-cli info memory`. Watch for fragmentation ratio — if consistently above 1.5, restart Redis to defragment.
- Use `SCAN` instead of `KEYS` in scripts — `KEYS *` blocks the single-threaded event loop.
