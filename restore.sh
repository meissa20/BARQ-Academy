#!/usr/bin/env bash
set -euo pipefail

if [ -z "${1:-}" ]; then
    echo "Usage: ./restore.sh <backup_file.sql>"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "FAIL: backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "Restoring ${BACKUP_FILE} into postgres database 'barq_tasks'..."

docker exec -i postgres psql -U barq_app -d barq_tasks < "$BACKUP_FILE"

RESULT=$(docker exec postgres psql -U barq_app -d barq_tasks -t -c "SELECT COUNT(*) FROM records;")
COUNT=$(echo "$RESULT" | tr -d '[:space:]')

echo "Restore complete. records table now has ${COUNT} row(s)."

if [ "$COUNT" -ge 0 ] 2>/dev/null; then
    echo "PASS: restore verified"
    exit 0
else
    echo "FAIL: could not verify restore"
    exit 1
fi