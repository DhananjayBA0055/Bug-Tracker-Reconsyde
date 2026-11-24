ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
UPDATE users SET role='product_developer' WHERE role='editor';
UPDATE users SET role='manager' WHERE role='viewer';
UPDATE users SET role='super_admin' WHERE id=(SELECT min(id) FROM users WHERE role='admin') AND NOT EXISTS(SELECT 1 FROM users WHERE role='super_admin');
ALTER TABLE users ADD CONSTRAINT users_role_check CHECK(role IN ('super_admin','admin','manager','product_developer','process_designer','quality_analyst','process_developer','client'));
ALTER TABLE users ADD COLUMN IF NOT EXISTS team text NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS manager_emails jsonb NOT NULL DEFAULT '[]';
ALTER TABLE users ADD COLUMN IF NOT EXISTS permissions jsonb NOT NULL DEFAULT '{}';
UPDATE users SET team=CASE WHEN role='product_developer' THEN 'Product Team' WHEN role IN ('process_developer','process_designer') THEN 'Process Team' WHEN role='quality_analyst' THEN 'QA Team' ELSE '' END WHERE team='';
UPDATE settings SET data=jsonb_set(data,'{Team}','["Process Team","Product Team","QA Team"]'::jsonb) WHERE key='lists';
ALTER TABLE attachments DROP CONSTRAINT IF EXISTS attachments_size_check;
ALTER TABLE attachments ADD CONSTRAINT attachments_size_check CHECK(size <= 20971520);
CREATE TABLE IF NOT EXISTS work_cycles(
 id bigserial PRIMARY KEY, issue_id text NOT NULL REFERENCES issues(id), developer_id bigint NOT NULL REFERENCES users(id),
 assigned_at timestamptz NOT NULL DEFAULT now(), responded_at timestamptz, fixed_at timestamptz, returned_at timestamptz,
 resolution text, rca text
);
CREATE INDEX IF NOT EXISTS work_cycles_issue ON work_cycles(issue_id,id DESC);
CREATE TABLE IF NOT EXISTS issue_events(
 id bigserial PRIMARY KEY, issue_id text NOT NULL REFERENCES issues(id), actor_id bigint REFERENCES users(id),
 kind text NOT NULL, data jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS knowledge_articles(
 issue_id text PRIMARY KEY REFERENCES issues(id), data jsonb NOT NULL,
 visibility text NOT NULL DEFAULT 'internal' CHECK(visibility IN ('internal','client_specific','global')),
 active boolean NOT NULL DEFAULT true, approved_by bigint REFERENCES users(id),
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS notification_outbox(
 id bigserial PRIMARY KEY, dedup_key text UNIQUE NOT NULL, recipients jsonb NOT NULL, cc jsonb NOT NULL DEFAULT '[]',
 subject text NOT NULL, body text NOT NULL, status text NOT NULL DEFAULT 'queued',
 attempts integer NOT NULL DEFAULT 0, next_attempt timestamptz NOT NULL DEFAULT now(),
 last_error text, sent_at timestamptz, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS notification_due ON notification_outbox(status,next_attempt);
CREATE TABLE IF NOT EXISTS chatbot_feedback(
 id bigserial PRIMARY KEY,user_id bigint NOT NULL REFERENCES users(id),issue_id text REFERENCES issues(id),
 helpful boolean NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO schema_versions(version) VALUES(2) ON CONFLICT DO NOTHING;
