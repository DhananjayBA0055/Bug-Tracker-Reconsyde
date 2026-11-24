# Version 3 validation record

Date: 17 November 2026

## Completed checks

| Check | Result |
| --- | --- |
| Python application tests | 72 passed: 40 calculation/access/validation checks and 32 real HTTP/PostgreSQL integration checks |
| Database used for integration | PostgreSQL 16.2, running as a local TCP server against disposable databases |
| Python compilation / JavaScript syntax | Passed |
| Frontend rendering-function checks | Passed: business-role navigation, user dropdowns, all 62 main workbook fields in intake, supplemental lifecycle evidence, performance empty-state, L1 assistant |
| Branded report generation | Excel and PDF generated and reopened/checked for all nine report families |
| PDF visual check | Branded sample resolution/RCA report rendered and inspected; logo, header, table and footer readable |
| Browser preview | Branded sign-in page and synthetic-data preview loaded; expanded reporting, rectification and closure forms inspected |
| Compose configuration | Application, PostgreSQL and worker services parsed; shared secret environment checked |
| Original imported dataset | 99 records retained, original IDs preserved, missing classifications left missing |

## Integration coverage

- Schema migration and initialization idempotence; protected Super Admin and default role rights.
- Product Developer -> QA acceptance, and Process Developer -> Process Designer return/fix/close loops.
- Mandatory developer resolution and RCA; only the designated role/tester can close; direct workflow bypass rejected.
- Acknowledgement timestamps, correction cycles, return count, closure and reopen behavior.
- Concurrent update rejection using revision numbers.
- Evidence uploads, type mismatch rejection, forbidden extensions and 20 MB size limit.
- User bulk preview/apply, invalid-row transaction rejection, master add/rename/delete and bulk import.
- Role-policy update and protection of the final active Super Admin.
- Verified knowledge publication, reopen withdrawal, chatbot source matching and client knowledge/issue boundaries.
- Employee response/fix/return metrics, designer/QA activity and employee issue drilldown.
- Branded XLSX/PDF output for dashboard, issues, clients, performance, knowledge, releases, requirement coverage, users and audit.
- Filtered issue exports reflect status/client filters.
- Connection-secret encryption and redacted reads; participant/manager CC generation; response and resolution SLA alerts; daily digests; scheduling deduplication; simulated worker delivery and retry; no provider-detail leakage in errors.
- CSRF rejection for mutation requests without the session request token.

No actual business emails were sent. Provider delivery was replaced with a test transport. The tests validate scheduling, recipients, queue persistence, accepted-send state and retries; they do not demonstrate deliverability to a real Outlook mailbox.

## Remaining deployment checks

- Build/start the Docker containers on the target server (Compose targets PostgreSQL 17; local integration used 16.2).
- Full authenticated browser UAT across staff roles and mobile layouts. Browser inspection covered sign-in and the synthetic-data reporting/rectification/closure preview; authenticated role workflow verification used real HTTP/API integration tests, not a complete browser UAT.
- Real Outlook/Microsoft Graph or SMTP connection and recipient delivery using Bancapp's approved account.
- Live Azure OpenAI/OpenAI calls using the selected deployment/model. The key-free knowledge-search chatbot was tested; generated answers were not exercised against a paid provider.
- HTTPS, secure cookies, real hostname, reverse-proxy body limits and worker uptime.
- Backup restoration, load/concurrency testing at intended production volume, and normal deployment review.

## First UAT run

1. Create named developers, designers, QA and Manager accounts.
2. Run one complete process route and one product route, returning a failed fix at least once.
3. Check mandatory RCA, tray ownership, closure permissions and the resulting resolution article.
4. Reopen a closed issue and confirm the article disappears until reverified.
5. Check employee drilldowns, response/fix/testing samples, team averages and report filters.
6. Upload screenshots, a short video and supporting office/PDF files.
7. Validate then apply user and dropdown bulk files; verify that one invalid row prevents all changes.
8. Configure mail, send a test, inspect CCs, and exercise an SLA/digest in a test environment.
9. Ask L1 about a verified issue, a nonexistent issue, and a client-isolated article.
10. Download Excel/PDF reports, restart services, and verify persistence and restoration.

The package is suitable for deployment review and UAT. It has not been deployed as Bancapp's production service.

## Additional lifecycle verification

- Rejected incomplete reporting payloads, fabricated QA/closure/RCA values at intake, financial-impact severity conflicts and invalid quantified impact.
- Checked regression baseline/coverage/prevention, code references, developer tests and designated QA acceptance evidence.
- Exercised production QA pass → release readiness → actual release → deployment evidence → final client-confirmed closure with RCA-sharing proof. Verified that an open, untested blocker prevents release and that test-approved fixes can ship without a circular closure dependency.
- Confirmed full per-bug branded Excel/PDF output includes developer RCA and deployment evidence.
- Confirmed tester-only milestone sign-off, rejection of future actual dates, reset of stale deployment and verification evidence on reopen.
- Tested client-scoped intake, rejection of client assignment to internal participants, severity-policy snapshots and the India/UTC midnight business-date boundary.
- Verified 98 intake field references (main workbook, supplemental source fields, developer response reference and added evidence), and unique backend field metadata.

No production accounts, external AI credentials or actual customer email delivery were used. Standalone preview forms share the production renderers but use local demo interactions; preview validation is not evidence of PostgreSQL persistence. Run the full package for authenticated persistence.

## Workspace visibility and RBAC verification update — 18 November 2026

63 backend checks pass (40 unit/validation checks, 23 PostgreSQL/HTTP integration checks). Additional tests reject direct manager/developer/client attempts to edit masters, bulk masters, role policies and mail configuration; reject developer/client performance access and exports; and allow manager performance exports. Multiple supporting files and media are categorised separately. Client isolation is checked on document listings and attachment download. Employee-specific Excel export is reopened and checked to contain exactly the selected employee.

Frontend rendering/syntax checks cover separate multiple-upload controls, manager versus Super Admin master visibility, report-catalogue restrictions, and dashboard employee-report links. Standalone parsing checks cover the expanded navigation, role selector, separate uploads, visibility CSS and embedded downloadable demo reports. A cloud-browser reload was blocked by its URL policy, so the latest expanded preview has not received a complete live-browser interaction test. Existing authenticated API tests are not a substitute for final browser UAT.

Offline controller interaction tests also passed for dashboard shortcuts, local dropdown changes, Manager/developer permission visibility, employee performance and the Reports centre. Embedded PDF/Excel bytes were validated for all nine core sample reports plus four individual employee variants.

## Eight-point reporting/admin update verification

72 tests pass: 40 unit/validation checks and 32 real PostgreSQL/HTTP integration checks. New coverage verifies independent request prefixes and filters, client-submitted features with acceptance criteria, request category immutability, response/resolution breach attribution and deduplication, Top 3 eligible rankings, all management-PDF sections, admin-only activity reports, login history across email changes, complete detail/evidence/latest-action payloads, full-list master modification and both template formats. The dashboard PDF's text is checked for request categories, workload, SLA, employee results, team averages, rankings and the complete register.

Frontend checks cover full status fields and attachments, latest remarks placement, request-specific form fields, master wizard branches and breadcrumbs. Offline preview-controller interactions cover the dashboard, local master changes, role visibility, employee screens, detailed status and evidence. All embedded PDF/Excel variants are opened/checked; the management PDF is rendered for layout review. These checks do not constitute full live browser UAT.
# Notification centre verification — 18 November 2026

89 automated backend checks pass, including real PostgreSQL/HTTP tests. New checks cover policy precedence, mandatory locks, timezone boundaries, daily/weekly grouping, individual immediate exceptions, notification administration permissions, template-only delegation, safe template expansion, invalid placeholders/settings, revision conflicts, queued-message cancellation, and preservation of revoked role rights after restart. Delivery providers are mocked; these checks send no real email.

Frontend rendering checks and offline preview-controller checks pass for schedules, group/individual inheritance, the subject/body editor, sample placeholder expansion and page visibility. The updated preview has not received complete live-browser UAT. Actual Outlook/Azure delivery and production deployment remain unverified.

# Docker handover verification - release 4.1

96 automated checks pass: the previous 89 backend checks plus seven offline deployment-helper tests for missing/invalid configuration, backup integrity/non-overwrite, failed-backup cleanup, refusal to restore to a populated database, and integration quarantine after empty-database recovery. Docker calls in these utility tests are mocked. Base and HTTPS Compose YAML parse successfully; source/scripts compile and frontend rendering checks remain passing. The environment has no Docker executable/daemon, so no container build, Compose startup, real provider delivery or Docker-volume recovery was executed here. Run the deployment acceptance checklist on the target server.

