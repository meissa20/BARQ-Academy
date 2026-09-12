# Troubleshooting journal

Keep chronological entries. Copy this block for each meaningful investigation.

## Entry 1 / 2026-09-10 / 19:40
- Symptom: /ready endpoint returns {"postgres": "unavailable", "redis": "unavailable"}, status 503
- Hypothesis: App can't reach Postgres — either DATABASE_URL is missing, wrong host, or wrong port
- Command or test:
    docker exec app-01 env | grep -i -E "DATABASE_URL|POSTGRES"
- Actual output:
    DATABASE_URL=postgresql://barq_app:BarqLabOnly_7qN2vK8d@postgres:5432/barq_tasks
- Failed attempt and what changed your thinking:
    I thougth that because backend.internal=true then port 15432 would be inside the container but then i understand that the container port is 5432 and so for redis
- Root cause:
    Password mismatch — compose file sets POSTGRES_PASSWORD=...vK8c, but
    config/app.env's DATABASE_URL contained ...vK8d (typo, last character).
    Confirmed via:
        docker logs postgres | grep "password authentication failed"
- Fix:
    Corrected config/app.env DATABASE_URL to use ...vK8c, matching POSTGRES_PASSWORD.
- Retest evidence:
    curl http://127.0.0.1:8081/ready
    -> {"status": "ready", "dependencies": {"postgres": "ready", "redis": "ready"}}
- Related commit: 2fc6afc
- Remaining uncertainty: None — password now matches exactly on both sides.

## Entry 2 / 2026-09-11 / 5:27
- Symptom: curl http://127.0.0.1:8080 returned connection
  reset/refused even after NGINX container reported healthy.
- Hypothesis: Compose maps host port to container port 81, but nginx.conf
  may be listening on a different port internally.
- Command or test:
    grep listen nginx/nginx.conf
- Actual output:
    listen 80;
- Failed attempt and what changed your thinking:
    there wasn't i got it right from the first time
- Root cause:
    docker-compose.yml published host:8080 -> container:81, but nginx.conf
    listens on port 80 inside the container — nothing was listening on 81,
    so Docker forwarded traffic to an empty port.
- Fix:
    Changed compose port mapping to 127.0.0.1:${PUBLIC_PORT:-8080}:80 to match
    nginx.conf's listen 80 directive.
- Retest evidence:
    curl -v http://127.0.0.1:8080/ -> 200 OK
- Related commit: 20ca24a
- Remaining uncertainty: None.

## Entry 3 / 2026-09-11 / 22:15
- Symptom: Even after fixing the NGINX upstream port (8081->8080) and the
  host publish/listen mismatch (81 vs 80), requests through NGINX
  (curl http://127.0.0.1:8080/) returned 502 Bad Gateway.
- Hypothesis: app-01/app-02 still bind Flask to 127.0.0.1 inside their own
  containers (APP_HOST=127.0.0.1). Loopback only accepts traffic originating
  from within the same container's network namespace — NGINX's requests
  arrive over the backend network via app-01's eth0 interface, not loopback,
  so they'd be refused even though NGINX is correctly configured and on the
  same network.
- Command or test:
    docker exec app-01 env | grep APP_HOST
    docker logs nginx | tail -20
- Actual output:
    APP_HOST=127.0.0.1
    nginx logs showed: connect() failed (111: Connection refused) while
    connecting to upstream, upstream: "http://app-01:8080/"
- Failed attempt and what changed your thinking:
    Initially assumed binding to 127.0.0.1 was fine here because NGINX and
    app-01 communicate over the internal `backend` network, and I reasoned
    that traffic stayed "inside the container network" so loopback would
    still apply. Testing app-01 directly on its previous debug port
    (127.0.0.1:8081, before I removed it) had worked, which reinforced this
    wrong assumption. Realized the distinction only after checking: loopback
    is scoped to a single container's network namespace, not to "the docker
    network" as a whole — any other container, even on an internal-only
    network, arrives via eth0, not loopback. This is the same root cause as
    Entry 1's host-unreachable bug; I hadn't fully applied the lesson to the
    container-to-container case yet.
- Root cause:
    APP_HOST=127.0.0.1 in the compose environment block caused Flask to bind
    only to app-01/app-02's loopback interface, refusing connections from
    NGINX arriving over the backend network's eth0 interface.
- Fix:
    Changed APP_HOST to 0.0.0.0 in the shared x-app environment anchor, so
    Flask listens on all interfaces inside the container (loopback and
    eth0), accepting both internal healthchecks and network-originated
    traffic from NGINX.
    Also removed the temporary debug port mappings (127.0.0.1:8081:8080 and
    127.0.0.1:8082:8080) from app-01/app-02, per the requirement to publish
    only NGINX on the host — app instances are no longer reachable except
    via NGINX or other containers on their shared networks.
- Retest evidence:
    docker compose up -d --force-recreate app-01 app-02 nginx
    curl -s http://127.0.0.1:8080/ | python3 -m json.tool
    -> 200 OK, {"service": "barq-api", "instance_id": "app-01", ...}
    curl -s http://127.0.0.1:8080/health -> 200 OK
    docker port app-01 -> (empty, confirms no host port published)
    docker port app-02 -> (empty, confirms no host port published)
- Related commit: 2fc6afc
- Remaining uncertainty: None for this bug. Still need to verify /instance
  shows both app-01 and app-02 identities across repeated requests through
  NGINX (round-robin load balancing not yet tested).

## Entry 4 / 2026-09-12 / 4:13
- Symptom: app-01 and app-02 showed as (health: starting) indefinitely or
  (unhealthy) in `docker ps`, despite the app responding correctly to manual
  curl requests on /health.
- Hypothesis: The Compose healthcheck probes a different path than the app
  actually exposes.
- Command or test:
    grep -A6 healthcheck docker-compose.yml
- Actual output:
    test: ["CMD", "python", "-c", "import urllib.request;
    urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2)"]
    (app/server.py only defines a route for /health, not /healthz)
- Failed attempt and what changed your thinking:
    Initially assumed the healthcheck failure was still related to the
    APP_HOST bind issue (Entry 3), since that also caused connection
    failures on similar-looking probes. Re-verified after that fix was
    already applied and confirmed working via manual curl:
        docker exec app-01 python3 -c "import urllib.request; \
          print(urllib.request.urlopen('http://127.0.0.1:8080/health', \
          timeout=2).status)"
        -> 200
    Since a direct request to /health succeeded but the container still
    reported unhealthy, this ruled out networking/binding as the cause and
    pointed at the healthcheck's own request path instead.
- Root cause:
    Compose healthcheck hit /healthz, but app/server.py only defines a
    route for /health (no trailing 'z'). Every healthcheck attempt returned
    404, which urllib.request treats as an HTTPError exception, causing the
    healthcheck command to exit non-zero and Docker to mark the container
    unhealthy indefinitely.
- Fix:
    Corrected the healthcheck test in docker-compose.yml's x-app anchor to
    request http://127.0.0.1:8080/health instead of /healthz.
- Retest evidence:
    docker compose up -d --force-recreate app-01 app-02
    docker ps
    -> app-01   Up About a minute (healthy)
    -> app-02   Up About a minute (healthy)
    (full docker ps output also confirms postgres and redis healthy, and
    nginx up and forwarding host 8080 -> container 80 correctly)
- Related commit: 8adaf78
- Remaining uncertainty: None — healthcheck path now matches the actual
  route; both instances report healthy consistently across recreation.

  
## Entry / date / time
- Symptom:
- Hypothesis:
- Command or test:
- Actual output:
- Failed attempt and what changed your thinking:
- Root cause:
- Fix:
- Retest evidence:
- Related commit:
- Remaining uncertainty:

Do not fabricate a failed attempt just to fill the template. Record actual attempts.
