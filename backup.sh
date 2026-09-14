#!/usr/bin/env bash
set -euo pipefail

# Load DB credentials the same way the app does
source config/app.env 2>/dev/null || true

BACKUP_DIR="./backups"
TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
BACKUP_FILE="${BACKUP_DIR}/barq_tasks_${TIMESTAMP}.sql"

mkdir -p "$BACKUP_DIR"

echo "Backing up postgres database 'barq_tasks' to ${BACKUP_FILE}..."

docker exec postgres pg_dump \
    -U barq_app \
    -d barq_tasks \
    --clean --if-exists \
    > "$BACKUP_FILE"

if [ -s "$BACKUP_FILE" ]; then
    echo "PASS: backup created successfully (${BACKUP_FILE}, $(wc -l < "$BACKUP_FILE") lines)"
    exit 0
else
    echo "FAIL: backup file is empty or was not created"
    exit 1
fi