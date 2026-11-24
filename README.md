# Bancapp Delivery Desk - Docker deployment release 4.1

A PostgreSQL-backed bug management application based on Bancapp's supplied reconciliation-platform tracker, extended with business roles, two enforced testing routes, email automation, employee reporting, a verified resolution library and an L1 chatbot.

The package includes full source, 99 source issues, the original workbook, Bancapp's logo, branded report generators, schema migrations, tests and Docker configuration. It is not deployed to Bancapp's infrastructure.

## Start the application

Install Docker Engine / Docker Desktop with Compose v2, and Python 3 for initial configuration. Extract the folder, open a terminal in it, and run:

```sh
python scripts/configure.py
docker compose up --build -d
docker compose ps
```

Use `python3` where needed. Open **http://localhost:8000**. Sign in using the administrator email and password you chose. The initial account is **Super Admin**. No default password is shipped.

Three services start: PostgreSQL, the FastAPI application, and the notification worker. The frontend needs no Node installation or build step. The configuration script generates a database password and an encryption key for saved mail/AI secrets. Keep `.env` private and preserve its encryption key in your backup process. Rotating the encryption key without re-encrypting stored secrets makes those connections unreadable.

## Roles and teams

| Role | Default rights |
| --- | --- |
| Product Developer | Receive/reassign product work, acknowledge, submit resolution and RCA |
| Process Developer | Receive/reassign process work, acknowledge, submit resolution and RCA |
| Process Designer | Raise/reassign bugs; test, return and close their designated process fixes |
| Quality Analyst | Raise/reassign bugs; test, return and close their designated product fixes |
| Manager | View dashboards, employee performance, reports and internal records |
| Admin | Manage users, role rights, dropdowns, releases, email/AI connections and external knowledge approval |
| Super Admin | All administration; create/edit protected Super Admin accounts |
| Client | Future client portal: raise issues for assigned clients, shared discussion, attachments, approved knowledge and chatbot |

Teams: **Process Team**, **Product Team**, **QA Team**. Admins can change role permissions and individual grant/deny overrides from the UI. Workflow ownership rules remain enforced even when a general permission is granted. At least one active Super Admin must remain. On upgrade from v1, the first existing Admin becomes Super Admin, Editors become Product Developers, and Viewers become Managers.

## Enforced workflow

**Process route:** Process Designer reports and assigns to Process Developer -> developer acknowledges/fixes -> Process Designer tests -> closes or returns to the developer.

**Product route:** Process Designer/QA reports and assigns to Product Developer -> developer acknowledges/fixes -> designated QA tests -> closes or returns to the developer.

Each newly assigned internal issue needs named developer and tester accounts. The developer must supply **both resolution and RCA** before submitting for testing. Only the designated tester with the correct business role can accept or return the fix. QA/Designer records the test outcome. Reopening withdraws the article from the resolution library and starts another measured correction cycle.

Do not use manual status edits to bypass the workflow. Imported historical issues must be linked through **Assign / reassign** before changing workflow state. Existing source classifications, statuses and evidence gaps remain visible.

## Included features

- **Admin → Notification centre:** event switches and immediate/daily/weekly/off schedules; role, team and custom-group defaults; individual overrides; mandatory locks; editable subject/body templates; safe sample previews; separate administration rights. See the notification guide in `docs/USER_GUIDE.md`.
- Original 62 tracker fields, source history and delivery/handover fields.
- Unique sequential bug IDs, search, filters, table and workflow board, client views, releases and audit.
- User administration and rights editing in the frontend; CSV/XLSX bulk upload with preview, validation and transactional apply.
- Dropdown add, rename, delete and CSV/XLSX bulk operations; historical record values are retained. The enforced workflow states, severity policy, Yes/No and the three business teams are structural controls rather than arbitrary labels.
- Manager employee dashboard with drilldown: reported-against attribution, assigned bugs, recorded response/fix/closure time, returned fixes, repeat patterns, raised issues, testing activity and current trays.
- Team response/fix averages weighted by recorded cycles. Best/worst fix-speed rankings require at least three completed fix cycles per person; consider team, severity and complexity before assessing overall performance.
- Email on issue creation, details changes, workflow actions, comments and attachments. Attached named participants receive notifications, with configured/reporting managers in CC.
- Day-end open-tray reports and deduplicated response/resolution SLA breach messages, processed by the persistent worker with retries and a delivery log.
- Screenshot/video and supporting Word, Excel, CSV and PDF files up to **20 MB per file**. Supported extensions: PNG/JPG/JPEG/WebP/GIF, MP4/WebM/MOV, DOC/DOCX, XLS/XLSX, CSV and PDF.
- Branded Excel and PDF downloads for the dashboard, issue register, clients, releases, requirement coverage, employee performance, user register, audit and knowledge library. Excel includes the full register; PDF uses readable register summary columns, with full per-bug PDF/Excel downloads. Other wide PDF reports are split into sections with repeated identifiers.
- An automatically built resolution/RCA library from newly verified closures; reopened issues are withdrawn.
- An L1 chatbot available to all signed-in roles. Verified knowledge search works immediately without a model key. Optional Azure OpenAI/OpenAI generates cited answers using only matching articles visible to that account.

## Configure users and dropdowns

In **Team & access**, add staff, choose roles/teams, and enter reporting-manager emails. Use **Bulk users** to download a template, then upload CSV or XLSX. Headers must be in row 1. Existing accounts match by email. Use semicolons for manager/client lists, JSON such as `{"raise":true}` for rights overrides, and 12+ character initial passwords for new accounts. Passwords are not echoed in the preview or exported user register. There is no invite/password-reset email flow.

In **Settings**, use the role-rights matrix, SLA policy, dropdown editor or bulk dropdown import. Bulk master columns: `group`, `operation`, `value`, `new_value`; operations are `add`, `rename`, `delete`. Preview before applying. Bulk requests with any invalid rows apply no changes.

## Outlook / Azure email setup

Open **Email & AI setup** as Admin. Choose:

1. **Outlook / Microsoft Graph**: enter sender mailbox, Azure tenant ID, app/client ID and client secret. Your Microsoft 365 administrator must grant the app `Mail.Send` application permission and administrator consent, and restrict mailbox scope according to your organization's policy.
2. **SMTP with STARTTLS / SMTP over SSL**: enter host, port, username and secret. Use this only where your Exchange/relay policy permits it. Graph is the supported modern choice for Microsoft 365 environments that do not allow password-based SMTP.

Enter manager CC addresses (or create active Manager accounts), the deployed app URL, report timezone and day-end time. Default time is **18:00 Asia/Kolkata**. Enable and save the connection, queue a test message, and inspect **Notification log**. Saving a configuration does not itself send a test message. Keep the worker running. Emails contain a brief issue summary and a sign-in link, not attachment bytes or internal note bodies.

No real mailbox credentials are supplied or used during the package's tests. Live provider delivery must be verified using your own connection. `sent` means accepted by the configured provider, not proof of final recipient delivery. SMTP/Graph retries can duplicate a message if acceptance occurred before a worker failure; this is an at-least-once delivery design.

## L1 assistant and company knowledge

The assistant searches developer-authored resolutions and RCA that a designated QA/Designer has verified at closure. It does not turn incomplete historical records into approved solutions. New verified closures expand its reference library; this is **knowledge indexing**, not automatic model-weight training.

Choose Knowledge search only, Azure OpenAI or OpenAI in **Email & AI setup**. For Azure, enter the HTTPS resource URL, deployment name and API key. For OpenAI, enter the model and API key. The app uses the official API endpoint. When a model is enabled, questions and the matching authorized articles are sent to that selected provider. If the provider fails or returns unsupported citations, the assistant falls back to the verified source resolutions.

Default articles are internal. Admin must explicitly approve client-specific or global visibility after reviewing sensitive information. Client accounts see only approved articles and permitted issue records. Reopening, resubmitting or re-verifying an issue resets external article approval; approve it again after review. The assistant does not execute changes, close issues or automatically invent unverified fixes. User helpfulness feedback is recorded for review.

## Source-data decisions

The main tracker supplies **99 issues: 25 Closed, 17 In Progress and 57 without status**. All 99 lack severity. Missing values remain unclassified; no response/fix timestamps or performance rankings are fabricated from workbook dates. Five release rows are retained as unvalidated template examples, outside the live release master. The three source sheets and 57 historical requirement-comparison rows remain available to authorized users. The exact original workbook is included under `data/source/`.

For meaningful performance/SLA reporting, create user accounts, link historical issues to named workflow owners, and classify missing fields. Reported-against developer attribution is separate from assigned ownership. Repeat counts use an explicit problem-family signature where supplied, otherwise normalized exact titles; they are not an AI root-cause diagnosis.

## Deploy to your server

Compose binds the application to `127.0.0.1:8000`, and does not publish PostgreSQL. Place a TLS reverse proxy/load balancer in front of it for remote access. Set `COOKIE_SECURE=true`, configure the real application URL in mail settings, and recreate services. `docs/Caddyfile.example` is a starting example; use a hostname/certificate configuration appropriate to your environment. Allow request bodies of at least 21 MB for 20 MB uploads plus multipart overhead.

For an existing managed PostgreSQL service, supply the application and worker with the same `DATABASE_URL`, `SETTINGS_ENCRYPTION_KEY`, bootstrap Admin variables, timezone and cookie configuration. Use the database provider's TLS settings and a dedicated database/schema. Keep private credentials in deployment secrets. Changing the bootstrap password variable after the first launch does not reset an existing user.

Schema migrations through version 6 run on startup under a database advisory lock. **Back up an existing database before upgrading.** Its recorded data remains; role mappings and new tables/columns are added. Existing imported issues are not silently converted into new measured workflow histories.

## Backup

```sh
docker compose exec -T db pg_dump -U tracker -d tracker -Fc > tracker.dump
```

This includes attachments, users, settings, work cycles, knowledge articles, notification jobs and audit history. Keep encrypted backups, `.env` encryption key and application source, and test restoration into a separate empty database. `docker compose down -v` removes the persistent database volume and is not a normal restart command.

## Validation

```sh
python -m pip install -r requirements.txt
python -m pytest -q
node tests/check_frontend.mjs
```

The Node check is optional for deployment; it tests frontend rendering functions. The Python integration suite requires `TEST_DATABASE_URL` pointing at an **empty, disposable PostgreSQL database**. It refuses an existing populated schema. See `docs/VALIDATION.md` for the exact completed checks and remaining UAT steps. Do not run integration tests against production.

## Boundaries

This is an application package for deployment review and UAT, not an already provisioned Bancapp production service. Full authenticated browser UAT, Docker image execution on your host, real Outlook/SMTP delivery, live model calls, load testing and backup restoration remain deployment checks. Verified API tests cover the application logic with a real PostgreSQL server and simulated email transport.

The app loads the current issue register into the browser. Add pagination and connection pooling for substantially larger volumes. Attachments are stored in PostgreSQL and downloaded as files. Audit records are not an independently tamper-proof service. SSO/MFA and sales/opportunity CRM are outside this bug-management scope.

## Workspace design refresh

The current interface includes grouped workspace navigation, a List/Board view bar, purple and blue accents, green/amber/pink status treatments, refined dashboard cards, colored assignee avatars and a coordinated issue drawer. The changes are presentation-only; PostgreSQL persistence, role permissions and the enforced testing routes remain in the existing backend. The refreshed dashboard/list/board templates passed rendering checks. An interactive demo-data preview was visually reviewed in a browser, including opening a board item and inspecting resolution/RCA. Full authenticated application-browser UAT remains a deployment check.


## Complete lifecycle forms (version 3)

The reporting form covers the complete main workbook field set and source milestones in eight sections. Calculated fields and later-stage fields are labelled and read-only. Conditional details capture regression baseline, release blocker reason, financial/regulatory impact, correction plan and requested business outcome. Named assignment separates the current fixer from reported-against attribution; additional followers can receive updates.

Use **Submit rectification & RCA** for the developer response, resolution type, root cause, code/change references, developer tests, regression coverage, verification/L1 steps and prevention. Use **Delivery milestones** for actual handover/UAT/deployment and communication dates; tester sign-offs remain role-controlled. Testing requires actual findings and evidence. Production fixes use a separate QA approval, deployment evidence and final closure sequence. Release blockers stop a release until they are closed or their fix has been QA-approved for deployment. Closure enforces required data correction, client confirmation and RCA sharing.

Every bug offers **Full record PDF / Excel**, including the full visible field set and correction cycles. The list PDF remains a concise register; Excel includes the full dataset. See `docs/FIELD_LIFECYCLE_MATRIX.md` for the exact field ownership and conditions. Source recommendations are historical context and are not used as verified RCA.

The downloadable frontend preview uses synthetic demonstration data and local interactions. It displays the reporting, rectification, testing, deployment and closure forms; it does not save to PostgreSQL or send notifications. Run the packaged application for persistent multi-user operation.


New workspace navigation includes **Dropdown administration**, **Roles & permissions**, **Supporting documents**, **Reports centre** and dashboard shortcuts to **Employee performance**. Supporting files and verified knowledge are separate sections. Screenshot/video and document uploads each support multiple files. Migration 4 categorises existing attachments without removing them. See the user guide and validation record for preview capabilities and RBAC verification.


The current release adds distinct Bug/Requirement/Feature/Change IDs and report breakdowns, SLA breach instance counts, Top 3 rankings, a complete management PDF, full current-status records, guided dropdown editing with CSV/XLSX templates, workspace breadcrumbs, admin login/activity reporting and the notification centre. Existing workbook IDs are retained. See docs/USER_GUIDE.md for exact rules and docs/VALIDATION.md for the 96-test validation record.

## Deployment handover

Start with `START_HERE.md`. The full branded features/SOP manual is in `docs/Bancapp_Deployment_Features_and_SOP_Manual.pdf`. Deployment procedures and the optional Docker HTTPS proxy are described in `docs/DEPLOYMENT.md`. Operational helpers: `scripts/preflight.py`, `scripts/backup.py`, and `scripts/restore.py`. The recovery helper refuses a nonempty database, leaves application services stopped, and disables restored outbound integrations. No production secrets are included. The standalone preview and bulk templates are under `preview/` and `templates/`.
