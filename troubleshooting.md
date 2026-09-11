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
