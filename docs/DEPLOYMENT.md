# Deployment and operations - release 4.1

## Prerequisites and topology

Use Docker Engine/Desktop with the Compose v2 plugin and Python 3. Commands are run from the extracted `reconsyde-tracker` folder. Python helpers use only the standard library. An initial planning allocation is 2-4 vCPU, 4-8 GB RAM and 20 GB free disk plus expected attachments/backups; this is an estimate, not a load-tested capacity guarantee. Size the PostgreSQL disk for attachments and growth. Initial build requires access to image registries and Python packages. Runtime needs network access only for configured integrations and certificate issuance, as applicable.

`db` uses PostgreSQL 17 on a named Docker volume; its port is not published. `app` runs FastAPI and binds only to host loopback at port 8000. `worker` processes notification schedules and retries about every 30 seconds. App health probes check PostgreSQL connectivity. App/worker wait for startup dependencies. Attachments are stored in PostgreSQL; there is no separate attachment filesystem to back up. Keep one worker service unless concurrency is separately tested.

## First start (local or controlled UAT)

```sh
python scripts/configure.py
python scripts/preflight.py
docker compose up --build -d
docker compose ps
docker compose logs --tail=100 app worker
```

Open `http://localhost:8000`. On a remote server the loopback binding is intentional: use an SSH tunnel (`ssh -L 8000:127.0.0.1:8000 user@server`) or configure HTTPS below. A bootstrap Super Admin is created only if no users exist. Changing ADMIN_PASSWORD later does not reset existing credentials. Startup imports the bundled workbook once by its content hash. Migrations through schema version 6 use a PostgreSQL advisory lock.

## HTTPS using the bundled Docker proxy

Point a hostname at the server, allow incoming TCP 80 and 443, and add `APP_DOMAIN=tracker.yourcompany.com` to `.env`. Set `COOKIE_SECURE=true`. Run:

```sh
python scripts/preflight.py --https
docker compose -f compose.yaml -f compose.https.yaml up --build -d
docker compose -f compose.yaml -f compose.https.yaml ps
```

The optional Caddy service proxies `app:8000` and persists its certificate data. It needs DNS/certificate-authority reachability; public certificates are not suitable for every private-only network. Use your organisation's TLS load balancer or private CA instead where necessary. The base app port remains loopback-only. Continue using both Compose files for HTTPS stack updates and shutdown. Normal app/db/worker commands in the helpers use the same default project and base file. If you deploy with `-p`, consistently pass that project name to the backup/recovery helpers.

Existing host Caddy can instead use `docs/Caddyfile.example`. Do not bind a second proxy to ports already used by your infrastructure. Reverse-proxy request limit is 21 MB per upload request; application maximum is 20 MiB per file. The UI uploads multiple files separately. Set the deployed HTTPS app URL in Email & AI setup. Secure cookies require HTTPS; local HTTP testing uses COOKIE_SECURE=false. The HTTPS overlay forces secure cookies for app and worker.

## Configuration inventory

| Variable | Purpose |
| --- | --- |
| ADMIN_EMAIL / ADMIN_NAME / ADMIN_PASSWORD | First-install Super Admin identity; not a reset mechanism |
| POSTGRES_PASSWORD | Generated hex password used by PostgreSQL and the database URL |
| SETTINGS_ENCRYPTION_KEY | Encrypts stored integration secrets; preserve across upgrades and restore |
| COOKIE_SECURE | false for local HTTP; true for HTTPS |
| APP_PORT | Host loopback app port, default 8000 |
| APP_DOMAIN | Optional Docker HTTPS proxy hostname |

Keep `.env` private. Do not paste `docker compose config` output into tickets because it expands secrets; use `config --quiet` for validation. Do not include `.env` in shared source archives. Changing POSTGRES_PASSWORD in `.env` alone does not change the password in an existing database volume; plan credential rotation separately.

## Backup SOP

Owner: infrastructure administrator. Frequency/retention: agree with Bancapp management according to RPO/RTO; a nightly backup plus a pre-upgrade backup is a starting operating policy, not a shipped scheduler.

```sh
python scripts/backup.py
python scripts/backup.py --output /secure/location/tracker-preupgrade.dump
```

The helper creates a custom-format PostgreSQL dump, refuses overwriting an existing output and removes incomplete output on failure. The dump includes attachments, users/password hashes, encrypted secrets, settings, pending mail, knowledge and audit history. Copy it to protected off-host storage, encrypt at rest and retain the matching SETTINGS_ENCRYPTION_KEY separately. Keep application version/source and proxy/configuration recovery material. Backups are not encrypted by this script. Caddy certificates are in separate volumes and can normally be reissued; preserve them if your recovery plan requires it. No backup schedule/retention agent is installed automatically.

## Recovery rehearsal / disaster recovery

Use an isolated project/host and a copy of the application folder. Supply the original encryption key. Use a distinct APP_PORT if the live stack is on the same host. Never run tests or recovery against the live database.

```sh
python scripts/restore.py /secure/location/tracker.dump --project-name bancapp-recovery --confirm-empty-restore
docker compose -p bancapp-recovery -f compose.yaml up --build -d app
docker compose -p bancapp-recovery -f compose.yaml ps
```

The helper starts only the recovery database, refuses running app/worker or any existing user tables, and restores in one transaction. It never drops a database or runs pg_restore --clean. After restore it disables mail and sets AI to retrieval mode, and leaves app/worker stopped. Other original connection details remain encrypted in settings; review before reenabling. Login uses restored account credentials, not the bootstrap password. Check user/issue/attachment counts, open evidence, download reports, inspect knowledge and audit, and confirm schema versions. Start the worker only after the environment is ready. Re-enable mail/AI deliberately; queued notification jobs may then resume.

For production recovery, rehearse first, agree a cutover window and restore to a new volume/host. Validate before switching the hostname. The base PostgreSQL image is 17; test upgrades from older dump sources and never reuse a physical database volume across incompatible PostgreSQL major versions.

## Upgrade and rollback SOP

1. Record the current release, Compose project name, configuration and acceptance results. Stop inbound work during the maintenance window.
2. Stop worker, then app; keep db running. Take a backup with the helper. Preserve the old source/image and encryption key.
3. Replace source files with the release; keep the existing `.env` and database volume. Review release notes/migrations.
4. Run preflight, then `docker compose up --build -d` (both files for HTTPS). Inspect health and logs. New migrations apply on startup.
5. Perform login, register/detail, file upload/download, one route, report and controlled email checks. Resume access after sign-off.
6. If rollback is needed, stop writes, preserve failure evidence and any new data, then restore the pre-upgrade backup into an isolated/new volume with the old release. Schema downgrade migrations are not provided. Do not run an old image blindly against a migrated database.

`docker compose restart` preserves data. `docker compose down` preserves named volumes. Never use `docker compose down -v` for an ordinary restart: it removes the database volume.

## Monitoring / troubleshooting SOP

- Routine: inspect service status, app health (`GET /api/health`), worker logs, Notification log, disk/database growth and backup completion. App health is not an email-delivery or end-to-end worker check.
- No remote page: verify HTTPS/DNS/proxy; localhost binding is expected. Port conflict: choose another APP_PORT, or resolve proxy port ownership.
- Login fails: verify restored/current credentials and cookie mode; configured bootstrap variables do not reset passwords. Check role/account activation and recorded login events.
- Email not sent: check enabled mail connection, saved event/group/individual effective rules, current tray/participant access, timezone, worker, manager CC and delivery states. Daily/weekly messages wait until their schedule. Sent means provider accepted, not inbox confirmation.
- Upload rejected: inspect allowed extension, signature, empty file, 20 MiB application limit and proxy request limit. Retry failed files against the saved issue; do not create a duplicate.
- Settings secrets cannot decrypt: restore the original encryption key. Do not generate a replacement key to fix decryption errors; saved secrets must be reentered if the original key is lost.
- Reports lack timing/rankings: imported records may have missing severity/owners and no measured cycles. Link/classify and collect actual workflow evidence; rankings need three completed bug fix cycles.
- Escalation evidence: record time, route/page, request ID and sanitized error type. Keep credentials, personal data and full expanded configuration out of shared logs.

## Go-live acceptance gates

Build/run containers on the intended host; verify TLS and backup recovery; test all role restrictions and client boundaries; exercise product/process return loops, production release gates, intake/attachments, all Excel/PDF reports, notification immediate/daily/weekly rules and actual Outlook/SMTP delivery; check optional AI only if configured. Obtain business-owner and infrastructure sign-off. The included suite passed 96 checks, including PostgreSQL integration tests and offline deployment safeguards, with provider calls mocked; Docker-host execution, real integrations, full browser UAT, load testing and recovery remain deployment gates.
