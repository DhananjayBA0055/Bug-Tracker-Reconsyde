CREATE TABLE IF NOT EXISTS schema_versions(version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS users (
 id bigserial PRIMARY KEY, email text UNIQUE NOT NULL, name text NOT NULL,
 password_hash text NOT NULL, role text NOT NULL CHECK(role IN ('admin','manager','editor','viewer','client')),
 clients jsonb NOT NULL DEFAULT '[]', active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash text PRIMARY KEY, user_id bigint NOT NULL REFERENCES users(id), csrf text NOT NULL,
 expires_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS login_attempts (id bigserial PRIMARY KEY, email text NOT NULL, ip text NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS login_attempts_window ON login_attempts(created_at);
CREATE SEQUENCE IF NOT EXISTS bug_number START 1;
CREATE TABLE IF NOT EXISTS issues (
 id text PRIMARY KEY, data jsonb NOT NULL, revision integer NOT NULL DEFAULT 1,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS issues_data ON issues USING gin(data);
CREATE TABLE IF NOT EXISTS releases (
 id text PRIMARY KEY, data jsonb NOT NULL, revision integer NOT NULL DEFAULT 1, updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS settings (key text PRIMARY KEY, data jsonb NOT NULL);
CREATE TABLE IF NOT EXISTS comments (
 id bigserial PRIMARY KEY, issue_id text NOT NULL REFERENCES issues(id), user_id bigint NOT NULL REFERENCES users(id),
 body text NOT NULL, internal boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS attachments (
 id uuid PRIMARY KEY, issue_id text NOT NULL REFERENCES issues(id), user_id bigint NOT NULL REFERENCES users(id),
 name text NOT NULL, content bytea NOT NULL, size integer NOT NULL CHECK(size <= 10485760), created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS audit (
 id bigserial PRIMARY KEY, issue_id text, actor text NOT NULL, action text NOT NULL, changes jsonb NOT NULL DEFAULT '{}',
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS audit_issue ON audit(issue_id, id DESC);
CREATE TABLE IF NOT EXISTS imports (source_hash text PRIMARY KEY, filename text NOT NULL, issue_count integer NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
INSERT INTO schema_versions(version) VALUES(1) ON CONFLICT DO NOTHING;
