# Technical decisions

Record at least 5 decisions. Include assumptions and limits.

## Decision 1

- Choice: Enabled Redis AOF persistence and added a named volume mounted at `/data`.
- Why: Redis should keep `/counter`'s value after a container restart or recreation. AOF records write operations, so it provides better durability than keeping the data only in memory.
- Alternative: Keep persistence disabled or use RDB snapshots. These were rejected because the counter could reset, or recent updates could be lost between snapshots.
- Trade-off: AOF adds a small amount of disk I/O and may take slightly longer to start because Redis replays the saved operations.
- Evidence / commit: cd17b61
- Production improvement: Configure AOF rewrite/compaction and review `appendfsync` settings to control file growth and balance durability with performance.

## Decision 2

- Choice:  Set resource limits based on the expected workload:
  * App: `256M` memory / `0.5` CPU
  * PostgreSQL: `512M` memory / `1.0` CPU
  * Redis: `128M` memory / `0.25` CPU
  * NGINX: `128M` memory / `0.25` CPU

- Why: PostgreSQL is expected to need the most resources because it is the main stateful service. The Flask app, Redis, and NGINX have relatively light workloads.
- Alternative: No resource limits or giving every service the same limits. No limits were rejected because the brief requires limits, and equal limits do not reflect the different workloads.
- Trade-off: These limits are only starting estimates. If they are too low, containers may run out of resources; if they are too high, resources may be wasted.
- Evidence / commit: edfc5eb
- Production improvement: Monitor the services under real traffic using tools such as `docker stats`, then adjust the limits based on actual CPU and memory usage.

## Decision 3

- Choice: Set `restart: unless-stopped` for all services.
- Why: If a container crashes unexpectedly, Docker will automatically restart it. However, if an operator deliberately runs `docker stop`, the container stays stopped until it is started again.
- Alternative: `restart: "no"` and `restart: always`.
  * `no` was rejected because crashed containers would stay down.
  * `always` was rejected because it would immediately restart a container during `failure_test.py`, making it difficult to measure the failure window.
- Trade-off: `unless-stopped` provides automatic recovery from crashes while still allowing the test script or an operator to deliberately stop a container.
- Evidence / commit: edfc5eb
- Production improvement: Use proper monitoring and alerting in addition to the restart policy, so operators know when a container repeatedly crashes instead of relying only on automatic restarts.

## Decision 4

- Choice: Removed the host port mappings for PostgreSQL and Redis. Both services are now reachable only through the internal `backend` Docker network, using `postgres:5432` and `redis:6379`.
- Why: The application already connects to these services through Docker's internal network, so publishing their ports to the host is unnecessary. Also, because the `backend` network is marked `internal: true`, it is isolated from external networks, so direct host access was not possible through these mappings anyway.
- Alternative: Keep the loopback mappings (`127.0.0.1:15432:5432` and `127.0.0.1:16379:6379`) for easier host-side debugging. This was rejected because the brief explicitly says not to publish PostgreSQL or Redis ports, and changing to unusual ports would not provide real security.
- Trade-off: Host-side debugging with commands such as `psql -h 127.0.0.1 -p 15432` is no longer available. Instead, debugging and administration must be done through `docker exec` or by temporarily re-adding a mapping.
- Evidence / commit: edfc5eb
- Production improvement: Keep database and Redis ports private, and use a controlled administration method such as `docker exec`, a secure bastion, or a private management network when direct access is required.

## Decision 5

- Choice: Store secrets in a local `.env` file that is ignored by Git, and use `${VAR}` in `docker-compose.yml` to load them. Commit a `.env.example` file with safe placeholder values.
- Why: This keeps real secrets out of the Git repository and Docker images while keeping the setup simple for a local Compose lab.
- Alternative: Docker Swarm secrets, BuildKit secrets, or an external secrets manager such as Vault or AWS Secrets Manager. These were rejected because they add complexity or require infrastructure outside the scope of this assessment.
- Trade-off: The `.env` approach is simple and keeps secrets out of Git, but the values are still stored as plain text on the host machine.
- Evidence / commit: 00d9469
- Production improvement: Use a dedicated secrets manager or another secure secrets solution that supports encryption, access control, secret rotation, and auditing.

<!-- ## Decision
- Choice:
- Why:
- Alternative:
- Trade-off:
- Evidence / commit:
- Production improvement:

Cover your base image, health checks, networks, timeouts/retries, restart/resource settings,
storage and any other meaningful choices. -->
