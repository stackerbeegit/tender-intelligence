#!/usr/bin/env bash
# Daily backup of the production database and uploaded documents.
# Keeps the last $KEEP_DAYS days. Run from the repo root on the server, e.g.
# from crontab:
#   30 3 * * * cd /opt/tender-intelligence && ./infrastructure/scripts/backup-db.sh >> backups/backup.log 2>&1
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env"
STAMP="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$BACKUP_DIR"

# Read just the two values needed; `source .env` would choke on values with
# spaces or parentheses (e.g. CRAWLER_USER_AGENT).
env_value() { grep -E "^$1=" .env | tail -1 | cut -d= -f2-; }
POSTGRES_USER="$(env_value POSTGRES_USER)"
POSTGRES_DB="$(env_value POSTGRES_DB)"

$COMPOSE exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom \
  > "$BACKUP_DIR/db-$STAMP.dump"

$COMPOSE exec -T backend tar -czf - -C /app/storage documents \
  > "$BACKUP_DIR/documents-$STAMP.tar.gz"

find "$BACKUP_DIR" -name 'db-*.dump' -mtime "+$KEEP_DAYS" -delete
find "$BACKUP_DIR" -name 'documents-*.tar.gz' -mtime "+$KEEP_DAYS" -delete

echo "$(date -Is) backup ok: db-$STAMP.dump documents-$STAMP.tar.gz"
