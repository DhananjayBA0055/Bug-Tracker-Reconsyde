# Bancapp Delivery Desk - Docker handover

Release 4.1 | 18 November 2026

1. Read `docs/Bancapp_Deployment_Features_and_SOP_Manual.pdf` and `docs/DEPLOYMENT.md`.
2. Install Docker with Compose v2 and Python 3. Extract the entire folder; do not run the HTML preview as the application.
3. From this folder: `python scripts/configure.py` (choose your Super Admin credentials).
4. Run `python scripts/preflight.py` and then `docker compose up --build -d`.
5. Inspect `docker compose ps`; open `http://localhost:8000`. For a remote server use an SSH tunnel or the documented HTTPS proxy.
6. Create staff, review role rights/dropdowns/SLA, and complete one product-route and one process-route acceptance test.
7. Configure email and notification policy, test with controlled recipients, then enable production delivery. AI is optional; verified knowledge retrieval works without a model key.
8. Take a backup and complete a recovery rehearsal before go-live.

The bundled source tracker imports 99 historical issues on first startup. They are source records, not synthetic demonstration issues. The standalone preview uses synthetic data. Do not delete source data files to change seeding behavior; request a reviewed clean-database migration if required.

96 automated checks pass, including backend tests against a disposable PostgreSQL server and seven offline deployment-utility safeguard tests. Provider calls are mocked. Docker execution, live Outlook/Azure delivery, full browser UAT, host sizing/load and a real Docker-volume recovery rehearsal remain server acceptance checks.

Contents: application and worker; PostgreSQL schema/migrations 1-6; Dockerfile/Compose; optional Caddy HTTPS service; original workbook and mapping/field matrix; test suite; deployment/backup/restore utilities; branded manual; standalone UI preview; CSV/XLSX dropdown templates. There are no passwords, tenant secrets or prebuilt container images in this archive. First build needs internet access to obtain base images and Python dependencies.
