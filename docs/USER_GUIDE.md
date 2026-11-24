# Bancapp Delivery Desk - user guide

## Initial setup by Super Admin

Create Product Developers, Process Developers, Process Designers, QA and Manager accounts in Team & access. Choose the three business teams and reporting-manager emails. Add users individually or validate/apply a CSV/XLSX bulk file. Give users their initial credentials through your approved internal process. Managers have read/report rights by default. Admin can edit role policies and individual overrides; only Super Admin can administer protected Super Admin accounts.

Review SLA policy and dropdown lists in Settings. Configure Outlook/Azure mail and optional AI in Email & AI setup. The notification worker must be running for scheduled reports and alerts.

## Raise a bug

Process Designer or QA selects New issue, fills the description and dropdowns, chooses the developer and testing owner, and adds screenshots/video/supporting files as needed. For a Product Developer, select QA as testing owner. For a Process Developer, select a Process Designer. A Process Designer reporting process work can select themselves for testing.

Reported-against developer is optional and independent of the developer assigned to fix it. Use it only when attribution is known. Files may be up to 20 MB each. If an upload fails after the bug is created, the bug stays saved; retry the failed file in Discussion rather than creating a duplicate.

## Developer tray

Open the assigned issue. Choose Acknowledge to record first response. A substantive developer comment or submitting a fix also records first response when one is missing. Choose Submit fix for testing and enter both the resolution and RCA. The application moves the issue to the designated testing owner's tray. Reassign is available while the issue is in your tray; both developer and tester must match the selected route.

## Test and close or return

The designated Process Designer handles process fixes; the designated QA handles product fixes. Choose Tests passed - Close and record test evidence, or Return to developer and record why the fix failed. A return starts a new correction cycle. Reopen is available to the designated tester for a closed issue and increments the reopen count. Required data correction must be completed before closure.

A verified closure creates a company knowledge article with the developer's resolution and RCA. Reopening withdraws that article until reverified. Only Admin may approve articles for external client visibility.

## Issue details and evidence

Details and Delivery & closure contain the original workbook fields. Use workflow buttons for ownership and status; those controls cannot be bypassed with ordinary form edits. Save each tab before switching. Discussion contains shared comments and attachments; use Internal note for staff-only text. Attachments are shared with anyone permitted to see that issue. Activity records post-import changes.

Imported issues retain their original missing classifications and closure evidence gaps. Use Assign / reassign to link a historical record to named workflow owners before taking a new workflow action. No historical first-response timestamps are inferred.

## Manager dashboard

Use Overview, Employee performance and Reports. Click a metric to drill into issues, or an employee to inspect related work. Employee reporting includes developer assignment/attribution, response/fix/closure averages, return counts, repeated problem families, raised bugs, testing activity and current trays. Filter by team/date. Rankings require at least three measured fix cycles and should be compared within comparable work.

Download branded Excel/PDF reports from the page. The full issue field set is in Excel; PDF register output is a readable summary. The resolution library has full resolution/RCA exports suitable for L1 training.

## Knowledge library and chatbot

Resolution library shows verified closed work. Search or open an article, inspect its fix and RCA, and mark it helpful or needing improvement. L1 assistant answers from matching articles visible to your account and references source bug IDs. If there is no verified match, it says so and suggests raising an issue.

Knowledge search works without an external model. Admin may add Azure OpenAI/OpenAI for generated answers. New verified articles update the search corpus rather than retraining model weights. A configured model receives only the question and selected permitted article text. Global/client-specific publication needs an Admin review; internal articles remain hidden from future client accounts.

## Notifications

After email is configured and enabled, participants get change notifications, the person holding an open issue gets a day-end tray report, and SLA breaches trigger messages. Reporting/configured managers are CC'd. Check Notification log for queued/sent/retry/dead states. No configuration or mailbox credentials are shipped in the package.


## Complete lifecycle forms (version 3)

The reporting form covers the complete main workbook field set and source milestones in eight sections. Calculated fields and later-stage fields are labelled and read-only. Conditional details capture regression baseline, release blocker reason, financial/regulatory impact, correction plan and requested business outcome. Named assignment separates the current fixer from reported-against attribution; additional followers can receive updates.

Use **Submit rectification & RCA** for the developer response, resolution type, root cause, code/change references, developer tests, regression coverage, verification/L1 steps and prevention. Use **Delivery milestones** for actual handover/UAT/deployment and communication dates; tester sign-offs remain role-controlled. Testing requires actual findings and evidence. Production fixes use a separate QA approval, deployment evidence and final closure sequence. Release blockers stop a release until they are closed or their fix has been QA-approved for deployment. Closure enforces required data correction, client confirmation and RCA sharing.

Every bug offers **Full record PDF / Excel**, including the full visible field set and correction cycles. The list PDF remains a concise register; Excel includes the full dataset. See `docs/FIELD_LIFECYCLE_MATRIX.md` for the exact field ownership and conditions. Source recommendations are historical context and are not used as verified RCA.

The downloadable frontend preview uses synthetic demonstration data and local interactions. It displays the reporting, rectification, testing, deployment and closure forms; it does not save to PostgreSQL or send notifications. Run the packaged application for persistent multi-user operation.

## Expanded workspace preview and evidence categories

The dashboard now links directly to Employee performance, Reports centre, Supporting documents, the Resolution & RCA library and (for authorised users) Dropdown administration. The Reports centre exposes nine report families; employee drilldowns offer individual Excel/PDF metrics exports.

Supporting documents (Word, Excel, CSV, PDF) and the Resolution & RCA knowledge library are separate navigation options. Screenshot/video evidence and supporting documents have separate multiple-file inputs both at reporting and in Discussion. Each file is limited to 20 MB; existing attachments are categorised on migration. The Supporting documents workspace inherits issue/client access checks; attachment download repeats the parent-issue access check.

The HTML preview includes Super Admin/Manager/developer/designer/QA/client role visibility simulation, dropdown add/rename/delete, CSV bulk validation/apply, the role-rights matrix, employee rows/drilldowns and a report catalogue. Preview changes affect demonstration state only. The standalone file contains branded sample Excel/PDF downloads for all nine report families, plus individual employee metrics. These exports use fixed synthetic data; live filters and business records run in the connected application. CSV/XLSX bulk imports are supported in the application; the standalone bulk demo accepts CSV. Preview role selection is a design aid, not an authentication mechanism.

## Reporting and administration update — 18 November 2026

- Employee performance includes response-SLA breaches, resolution-SLA breaches and their total. Instances are counted per response cycle or resolution deadline, independently of email attempts. They are attributed to the recorded owner; unverified historical ownership remains unassigned. Bug timing/rankings are separated from requirements/features/change requests. Best and worst tables show up to three eligible developers; the minimum remains three recorded completed bug fix cycles. No missing performers are fabricated.
- The management dashboard PDF is a continuous branded report with global pagination. It includes request-type totals, status/client/severity/current-tray breakdowns, SLA attention items, data readiness, employee results, team averages, both Top 3 lists, and the complete current request register. Client exports omit internal employee sections.
- Clicking a register row opens the full current status: latest action remarks first, all visible fields, attachment downloads, discussion, correction cycles and history. Editing reporting information is a separate control. Existing workflow ownership and client access checks remain enforced.
- Dropdown administration shows each list's affected form fields. Choose a list, then **Edit / Modify**, **Add**, **Rename** or **Delete**, then the manual or bulk method. Manual Modify edits/reorders the entire list; a bulk `modify` row edits the named existing value. Required workflow/policy values stay protected. CSV and Excel formats have headers in row 1. A validation preview precedes bulk application, and invalid batches apply nothing.
- Every workspace page has a Back control and breadcrumb; drawers return to their originating workspace. Admin can open **User login & activity** to inspect every user's last recorded login, last action, activity count and action history. Excel/PDF exports include the recorded actions. User IDs retain attribution across email changes. Page-view clicks are not presented as audited business actions.
- The raising form supports **Bug**, **New Requirement**, **Feature Request** and **Change Request**. New requests require business justification, expected outcome and acceptance criteria; internal requests also require module and priority. Bug-specific reproduction/classification gates remain mandatory for bugs. New IDs use `BUG-`, `REQ-`, `FTR-` and `CHG-` with independent PostgreSQL sequences. Existing workbook IDs remain unchanged for traceability. Request types cannot be changed after number allocation; create a linked request instead. Requirement delivery targets are separate from bug SLA deadlines.

The standalone preview uses synthetic data. It includes three sample developers in each ranking, detailed current-status screens, the redesigned master wizard, per-user activity and sample report downloads. Its CSV/Excel templates are also supplied as separate downloadable files. Live browser UAT and real mail/model/server deployment verification remain separate from the offline/API checks.
# Notification centre

Open **Admin → Notification centre**. Admin and Super Admin have three separate rights by default: manage notification rules/groups, edit email templates, and manage individual overrides. Delegate each through the existing role-rights matrix or individual grant/deny controls. Notification groups affect delivery preferences; they do not grant access to issues or clients.

**Events & schedule:** choose immediate, daily, weekly or off for issue creation, assignment, status/details changes, comments, internal notes, attachments, fix submission, testing, closure, reopening and response/resolution SLA breaches. Open-tray reports support daily, weekly or off. Set timezone, daily time, weekly day and weekly time; blank schedule fields inherit the mail connection's schedule. Frequencies apply per recipient and event. SLA breach recording and performance statistics continue even when breach emails are disabled.

**Groups:** create role, team or named-member groups. Rules inherit workspace defaults, then role groups, team groups and custom groups, then individual overrides. Within each kind, higher priority applies later; group ID breaks ties. A mandatory rule locks the effective setting against later groups and individual overrides. A workspace mandatory rule locks everyone. Use mandatory immediate SLA notifications where appropriate. Inspect the effective-policy preview before saving.

**Individuals:** select a user, inspect the source of each inherited rule, and choose an exception or return to inheritance. Mandatory rules cannot be overridden here. Inactive users receive no notifications; clients never receive internal-note notifications.

**Templates:** edit each event's subject and plain-text body. Daily/weekly batching uses separate digest templates, with compact event summaries in `{{items}}`. Open-tray reports use their own template. Insert supported placeholders from the token list. Unknown placeholders, multiline subjects and executable template expressions are rejected. A preview uses sample data and sends no email. Save changes explicitly; concurrent edits are protected by a revision check.

Managers remain in CC and cannot be removed through these preference controls. Notification recipients are active people already attached to an issue and authorised to see it; selecting a notification group does not subscribe every member to every issue. Mail delivery must be enabled and Outlook/SMTP configured separately. Events occurring while mail is disabled are not queued for retrospective delivery.

Pending notifications are reevaluated against current rules and issue access; saving settings rebuilds queued/retry messages with current templates. Sent or in-flight messages cannot be recalled. Large backlogs are processed in batches and may produce more than one digest. Delivery errors use the existing retry worker and delivery log.

The standalone preview edits local sample settings only. Use the authenticated PostgreSQL application for persistence and real delivery. Validate Outlook delivery in a test environment before production use.

