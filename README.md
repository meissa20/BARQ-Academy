## Submission status note

This submission is incomplete due to time constraints, and I want to be
upfront about exactly what is and isn't finished rather than present it
as more complete than it is.

**Completed and verified:**
- Investigation, root-cause fixes, and retesting for [N] distinct bugs
  across the app, Docker Compose, and NGINX configuration — documented
  with real commands/output in troubleshooting.md
- Working 2-instance Flask + NGINX + PostgreSQL + Redis stack, with
  network isolation, health checks, restart policies, and resource limits
- validate.py and failure_test.py, both fully built and passing
- backup.sh/restore.sh, tested end-to-end with real evidence
- 5 documented technical decisions with alternatives and trade-offs

**Not completed:**
- CI pipeline (.github/workflows/ci.yml)
- No video demonstration was recorded. I ran out of time before I could
  do a full, unedited 12-18 minute run-through as required, including
  the live port change, third instance, and video_challenge.sh steps.
- log_analysis.md is partially done - questions 1 and 2 are answered
  with real commands and output; questions 3-10 are not yet answered.
- security_review.md, decisions.md follow-ups, docs/ARCHITECTURE.md,
  docs/EVIDENCE_INDEX.md, and AI_USAGE.md are incomplete or not started.

I'd rather submit honest, verified partial work than pad out the
documentation with unverified claims. Everything marked as "completed"
above has real command output backing it in troubleshooting.md and the
relevant scripts/logs in this repo.