CREATE SEQUENCE IF NOT EXISTS requirement_number;
CREATE SEQUENCE IF NOT EXISTS feature_number;
CREATE SEQUENCE IF NOT EXISTS change_number;
CREATE TABLE IF NOT EXISTS sla_breaches(
 breach_key text PRIMARY KEY, issue_id text NOT NULL REFERENCES issues(id),cycle_id bigint REFERENCES work_cycles(id),
 breach_type text NOT NULL CHECK(breach_type IN ('response','resolution')),user_id bigint REFERENCES users(id),
 due_at timestamptz NOT NULL,detected_at timestamptz NOT NULL DEFAULT now(), request_kind text NOT NULL DEFAULT 'Bug'
);
CREATE INDEX IF NOT EXISTS sla_breaches_user ON sla_breaches(user_id,due_at);
INSERT INTO schema_versions(version) VALUES(5) ON CONFLICT DO NOTHING;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at timestamptz;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_action_at timestamptz;
ALTER TABLE audit ADD COLUMN IF NOT EXISTS user_id bigint REFERENCES users(id);
UPDATE audit a SET user_id=u.id FROM users u WHERE lower(a.actor)=lower(u.email) AND a.user_id IS NULL;
UPDATE users u SET last_login_at=(SELECT max(created_at) FROM audit WHERE user_id=u.id AND action='Signed in'),last_action_at=(SELECT max(created_at) FROM audit WHERE user_id=u.id);
