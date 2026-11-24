# Workbook mapping and source preservation

The authoritative detailed mapping is [FIELD_LIFECYCLE_MATRIX.md](FIELD_LIFECYCLE_MATRIX.md), with an equivalent CSV. It covers every main tracker column, supplemental delivery fields, stage ownership and validation.

- Bug ID → `bug_id`
- Date Reported → `date_reported`
- Reported By → `reported_by`
- Source → `source`
- Bug Scope → `bug_scope`
- Client / Tenant → `client`
- Client Ticket Ref → `client_ticket_ref`
- Product Module → `product_module`
- Recon Type → `recon_type`
- Environment → `environment`
- Detection Stage → `detection_stage`
- Deployment Phase → `deployment_phase`
- Found in Release → `found_in_release`
- Browser / Device → `browser_device`
- Build / Version Found → `build_version_found`
- Bug Category → `bug_category`
- Regression? → `regression`
- Release Blocker? → `release_blocker`
- Bug Title → `title`
- Steps to Reproduce → `steps_to_reproduce`
- Expected Result → `expected_result`
- Actual Result → `actual_result`
- Severity → `severity`
- Priority → `priority`
- Financial Impact? → `financial_impact`
- Clients Affected (No.) → `clients_affected`
- Records Affected → `records_affected`
- Amount Impacted (INR) → `amount_impacted_inr`
- Regulatory / Audit Impact? → `regulatory_impact`
- Data Correction Required? → `data_correction_required`
- Workaround Available → `workaround_available`
- Status → `status`
- Assigned To → `assigned_to`
- Team → `team`
- Open / Closed → `open_closed`
- Due Date (SLA) → `due_date`
- Resolved Date → `resolved_date`
- Age (days) → `age_days`
- SLA Status → `sla_status`
- Target Fix Release → `target_fix_release`
- Target Release Date → `target_release_date`
- Sprint / Iteration → `sprint`
- Actual Fix Release → `actual_fix_release`
- Actual Release Date → `actual_release_date`
- Release Plan Status → `release_plan_status`
- Post-Deploy Action → `post_deploy_action`
- Resolution Type → `resolution_type`
- Root Cause Category → `root_cause_category`
- Root Cause & Fix Summary → `root_cause_summary`
- Code / PR / Commit Ref → `code_ref`
- Change / Deployment Ticket Ref → `deployment_ticket_ref`
- Test Case / Evidence Ref → `test_evidence_ref`
- Verified By (QA) → `verified_by`
- QA Verified Date → `qa_verified_date`
- Data Correction Completed On → `data_correction_completed_on`
- RCA Shared with Client? → `rca_shared`
- Client Confirmation → `client_confirmation`
- Closed By → `closed_by`
- Closure Date → `closure_date`
- Closure Remarks → `closure_remarks`
- Reopen Count → `reopen_count`
- Remarks → `remarks`

The original 99 records, IDs, missing values and source_metadata are retained. Three source tabs, 57 requirement comparisons and five example release rows remain reference material. They are not silently promoted to operational releases or verified knowledge. New actor-stamped fields never infer who performed historical work. Source recommendation text is exposed separately and flagged when it was copied into Actual Result or Root Cause & Fix Summary.

PostgreSQL uses a unique relational issue ID, revision number and JSONB fields. Users, sessions, releases, comments, attachments, audit, work_cycles, issue_events, knowledge_articles, notification_outbox, settings and migrations are separate tables. Attachment bytes are backed up with the database. Migration 3 adds persistent per-cycle response deadlines; initialization is idempotent and preserves existing users/data/settings.
