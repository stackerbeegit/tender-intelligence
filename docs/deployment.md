# Deployment (internal Stackerbee server)

The app is an internal sales-pipeline tool, so it runs on one private server with
Docker Compose and is reachable only from the team's network. Everything below uses
`docker-compose.prod.yml`.

```
            ┌──────────── server (Docker) ─────────────────────────────┐
 team ──▶   │ web (nginx: built React app, /api → backend)  :80         │
 browser    │ backend (FastAPI)   worker (Celery)   beat (01:00 IST)   │
            │ migrate (runs once per deploy)                            │
            │ postgres (pgvector)   redis          volumes: db, docs    │
            └───────────────────────────────────────────────────────────┘
```

Only `web` publishes a port. Postgres and Redis are reachable inside the Docker
network only.

## Quick start: `deploy.sh`

[`deploy.sh`](../deploy.sh) does steps 4–7 for you. On the server:

```bash
git clone https://github.com/stackerbeegit/tender-intelligence.git /opt/tender-intelligence
cd /opt/tender-intelligence
./deploy.sh                    # or, to bring laptop data along:
./deploy.sh --restore-db local-db.dump --restore-docs local-documents.tar.gz
```

On first run it:
- installs Docker if it's missing
- creates `.env` with freshly generated secrets, asking for the Anthropic key and the
  listen address (it defaults to the Tailscale IP when Tailscale is installed)
- builds and starts the stack, and waits until it's healthy
- creates the GeM source
- installs the 03:30 backup cron job

Run it again after every `git push` to deploy the update. Other commands:
`./deploy.sh status`, `./deploy.sh logs worker`, `./deploy.sh crawl` (fill the
database now), `./deploy.sh backup`.

The sections below describe the same steps by hand.

## 1. What you need

- A Linux server (Ubuntu 22.04/24.04), **2 vCPU / 4 GB RAM / 40 GB disk**, switched on
  24×7. The nightly crawl runs at 01:00 IST.
- Outbound internet access to `bidplus.gem.gov.in` (crawling) and `api.anthropic.com`
  (AI analysis).
- A way for the team to reach it privately. Tailscale is recommended (step 3).

## 2. Push the code (on your laptop)

The server deploys from GitHub, so commit and push first:

```bash
git add -A && git commit -m "..." && git push origin main
```

## 3. Prepare the server

```bash
# Docker Engine + Compose plugin
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER        # log out and back in once after this

# Recommended: private access through Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up                    # sign in with the Stackerbee Tailscale account
tailscale ip -4                      # note this 100.x.y.z address
```

Install Tailscale on each team member's laptop or phone and sign in to the same
account. Only those devices can open the app.

## 4. Get the code and configure it

```bash
sudo mkdir -p /opt/tender-intelligence && sudo chown $USER /opt/tender-intelligence
git clone https://github.com/stackerbeegit/tender-intelligence.git /opt/tender-intelligence
cd /opt/tender-intelligence

cp .env.production.example .env
openssl rand -hex 32    # paste as SECRET_KEY
openssl rand -hex 24    # paste as POSTGRES_PASSWORD
nano .env               # fill every CHANGE_ME, add ANTHROPIC_API_KEY
```

To serve the app on the Tailscale network only, set `WEB_BIND=100.x.y.z:80` (the IP
from step 3). Docker publishes ports past `ufw`, so binding to the Tailscale IP is what
actually keeps the app off the public internet.

## 5. Build and start

```bash
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
docker compose -f docker-compose.prod.yml ps
```

`migrate` should show **Exited (0)**. Every other service should be **running**, with
`backend` marked **healthy**. If something is wrong, check the logs:

```bash
docker compose -f docker-compose.prod.yml logs migrate backend worker beat
```

## 6. One-time setup

```bash
DC="docker compose -f docker-compose.prod.yml --env-file .env"

# Create the GeM source, with crawling enabled
$DC exec backend python -m app.scripts.seed_gem_source

# User accounts are created by Stackerbee's own process. For the first admin, this
# CLI is available:
$DC exec backend python -m app.scripts.create_admin --email you@stackerbee.com --password '<strong>' --name "Your Name"
```

**First data.** Either wait for 01:00, or run one crawl now. It takes about 10–15
minutes:

```bash
$DC exec worker celery -A app.workers.celery_app call app.workers.tasks.crawl_all_sources
$DC logs -f worker      # wait for "crawl_all_sources[...] succeeded"
```

Open `http://<server-or-tailscale-ip>/` and sign in. `http://<ip>/api/v1/health` should
return `{"status":"ok"}`.

**Optional: HTTPS on Tailscale.** Run `sudo tailscale serve --bg 80` to serve the app
at `https://<server-name>.<tailnet>.ts.net` with an automatic certificate. If you do,
set `WEB_BIND=127.0.0.1:80`.

**Optional: HTTPS on a public domain** (e.g. `sales.stackerbee.com`). A Caddy
container gets a Let's Encrypt certificate and renews it automatically.

1. Add a DNS **A record** for the domain pointing at the server's public IP.
2. Open ports 80 and 443 in the cloud firewall / security group (`sudo ufw allow 80,443/tcp`).
3. In `.env`:
   ```bash
   COMPOSE_PROFILES=https
   DOMAIN=sales.stackerbee.com
   WEB_BIND=127.0.0.1:8080
   ```
4. `./deploy.sh`, then check `$DC logs caddy` for `certificate obtained successfully`.

This makes the app reachable from the whole internet, not only the team's network.

## 7. Backups

```bash
crontab -e
# add:
30 3 * * * cd /opt/tender-intelligence && ./infrastructure/scripts/backup-db.sh >> backups/backup.log 2>&1
```

This keeps 14 days of database dumps and document archives in `backups/`. Copy that
folder off the server regularly (to S3, Google Drive, another machine). A backup that
only lives on the same disk doesn't protect against losing the disk.

To restore a database dump:

```bash
$DC exec -T postgres pg_restore -U stackerbee -d stackerbee_tender --clean --if-exists < backups/db-YYYYMMDD-HHMMSS.dump
```

## 8. Optional: bring over local data

To start with the tenders already collected on a laptop instead of an empty
database, copy two files:

| File | Contents |
|---|---|
| `backups/local-db-*.dump` | the whole database: tenders, users, GeM source, crawl history |
| `backups/local-documents-*.tar.gz` | uploaded or processed document files |

Make fresh ones on the laptop with:

```bash
pg_dump -h localhost -U stackerbee -d stackerbee_tender --format=custom --no-owner --no-privileges -f backups/local-db.dump
tar -czf backups/local-documents.tar.gz -C storage documents
scp backups/local-db.dump backups/local-documents.tar.gz server:/opt/tender-intelligence/
```

Then on the server, after step 5 (so migrations have created an empty schema):

```bash
cd /opt/tender-intelligence
DC="docker compose -f docker-compose.prod.yml --env-file .env"
$DC stop backend worker beat
$DC exec -T postgres pg_restore -U stackerbee -d stackerbee_tender --clean --if-exists --no-owner < local-db.dump
$DC run --rm -T --no-deps backend tar -xzf - -C /app/storage < local-documents.tar.gz
$DC up -d
```

This brings over the laptop's users and GeM source too, so **skip step 6** (seeding and
creating an admin). Log in with the same accounts as on the laptop. Change those
passwords if they were only ever meant for local testing.

## 9. Deploying updates

```bash
cd /opt/tender-intelligence
./deploy.sh                 # pulls the branch the server is on, rebuilds, restarts
```

To deploy a different branch (for example a release branch `v1`), push it to GitHub and run
once on the server:

```bash
./deploy.sh --branch v1
```

The server stays on that branch, so later plain `./deploy.sh` runs keep deploying it. Check
which branch is live with `git -C /opt/tender-intelligence branch --show-current`.

Migrations run automatically through the `migrate` service before the app restarts.
Data lives in Docker volumes (`pgdata`, `redisdata`, `documents`) and survives rebuilds.
**Don't run `down -v`**: that deletes the volumes.

## 10. Day-to-day checks

| What | Command |
|---|---|
| Is everything up? | `$DC ps` |
| Did last night's crawl run? | `$DC logs --since 24h worker \| grep crawl_all_sources` |
| Next scheduled crawl | beat logs `Scheduler: Sending due task daily-crawl-all-sources` at 01:00 |
| Crawl history in the app | Sources page → last successful crawl / status |
| Restart one service | `$DC restart worker` |

The crawl time is set by `SCHEDULED_CRAWL_HOUR` / `SCHEDULED_CRAWL_MINUTE` in `.env`.
After changing it, run `$DC up -d beat`.
