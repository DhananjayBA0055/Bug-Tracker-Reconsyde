# Application purpose and release scope

Bancapp Delivery Desk manages bugs, requirements, feature requests and change requests across the Product, Process and QA teams. It records the full issue lifecycle: intake, assignment, response, rectification, developer RCA, testing, release/deployment, closure, reopening and reusable L1 knowledge. Managers receive drilldowns and employee reporting; administrators manage users, rights, lists, integrations and notification rules through the UI.

This manual describes release 4.1, prepared on 18 November 2026. It covers delivered behavior and operational procedures. The supplied application is a deployable source package, not an already provisioned production service. The Docker build downloads base images and Python dependencies; no prebuilt/offline container images are supplied. Business-owner and infrastructure acceptance are required before live use.

The exact source tracker is retained in data/source. Its 99 historical issues include 25 Closed, 17 In Progress and 57 without status; all lack severity. Missing data remains visible. Five source release examples and 57 historical requirement-comparison rows remain references rather than new live releases or tasks. Historical dates are not invented response/fix timestamps. Imported closed rows without developer-authored, tester-verified resolution/RCA do not automatically become verified knowledge.

## Package contents

| Component | Included material |
| --- | --- |
| Application | FastAPI API, modern browser UI, RBAC, workflow and reporting modules |
| Database | PostgreSQL 17 Compose service, schema and migrations through version 6 |
| Notifications | Durable queue, scheduling worker, Graph/SMTP adapters and notification policy UI |
| Deployment | Dockerfile, base Compose, optional HTTPS proxy, configuration and operations helpers |
| Data | Original workbook, normalized source records, mapping and lifecycle field matrix |
| Handover | This manual, deployment instructions, validation notes and automated tests |
| Preview | Standalone HTML with synthetic interactions and fixed sample report downloads |
| Templates | Dropdown CSV/XLSX formats; user templates are downloaded from the authenticated UI |

The preview is a demonstration only: it does not persist to PostgreSQL, authenticate real accounts, send email or establish an AI connection. Run the Docker application for multi-user operations.

# Feature catalogue

| Feature area | Delivered behavior |
| --- | --- |
| Workspace | Overview, issue register, list/board views, search/filters, client and release views; Back and breadcrumbs |
| Intake | Separate Bug, New Requirement, Feature Request and Change Request forms; dropdowns, conditional evidence, named owners and followers |
| Numbering | Independent PostgreSQL sequences for BUG-, REQ-, FTR- and CHG-; original imported identifiers preserved |
| Detailed status | Full visible fields, latest action remarks first, attachments, discussion, cycles and action history |
| Rectification | Mandatory resolution/RCA, classification, developer tests, code/change references, regression coverage, prevention and L1 verification steps |
| Testing | Designated tester acceptance/return, evidence gates, regression results and repeat correction cycles |
| Release/closure | Production QA, release readiness, actual deployment evidence, data correction, client confirmation and RCA-sharing gates |
| Attachments | Separate media and supporting-document upload options, multiple files, up to 20 MiB each |
| Management | Request-type breakdowns, workload, SLA attention, employee drilldowns, Top 3 rankings and team averages |
| Reports | Branded Excel/PDF dashboards/registers, employee metrics, admin activity and full individual issue records |
| Knowledge/L1 | Verified resolution/RCA library, search, feedback, client publication review and cited assistant |
| User administration | Named accounts, activation, role/team, managers, client scope, role rights and individual grants/denials; bulk preview/apply |
| List administration | List-to-form mapping, Edit/Modify, Add, Rename, Delete; manual and CSV/XLSX validation/apply |
| Notifications | Event enablement, immediate/daily/weekly/off, group defaults, individual exceptions, mandatory locks, editable templates and sample preview |
| Integrations | Outlook/Microsoft Graph, TLS SMTP, optional Azure OpenAI/OpenAI; secrets encrypted in database |
| Traceability | Login/action reporting, workflow cycles, notification states and administrative audit history |

# Roles, rights and responsibilities

## Role model

| Role | Default business responsibility |
| --- | --- |
| Product Developer | Receive/reassign product work, acknowledge, record fix and RCA; submit to designated QA |
| Process Developer | Receive/reassign process work, acknowledge, record fix and RCA; submit to designated Process Designer |
| Process Designer | Raise/assign work, test designated process fixes, return or close |
| Quality Analyst | Raise/assign work, test designated product fixes, return or close |
| Manager | View internal records, management dashboard, employee performance and reports |
| Admin | Manage users, permissions, dropdowns, releases, integrations, notifications and knowledge publication |
| Super Admin | All administration plus protected Super Admin account management |
| Client | Scoped intake, permitted client records/discussion/attachments, approved knowledge and assistant |

These are defaults. Admin can change role policies and apply individual grant/deny overrides. Server-side checks enforce permissions and parent-issue/client access; a hidden menu alone is not the security control. Workflow ownership restrictions remain: a general right does not let a developer bypass designated tester acceptance. Maintain at least one active Super Admin. Only Super Admin administers protected Super Admin accounts.

Product Team, Process Team and QA Team are the three business teams. Assign each named user a role, appropriate team, reporting managers and any client scope. Notification custom groups affect preferences only and do not grant application access.

## SOP: onboard, change or remove access

Owner: Admin; protected accounts: Super Admin.

1. Verify the person's business role, team, reporting manager and client scope with their manager.
2. Open Team & access; add the named account, initial credentials, role/team and manager emails. Do not create shared developer or tester accounts.
3. Review the role-rights matrix. Add an individual exception only with a documented reason; use deny overrides where a role right must be removed.
4. For bulk changes, download the user CSV/XLSX template, keep headers in row 1, and match existing accounts by email. Use semicolons for manager/client lists and the documented JSON format for rights overrides. New passwords must meet the UI policy and are not echoed in previews/exports.
5. Upload and inspect validation results. Correct all invalid rows; one invalid row prevents the whole batch from applying. Apply only after verifying role and scope changes.
6. Have the user sign in and confirm the permitted tray/pages. Distribute credentials through Bancapp's approved channel; no automated invite/password-reset email flow is shipped.
7. On exit/role change, reassign open work to an active named owner, then deactivate/restrict the account. Retain historical identity for audit and performance attribution.

## SOP: review access and actions

Owner: Admin; recommended operating cadence: monthly and on personnel changes.

Open Roles & permissions and review individual overrides alongside role defaults. Open User login & activity to inspect last recorded login, last recorded business action, action count and detailed history. Export Excel/PDF for review. User IDs retain attribution across email changes. Page-view clicks are not represented as audited business actions, and imported pre-application history is not inferred. Review unusual assignments, bulk changes, publication approvals and connection/policy edits. Audit history is application-managed; it is not an independently tamper-proof external audit service.

# SOP: raise and triage a bug or request

Owner: Process Designer or QA for internal reporting; Client for scoped external intake; Admin oversees source remediation.

## Select the correct request type

| Type | New ID prefix | Mandatory business distinction |
| --- | --- | --- |
| Bug | BUG- | Existing behavior fails; record reproduction, expected and actual results |
| New Requirement | REQ- | New business need; justification, expected outcome and acceptance criteria |
| Feature Request | FTR- | Capability enhancement; justification, expected outcome and acceptance criteria |
| Change Request | CHG- | Requested change; justification, expected outcome and acceptance criteria |

Request type is immutable after ID allocation. If misclassified, create a linked corrected request rather than changing the meaning of an allocated number. Bug SLA/rankings and non-bug delivery targets are reported separately. An imported historical ID remains unchanged for traceability.

## Reporting procedure

1. Search the register and verified knowledge first. Link a duplicate/repeated problem rather than losing its relationship to earlier work.
2. Choose New issue and request type. Select client/tenant, scope, source, product module, environment, discovery stage, category, severity and priority as appropriate. Internal non-bug requests need module and priority plus the required business fields.
3. For bugs, enter a precise title, reproducible steps, expected result and actual result. Add release/build, browser/device, client reference, sprint and process SPOC where relevant. Do not fill later-stage closure evidence with guesses.
4. Set impact flags. Regression requires a last-working version. Release blocker requires a reason. Financial impact requires S1/S2 severity, assessment status and notes. A quantified impact needs records affected and INR amount; a zero value needs a meaningful justification. Regulatory impact needs notes. Required data correction needs a scope/plan.
5. Choose the assigned developer and designated tester. Product Developer routes to QA; Process Developer routes to Process Designer. Set reported-against developer only when the attribution is known; it is separate from the person fixing the issue. Add permitted followers for updates.
6. Upload media and supporting documents through their separate controls. Check filenames and remove unnecessary sensitive data before upload. Submit and record the unique ID.
7. If an attachment fails after creation, retain the saved issue and retry that file in Discussion. Do not submit a second issue solely to replace a failed upload.
8. Triage incomplete source/imported rows by linking named workflow owners, classifying missing fields and recording evidence gaps. Do not present source-era recommendations as verified developer RCA.

For client intake, the form is smaller and restricted to the client's allowed scope. External reports enter internal triage; clients do not choose arbitrary internal owners or see internal notes.

## SOP: inspect current status and collaborate

Click any issue-register row. Read the latest action remarks at the top, then inspect full current status, reporting fields, attachment links, shared discussion, rectification cycles, delivery evidence and history. Use Edit reporting information for editable intake details; use workflow actions for ownership and status. Save each tab before moving away. Add shared comments for visible collaboration and Internal note only for staff-only text. Attachments inherit the issue's access scope; they are not private simply because uploaded next to an internal note.

Use Back/breadcrumbs to return to the originating workspace. Full record PDF/Excel contains the visible detailed issue record; a list-register PDF is a concise register, not a replacement for the full-record export.

# SOP: acknowledge, reassign and submit rectification

Owner: currently assigned Product Developer or Process Developer.

## Enforced routes

| Route | Rectification owner | Test/acceptance owner | Failure loop |
| --- | --- | --- | --- |
| Product | Product Developer | Named Quality Analyst | QA returns to developer, who rectifies and resubmits |
| Process | Process Developer | Named Process Designer | Designer returns to developer, who rectifies and resubmits |

1. Open My tray/assigned work; inspect the full report, evidence, severity, deadline and last action.
2. Choose Acknowledge to record first response. A substantive developer comment or submitting a fix also records first response when missing. Acknowledge does not mean the defect is rectified.
3. If ownership is incorrect, use Assign/reassign while the work is in your tray. Select a valid named developer/tester pair and explain the handoff. Reassignment preserves history and starts the relevant response measurement for the new assignment.
4. Investigate and choose Submit rectification & RCA. Enter both developer resolution and root cause analysis; these are mandatory and independently meaningful.
5. Complete resolution/root-cause classification, developer test evidence, fix verification/L1 steps and applicable release information. Code changes need PR/commit references; configuration changes need a change ticket. Duplicate classification links a different, accessible original issue.
6. For a regression, record regression coverage and prevention. S1/S2 production fixes need preventive action. Production code fixes need a planned fix release and post-deploy action. Record data-correction plan where required.
7. Submit for testing. The tray moves to the designated QA/Designer; retain supporting evidence and communicate any known limitations. Do not directly close your own fix through a status edit.

Each correction cycle retains response/fix timestamps, resolution and RCA. Returned fixes and reopen counts remain visible; they are not erased by resubmission. The combined source Root Cause & Fix Summary is reference context and does not replace current developer-authored evidence.

# SOP: testing, deployment and closure

Owner: designated QA for product work; designated Process Designer for process work. Release administration/deployment evidence is handled by the permitted developer/release administrator.

## Test or return

1. Open your testing tray and verify the reported symptom, expected result and developer change against the original evidence.
2. Run the stated developer checks plus independent acceptance and regression checks. Enter actual findings, test evidence/reference and regression result where applicable.
3. If the fix fails, choose Return to developer and record the failure, reproduction and evidence. The issue returns to the developer for another correction cycle; repeat until acceptance criteria are met.
4. If testing passes, use the applicable acceptance action. Non-production work can proceed to final closure once all gates are met. Applicable production work first becomes Ready for Deployment; QA approval alone is not production closure.

## Release and deployment

1. Create/review the target release and included work in Releases. Source template-release examples are not live release approvals.
2. Review release blockers. An open, untested blocker prevents release; a QA-approved fix can be deployed without requiring circular pre-deployment closure.
3. For applicable production code fixes, record a Released release with actual release date, change/deployment ticket, actual production deployment date and deployment evidence. Record actual fix release and post-deploy action.
4. Complete required data correction and record its completion date. Fill applicable handover, Bancapp UAT, ProcessDev, client UAT/production and communication milestones. Actual dates cannot be in the future; tester sign-offs remain restricted to the designated tester.
5. The issue becomes Ready for Closure when applicable evidence is present. Do not use generic field editing to bypass the workflow.

## Final closure and reopening

1. The designated tester confirms the deployed behavior and records closure remarks and evidence.
2. Client-reported issues require confirmation evidence. Client-reported production S1/S2 issues also require RCA-sharing evidence. Complete any required data correction before closure.
3. Close only when the recorded results support acceptance. Closure stamps the actor/date and publishes the verified resolution/RCA to the internal knowledge library.
4. If the issue recurs or acceptance is invalidated, the designated tester reopens it with evidence. Current-cycle verification/deployment evidence is reset as applicable, the reopen count increases and the knowledge article is withdrawn until reverified. Earlier cycles remain auditable.
5. Reverification/resubmission resets external knowledge approval. Admin must review and approve client publication again.

# SOP: attachments and supporting documents

| Category | Formats | Limit |
| --- | --- | --- |
| Screenshot/image | PNG, JPG/JPEG, WebP, GIF | 20 MiB per file |
| Short video | MP4, WebM, MOV | 20 MiB per file |
| Supporting documents | DOC/DOCX, XLS/XLSX, CSV, PDF | 20 MiB per file |

Multiple attachments are allowed. Media evidence and supporting documents are separate controls; the resolution/RCA library is a separate workspace, not a document-upload category. The application checks file type, size, empty content and supported signatures. These checks are not an antivirus or DLP service; add infrastructure scanning if Bancapp requires it.

Upload during intake or Discussion. Confirm that each file appears on the saved issue and can be opened by an authorised recipient. Use Supporting documents to find documents within your allowed issues. Downloads repeat parent-issue/client access checks. Attachments are stored in PostgreSQL and included in the database backup; database sizing must include media growth. Avoid unnecessary personal/financial records and redact sensitive samples according to Bancapp's handling policy.

# SOP: dashboards, employee performance and reports

Owner: Manager; Admin/Super Admin for administrative reports.

## Management review

1. Select the reporting period, request type/team or other available page filters. Review Bug separately from New Requirement, Feature Request and Change Request.
2. Inspect open workload, status, severity/client/current-tray distribution, overdue/SLA attention and classification readiness. Drill into cards/rows to inspect the underlying issues.
3. Open Employee performance; drill into an employee to inspect assigned work, reported-against attribution, response/fix/closure measurements, returned fixes, repeats, raised issues, testing activity and current tray.
4. Review response-SLA breaches, resolution-SLA breaches and total instances. These are business breach instances, not email attempts. They are attributed to the recorded owner; unverifiable historical ownership remains unassigned.
5. Review team averages and the Top 3 best/worst eligible fix-speed lists. Rankings require at least three completed measured bug fix cycles per person; fewer eligible people means fewer displayed names. Requirements are separated from bug timing/rankings.
6. Assess severity, complexity, scope and work mix before personnel decisions. A faster average alone is not a quality assessment. Repeats use an explicit problem-family signature or normalized exact title, not AI root-cause inference.
7. Download reports using the desired page/report controls and confirm date/filter context. Individual employee exports contain that employee's selected metrics. Preview exports are fixed synthetic examples and do not recompute from live filters.

Team response/fix averages use recorded cycles, weighted by their recorded samples. Missing response/fix times are not synthesized from historical tracker dates. Resolution SLA deadlines are calendar dates; no business-day/holiday calendar is shipped. Severity policy snapshots are set on creation or explicit severity change; later global edits do not silently shorten existing agreements.

## Export catalogue

| Report | Content and format |
| --- | --- |
| Management dashboard | Branded Excel/PDF; request totals, workload breakdowns, SLA items, readiness, employee/team results, Top 3 lists and full current register |
| Issue register | Full dataset in Excel; readable summary columns in PDF |
| Full issue record | Detailed visible fields, developer RCA/resolution, cycles and deployment evidence in Excel/PDF |
| Employee performance | Employee measurements, SLA instances, team averages and eligible rankings; individual drilldown exports |
| Client report | Client-scoped issue/delivery view; restricted exports omit internal employee sections |
| Release report | Release plans and actual delivery status |
| Requirement coverage | Historical comparison/reference coverage view |
| User register | Admin user/role/team register; no passwords |
| Audit report | Recorded post-import business/admin actions |
| User login & activity | Admin last-login/last-action summaries and detailed action history |
| Resolution & RCA library | Verified solutions, RCA, prevention and verification content for reuse and L1 training |

If a report is empty, check permissions, filters, data classification and measured-cycle availability before assuming a calculation defect. Management PDF includes all of its defined sections; use individual full-record exports for every field and attachment reference of a specific issue. Binary attachment contents are downloaded separately rather than embedded into report PDFs.

# SOP: dropdown administration

Owner: Admin or delegated master administrator.

1. Open Dropdown administration. Select the list and read the displayed mapping to the affected input fields; for example, a module list changes the Product Module selection, not severity policy or workflow ownership.
2. Choose Edit/Modify, Add, Rename or Delete. The next UI separates manual work from bulk upload.
3. For manual Modify, review/edit/reorder the complete list. For Add enter new values; for Rename select the existing value and replacement; for Delete review the exact values. Historical record values remain preserved.
4. For bulk work, download the CSV/XLSX format. Keep headers in row 1: group, operation, value, new_value. A modify row updates the specified existing value; it is not a full-list replacement. Supported operations are validated by the selected action/template.
5. Upload, validate and review the resulting changes. Correct every error before applying; invalid batches are transactional and apply nothing.
6. Reopen the affected intake/workflow selection and verify the intended choices. Record the business reason in the administrative review process.

Structural workflow states, severity-policy requirements, Yes/No values and the three business teams are protected controls rather than arbitrary editable labels. Use the corresponding policy/role workflows to change supported business behavior; renaming a dropdown does not rewrite application workflow logic.

# SOP: notification policy and editable emails

Owner: Admin/Super Admin or explicitly delegated notification administrator.

Three separate rights control notification rules/groups, individual overrides and template editing. Use role policies and individual grant/deny overrides to delegate these independently. Users cannot grant themselves application rights by joining a notification group.

## Events and frequencies

| Event | Available delivery controls |
| --- | --- |
| Created, assigned, status/details updated | Immediate, daily, weekly or off |
| Shared comment, internal note, attachment | Immediate, daily, weekly or off; internal notes never reach clients |
| Fix submitted, testing, closed, reopened | Immediate, daily, weekly or off |
| Response/resolution SLA breach | Immediate, daily, weekly or off; disabling email does not stop breach recording |
| Open-tray report | Daily, weekly or off |

1. Open Admin > Notification centre > Events & schedule. Enable the events required by Bancapp and choose each cadence. Immediate means queued for the next worker cycle, not guaranteed synchronous inbox delivery.
2. Set timezone, daily time, weekly day and weekly time. Blank schedule fields inherit the mail connection schedule. Review local timezone boundaries before saving.
3. Open Groups and choose role, team or custom named members. Rules apply in order: workspace defaults, role groups, team groups, custom groups, then individual overrides. Within a kind, higher priority applies later; group ID resolves ties deterministically.
4. Mark a rule mandatory if later groups/individuals must not override it. A workspace mandatory rule locks everyone. For example, mandate immediate SLA alerts while batching routine comments daily.
5. Open Individuals, select the account, inspect the inherited source/lock and choose an exception or restore inheritance. Inactive accounts are excluded. A preference group does not subscribe all members to all issues: recipients must already be attached to the issue and authorised to see it.
6. Open Effective policy & preview to inspect source, cadence, next schedule and managers in CC. Save explicitly. A revision conflict means another admin saved first; reload and review before saving again.

## Edit email subject and body

1. Open Templates and select an event, daily digest or weekly digest. Subjects and bodies are editable plain text; this release has no rich-HTML designer.
2. Insert supported placeholders: recipient_name, issue_id, title, request_type, client, status, assignee, event_name, occurred_at, app_url, items, item_count and period. The UI inserts them with double braces, for example {{issue_id}}.
3. Use event templates for immediate emails. Daily/weekly batching uses its separate digest template; items contains compact event summaries. Tray reports have their own template. Unknown placeholders, multiline subjects and executable expressions are rejected.
4. Preview with sample data. Preview sends no email and does not authenticate a provider. Verify the subject/body, placeholder expansion, cadence and manager CC, then save.
5. Test actual transport separately with controlled recipients using Email & AI setup and Notification log.

Managers remain in CC through this preference UI. Attached participants, mapped reporting managers and configured/fallback managers determine recipients; admins must maintain correct manager mappings. Email contains a brief issue summary and link, not attachment bytes or raw internal-note/RCA bodies.

Events occurring while mail is disabled are not backfilled. Pending deliveries are reevaluated against current policy and access; saving changes rebuilds queued/retry emails. In-flight/provider-accepted/sent messages cannot be recalled. Large backlogs are processed in batches and may create multiple digests. Retries provide at-least-once delivery: a provider acceptance followed by a worker failure may cause a duplicate. Sent means provider accepted, not proof of inbox delivery.

## Daily notification operations

Inspect Notification log for queued, sent, retry, dead or cancelled work and investigate persistent failures. Check worker health/logs, connection enabled flag, recipient activation/access, effective policy, timezone and manager CC. Do not repeatedly queue live test emails to troubleshoot an unrelated rule preview. Confirm scheduled open-tray emails go to the person whose tray holds the work. Pending restored jobs require review before mail is reenabled after recovery.

# SOP: email and AI connection setup

Owner: Admin with integration rights; Microsoft tenant administrator supplies and approves Microsoft configuration.

## Outlook / Microsoft Graph

1. Obtain an approved sender mailbox, tenant ID, application/client ID and client secret from your tenant administrator. Application Mail.Send permission, administrator consent and appropriate mailbox scoping must be configured by the tenant administrator.
2. Open Email & AI setup and choose Outlook / Microsoft Graph. Enter the connection fields, manager CC addresses or active reporting-manager accounts, real application URL and reporting timezone/day-end time.
3. Save and enable in a controlled test environment. Queue a test email and inspect Notification log plus the controlled recipient inbox/CC. Saving the connection does not itself send a test email.
4. Test immediate, daily and weekly policy behavior using attached test users before production enablement. Renew expiring secrets according to tenant policy.

For SMTP, choose STARTTLS or SMTP over SSL, then enter approved host/port, sender, username and secret. Use only an approved relay/Exchange configuration that permits the selected authentication. Mailbox/tenant provisioning, consent, relay policy and domain reputation are external setup tasks; the package does not configure Azure or Microsoft 365 automatically.

## AI connection

The assistant works immediately in Knowledge search only mode without an API key. Optional Azure OpenAI needs resource HTTPS URL, deployment/model configuration and API key; optional OpenAI needs model and key. Save only approved endpoints and validate provider behavior with permitted sample content. Questions and selected authorised article text are sent to the configured provider when enabled. Credentials are encrypted using SETTINGS_ENCRYPTION_KEY. Preserve that key; changing it without reencrypting existing secrets prevents decryption.

# SOP: resolution library and L1 assistant

Owner: developer authors; designated tester verifies; Admin controls external publication; all signed-in users can use the assistant within their access scope.

1. Developers supply usable resolution, RCA, preventive action and verification/L1 steps during rectification. QA/Designer verifies before closure.
2. Open Resolution & RCA library after closure. Search by symptom/category, inspect the source issue and check that the instructions are reusable and do not expose sensitive client information.
3. Use helpful/needs-improvement feedback for content review. Download branded Excel/PDF for L1 training/self-help. Uploaded supporting documents remain separate from these verified articles.
4. Admin may approve client-specific or global visibility only after reviewing sensitive data. Default knowledge is internal. A future client account sees only approved articles and its permitted records.
5. Ask the L1 assistant a concrete symptom question. Review cited issue IDs and verify the environment before applying the guidance. With no verified match it should suggest raising an issue rather than inventing a fix.
6. Reopened work is removed from active verified knowledge until reverified. Reapproval is required for external visibility after the relevant lifecycle change.

New verified closures extend the searchable reference corpus. This is knowledge indexing/retrieval, not unsupervised learning or model-weight retraining. Optional generated answers use authorised matches; failures or unsupported citations fall back to verified source resolutions. The assistant does not execute fixes, alter records or close issues. Client role/scoping is a foundation for future client rollout, not a completed commercial self-service onboarding portal or public anonymous chatbot.

# Operating calendar and control ownership

These are recommended SOP cadences for Bancapp to adopt; only the configured notification schedules run automatically. The package does not install human-review or backup schedules.

| Cadence | Owner | Review and retained evidence |
| --- | --- | --- |
| Each workday start | Developer/tester | Current tray, priorities, deadlines, returned fixes and last remarks |
| During each handoff | Developer/tester | Named owner, resolution/RCA or test evidence, status and next action |
| Each day end | Team manager | Open tray, ageing/SLA attention, blocked work and notification failures |
| Weekly | Manager | Bug versus requirement trends, employee/team metrics, returns, repeats and action owners |
| Weekly | Knowledge owner/Admin | Verified article quality, feedback and external publication scope |
| Monthly / personnel change | Admin | Role grants/denials, group rules, account activation, manager mapping and login/activity report |
| Nightly and before upgrade | Infrastructure owner | Successful protected database backup and off-host copy, subject to agreed RPO/RTO |
| Before go-live / scheduled rehearsal | Infrastructure + business owner | Restore results, role/client isolation, full workflows, exports and actual email acceptance |

## Exception handling and escalation

Record the request ID, time, current tray, failed action, safe error description and attempted resolution. Escalate business ownership to the relevant team manager and deployment/provider faults to the infrastructure/integration owner. Preserve the original issue and history; do not create duplicates for failed uploads or overwrite source-era evidence to improve metrics. Avoid secrets or unnecessary customer data in exported diagnostics.

## Boundaries and acceptance evidence

The backend tests exercise real PostgreSQL and authenticated HTTP behavior, with provider calls mocked. Frontend rendering and offline preview interactions are checked. The Docker daemon is unavailable in the build workspace, so images/containers have not been executed there. Full authenticated browser UAT, actual Outlook/SMTP delivery, live AI calls, production load/sizing and Docker-volume recovery must be completed on the intended deployment environment.

The current UI loads the issue register into browser memory; substantially larger volumes need pagination and database connection pooling. SSO/MFA, antivirus/DLP scanning, external tamper-proof audit storage, business-day holiday SLA calendars, automated backup retention and sales/opportunity CRM are not shipped. These limits should inform rollout scope without preventing controlled UAT of the delivered tracker.

# Acceptance and handover checklist

| Check | Acceptance evidence to record |
| --- | --- |
| Infrastructure | Host owner, release checksum, service health, TLS URL, storage and outbound network |
| Recovery | Backup location/key custody, recovery project, restored counts/files, measured recovery time |
| Access | Named accounts, Manager read rights, Admin rights, individual denies and client isolation |
| Product route | Raised bug, acknowledgement, fix/RCA, QA return/resubmit and final acceptance |
| Process route | Raised bug, process fix/RCA, Designer return/resubmit and closure |
| Production gates | Release blocker test, QA pass, released deployment evidence, client/RCA/data-correction gates |
| Intake | All four request types and ID formats; conditional impact/regression fields; multiple attachments |
| Reports | Management PDF sections, employee SLA instances/Top 3, team averages, full-record and admin activity exports |
| Lists/users | Manual edit and valid bulk apply; invalid batch rejected; list/form mapping confirmed |
| Notifications | Template preview; mandatory group rule; individual exception; real immediate/daily/weekly email and manager CC |
| Knowledge/L1 | Closure publication, reopen withdrawal, cited answers, no-match behavior and client publication review |
| Approval | Business owner, infrastructure owner, approval date, open exceptions and accountable owners |

Keep a signed acceptance record alongside Bancapp's deployment/change register. This manual provides procedures; it is not evidence that the target environment has passed them.
