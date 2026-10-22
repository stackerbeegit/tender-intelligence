#!/usr/bin/env bash
# =============================================================================
# Stackerbee Tender Intelligence — one-command server deployment.
#
# On a fresh Ubuntu server:
#   git clone https://github.com/stackerbeegit/tender-intelligence.git /opt/tender-intelligence
#   cd /opt/tender-intelligence
#   ./deploy.sh                       # first deploy (asks a few questions)
#
# First deploy with the data copied from a laptop (see docs/deployment.md §8):
#   ./deploy.sh --restore-db local-db.dump --restore-docs local-documents.tar.gz
#
# Later:
#   ./deploy.sh                       # pull latest code, rebuild, restart
#   ./deploy.sh --branch v1           # switch the server to branch v1, then deploy it
#                                     # (it stays on v1 for later plain ./deploy.sh runs)
#   ./deploy.sh status | logs [service] | crawl | backup
# =============================================================================
set -euo pipefail

cd "$(dirname "$0")"
APP_DIR="$(pwd)"
COMPOSE_FILE="docker-compose.prod.yml"

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mxx\033[0m %b\n' "$*" >&2; exit 1; }

dc() { docker compose -f "$COMPOSE_FILE" --env-file .env "$@"; }
env_value() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2-; }
set_env() {  # set_env KEY VALUE — values here are hex/keys, never contain '|'
  if grep -qE "^$1=" .env; then sed -i "s|^$1=.*|$1=$2|" .env; else echo "$1=$2" >> .env; fi
}

# --- prerequisites ------------------------------------------------------------
ensure_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    info "Docker not found — installing Docker Engine + Compose plugin (needs sudo)"
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker "$USER" || true
    die "Docker installed. Log out and back in (so your user can run docker), then re-run ./deploy.sh"
  fi
  docker compose version >/dev/null 2>&1 || die "Docker Compose plugin missing: sudo apt-get install docker-compose-plugin"
  docker info >/dev/null 2>&1 || die "Can't talk to Docker. Is it running, and is $USER in the 'docker' group? (log out/in after usermod)"
}

# Small servers (2 GB RAM, no swap) get OOM-killed during image builds:
# apt-get alone can use >1 GB. Add a swap file once if there is none.
ensure_swap() {
  local mem_kb swap_kb
  mem_kb="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)"
  swap_kb="$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo)"
  if (( swap_kb == 0 && mem_kb < 4 * 1024 * 1024 )); then
    info "Low RAM ($(( mem_kb / 1024 )) MB) and no swap — creating a 4 GB swap file (needs sudo)"
    if [[ ! -f /swapfile ]]; then
      sudo fallocate -l 4G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=4096
      sudo chmod 600 /swapfile
      sudo mkswap /swapfile >/dev/null
    fi
    sudo swapon /swapfile
    grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
    echo 'vm.swappiness=10' | sudo tee /etc/sysctl.d/99-swap.conf >/dev/null
    sudo sysctl -q -p /etc/sysctl.d/99-swap.conf
    info "Swap enabled: $(free -h | awk '/^Swap:/ {print $2}')"
  fi
}

# --- .env ---------------------------------------------------------------------
ensure_env() {
  if [[ ! -f .env ]]; then
    info "Creating .env from .env.production.example with fresh secrets"
    command -v openssl >/dev/null || die "openssl is required to generate secrets: sudo apt-get install openssl"
    cp .env.production.example .env
    chmod 600 .env
    set_env SECRET_KEY "$(openssl rand -hex 32)"
    set_env POSTGRES_PASSWORD "$(openssl rand -hex 24)"

    read -r -p "Anthropic API key for AI analysis (Enter to skip for now): " key || true
    [[ -n "${key:-}" ]] && set_env ANTHROPIC_API_KEY "$key"

    default_bind="80"
    if command -v tailscale >/dev/null 2>&1 && ts_ip="$(tailscale ip -4 2>/dev/null | head -1)" && [[ -n "$ts_ip" ]]; then
      default_bind="$ts_ip:80"
      info "Tailscale detected ($ts_ip) — defaulting to serve on the Tailscale network only"
    fi
    read -r -p "Listen address for the web app [$default_bind]: " bind || true
    set_env WEB_BIND "${bind:-$default_bind}"
    info ".env written (keep it private; it is git-ignored)"
  fi

  local missing
  missing="$(grep -E '^(SECRET_KEY|POSTGRES_PASSWORD|POSTGRES_USER|POSTGRES_DB)=(CHANGE_ME.*)?$' .env || true)"
  [[ -z "$missing" ]] || die "Fill these in .env first:\n$missing"
  [[ "$(env_value ANTHROPIC_API_KEY)" == CHANGE_ME* || -z "$(env_value ANTHROPIC_API_KEY)" ]] \
    && warn "ANTHROPIC_API_KEY not set — the app works, but 'Run analysis' will fail until you add it to .env"
  return 0
}

# --- steps --------------------------------------------------------------------
pull_code() {
  local branch="${1:-}"
  if [[ -d .git ]]; then
    if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
      [[ -z "$branch" ]] || die "Local changes in the repo — commit or discard them before switching to '$branch'"
      warn "Local changes in the repo — skipping git pull"
    elif [[ -n "$branch" ]]; then
      info "Fetching and switching to branch '$branch'"
      git fetch origin
      git rev-parse --verify --quiet "refs/remotes/origin/$branch" >/dev/null \
        || die "Branch '$branch' does not exist on origin — push it first"
      if [[ "$(git rev-parse --abbrev-ref HEAD)" != "$branch" ]]; then
        git checkout "$branch"
      fi
      git branch --set-upstream-to="origin/$branch" "$branch" >/dev/null
      git pull --ff-only origin "$branch"
    else
      info "Pulling latest code (branch $(git rev-parse --abbrev-ref HEAD))"
      git pull --ff-only
    fi
  fi
}

# Build one service at a time instead of all in parallel. backend, worker,
# beat and migrate share the same Dockerfile, so after backend is built the
# others come straight from the build cache — one apt-get run, not four.
build_images() {
  local services svc
  services="$(dc config --services)"
  if grep -qx backend <<<"$services"; then
    info "Building backend"
    dc build --progress=plain backend
  fi
  for svc in $services; do
    [[ "$svc" == backend ]] && continue
    info "Building $svc"
    dc build --progress=plain "$svc"
  done
}

wait_healthy() {
  info "Waiting for the backend to become healthy"
  for _ in $(seq 1 60); do
    if dc exec -T backend curl -fsS http://localhost:8000/api/v1/health >/dev/null 2>&1; then
      info "Backend is healthy"; return 0
    fi
    sleep 5
  done
  dc logs --tail=80 migrate backend
  die "Backend did not become healthy in 5 minutes (logs above)"
}

restore_data() {
  local db_dump="$1" docs_tar="$2"
  info "Starting database for restore"
  dc up -d postgres redis
  for _ in $(seq 1 30); do
    dc exec -T postgres pg_isready -U "$(env_value POSTGRES_USER)" >/dev/null 2>&1 && break
    sleep 2
  done
  dc stop backend worker beat >/dev/null 2>&1 || true

  if [[ -n "$db_dump" ]]; then
    [[ -f "$db_dump" ]] || die "No such file: $db_dump"
    info "Restoring database from $db_dump"
    dc exec -T postgres pg_restore -U "$(env_value POSTGRES_USER)" -d "$(env_value POSTGRES_DB)" \
      --clean --if-exists --no-owner --no-privileges < "$db_dump" \
      || warn "pg_restore reported warnings (usually harmless on a fresh database)"
  fi
  if [[ -n "$docs_tar" ]]; then
    [[ -f "$docs_tar" ]] || die "No such file: $docs_tar"
    info "Restoring documents from $docs_tar"
    dc run --rm -T --no-deps backend tar -xzf - -C /app/storage < "$docs_tar"
  fi
}

seed_and_cron() {
  info "Ensuring the GeM source exists (no-op if it already does)"
  dc exec -T backend python -m app.scripts.seed_gem_source

  local line="30 3 * * * cd \"$APP_DIR\" && ./infrastructure/scripts/backup-db.sh >> backups/backup.log 2>&1"
  if ! crontab -l 2>/dev/null | grep -q "backup-db.sh"; then
    info "Installing daily 03:30 backup cron job"
    mkdir -p backups
    (crontab -l 2>/dev/null; echo "$line") | crontab -
  fi
}

deploy() {
  local db_dump="" docs_tar="" branch=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --branch)       branch="${2:?--branch needs a branch name}"; shift 2 ;;
      --restore-db)   db_dump="${2:?--restore-db needs a file}"; shift 2 ;;
      --restore-docs) docs_tar="${2:?--restore-docs needs a file}"; shift 2 ;;
      --no-pull)      NO_PULL=1; shift ;;
      *) die "Unknown option: $1" ;;
    esac
  done

  ensure_docker
  ensure_swap
  ensure_env
  if [[ -n "${NO_PULL:-}" ]]; then
    [[ -z "$branch" ]] || die "--branch and --no-pull cannot be combined"
  else
    pull_code "$branch"
  fi

  info "Building images one at a time (first time takes a few minutes)"
  build_images

  if [[ -n "$db_dump$docs_tar" ]]; then
    restore_data "$db_dump" "$docs_tar"
  fi

  info "Starting all services (migrations run first)"
  dc up -d --no-build --remove-orphans
  wait_healthy
  seed_and_cron

  dc ps
  local bind; bind="$(env_value WEB_BIND)"; bind="${bind:-80}"
  local host="${bind%:*}"; [[ "$host" == "$bind" || "$host" == "0.0.0.0" ]] && host="$(hostname -I | awk '{print $1}')"
  echo
  if [[ "$(env_value COMPOSE_PROFILES)" == *https* && -n "$(env_value DOMAIN)" ]]; then
    info "Deployed. Open: https://$(env_value DOMAIN)/"
  else
    info "Deployed. Open: http://$host/"
  fi
  info "The GeM crawl runs nightly at $(env_value SCHEDULED_CRAWL_HOUR):$(printf '%02d' "$(env_value SCHEDULED_CRAWL_MINUTE)") $(env_value SCHEDULER_TIMEZONE)."
  info "To fill the database now:   ./deploy.sh crawl"
  [[ -n "$db_dump" ]] || info "First admin user:  docker compose -f $COMPOSE_FILE exec backend python -m app.scripts.create_admin --email ... --password ... --name ..."
}

case "${1:-deploy}" in
  deploy|--*) [[ "${1:-}" == deploy ]] && shift; deploy "$@" ;;
  status)     dc ps ;;
  logs)       shift; dc logs -f --tail=200 "$@" ;;
  crawl)      info "Queuing a crawl of all sources now (takes ~10–15 min)"
              dc exec -T worker celery -A app.workers.celery_app call app.workers.tasks.crawl_all_sources
              info "Follow it with: ./deploy.sh logs worker" ;;
  backup)     ./infrastructure/scripts/backup-db.sh ;;
  *) die "Usage: ./deploy.sh [deploy] [--branch NAME] [--restore-db FILE] [--restore-docs FILE] [--no-pull] | status | logs [service] | crawl | backup" ;;
esac