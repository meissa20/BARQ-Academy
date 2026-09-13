# Technical decisions

Record at least 5 decisions. Include assumptions and limits.

## Decision 1

- Choice: Enabled Redis AOF persistence and added a named volume mounted at `/data`.
- Why: Redis should keep `/counter`'s value after a container restart or recreation. AOF records write operations, so it provides better durability than keeping the data only in memory.
- Alternative: Keep persistence disabled or use RDB snapshots. These were rejected because the counter could reset, or recent updates could be lost between snapshots.
- Trade-off: AOF adds a small amount of disk I/O and may take slightly longer to start because Redis replays the saved operations.
- Evidence / commit: cd17b61
- Production improvement: Configure AOF rewrite/compaction and review `appendfsync` settings to control file growth and balance durability with performance.


## Decision
- Choice:
- Why:
- Alternative:
- Trade-off:
- Evidence / commit:
- Production improvement:

Cover your base image, health checks, networks, timeouts/retries, restart/resource settings,
storage and any other meaningful choices.
