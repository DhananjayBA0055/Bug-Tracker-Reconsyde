# Requested feature coverage

| Requirement | Implementation | Setup / behavior |
| --- | --- | --- |
| Six internal user categories plus Admin/Super Admin | Business roles and protected Super Admin | Create staff from Team & access |
| Three business teams | Process Team, Product Team, QA Team | Assigned by role; editable user team |
| Process Developer testing loop | Developer -> designated Process Designer -> close/return | Enforced API workflow |
| Product Developer testing loop | Developer -> designated QA -> close/return | Enforced API workflow |
| Frontend user/rights administration and bulk upload | Individual edits, role matrix, user overrides, CSV/XLSX preview/apply | Match existing users by email |
| Dropdown-oriented bug reporting | Client, classification, severity, priority, module, environment, developer and tester selections | Narrative fields remain text |
| Dropdown add/delete/modify/bulk | UI master editor and CSV/XLSX bulk operations | Workflow/policy structural values protected; historical values retained |
| Manager performance dashboard and drilldown | Employee cycles, response/fix/closure, returns, repeats, attribution, tester activity, team averages | No fabricated historical timing; ranking minimum 3 fix cycles |
| Email each attached person on bug changes, managers CC | Transactional notification queue and worker | Configure enabled Outlook/Graph or SMTP connection |
| Daily end-of-day open-tray report, managers CC | Per-user timezone-aware digest | Default 18:00 Asia/Kolkata; editable |
| SLA breach emails, managers CC | Response and resolution alerts | Deduplicated by cycle/deadline; severity policy required |
| Frontend Outlook/Azure mail setup | Graph app configuration or TLS SMTP | Azure app/tenant consent or approved relay credentials required |
| Bancapp branding | Supplied existing logo and blue theme | Used in UI and generated reports |
| Excel and branded PDF reports/dashboard | Server-generated XLSX/PDF for nine report families | Full issue fields in Excel; readable PDF register summary plus full-record PDF/Excel per bug |
| Screenshots/videos up to 20 MB | Reporting form and issue discussion uploads | File type and size checks |
| Word/Excel/CSV/PDF evidence | DOC/DOCX, XLS/XLSX, CSV, PDF | Up to 20 MB each |
| Bug library with mandatory developer resolution/RCA | Generated on tester-verified closure | Reopening withdraws article; UI and XLSX/PDF exports |
| Unique bug number | PostgreSQL sequence and unique key | Existing BUG-0001 to BUG-0099 retained |
| Future clients and current L1 chatbot | Client roles, approved article visibility and cited assistant | Retrieval works now; model-generated answers require configured Azure OpenAI/OpenAI |

Knowledge growth means that newly verified resolutions are indexed for retrieval. It is not unsupervised model retraining. Existing imported closed records without developer-authored resolution/RCA remain historical records rather than automatically approved training articles.


## Complete lifecycle forms (version 3)

The reporting form covers the complete main workbook field set and source milestones in eight sections. Calculated fields and later-stage fields are labelled and read-only. Conditional details capture regression baseline, release blocker reason, financial/regulatory impact, correction plan and requested business outcome. Named assignment separates the current fixer from reported-against attribution; additional followers can receive updates.

Use **Submit rectification & RCA** for the developer response, resolution type, root cause, code/change references, developer tests, regression coverage, verification/L1 steps and prevention. Use **Delivery milestones** for actual handover/UAT/deployment and communication dates; tester sign-offs remain role-controlled. Testing requires actual findings and evidence. Production fixes use a separate QA approval, deployment evidence and final closure sequence. Release blockers stop a release until they are closed or their fix has been QA-approved for deployment. Closure enforces required data correction, client confirmation and RCA sharing.

Every bug offers **Full record PDF / Excel**, including the full visible field set and correction cycles. The list PDF remains a concise register; Excel includes the full dataset. See `docs/FIELD_LIFECYCLE_MATRIX.md` for the exact field ownership and conditions. Source recommendations are historical context and are not used as verified RCA.

The downloadable frontend preview uses synthetic demonstration data and local interactions. It displays the reporting, rectification, testing, deployment and closure forms; it does not save to PostgreSQL or send notifications. Run the packaged application for persistent multi-user operation.
# Notification administration extension

Implemented in authenticated API, PostgreSQL worker and frontend: per-event enablement/cadence, daily/weekly schedules, role/team/custom groups, individual exceptions, mandatory locks, editable plain-text subjects/bodies and digest templates, safe no-send preview, three granular administration rights, revision/audit history, queued-policy rechecks and manager CC enforcement. Preview uses local demo state. Actual provider delivery requires configured infrastructure and deployment UAT.

