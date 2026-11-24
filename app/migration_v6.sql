CREATE TABLE IF NOT EXISTS notification_events(
 id bigserial PRIMARY KEY,event_key text UNIQUE NOT NULL,event_type text NOT NULL,issue_id text REFERENCES issues(id),
 context jsonb NOT NULL,internal boolean NOT NULL DEFAULT false,created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS notification_deliveries(
 event_id bigint NOT NULL REFERENCES notification_events(id),user_id bigint NOT NULL REFERENCES users(id),
 frequency text NOT NULL,status text NOT NULL DEFAULT 'pending',due_at timestamptz NOT NULL,outbox_id bigint REFERENCES notification_outbox(id),
 PRIMARY KEY(event_id,user_id)
);
CREATE INDEX IF NOT EXISTS notification_deliveries_due ON notification_deliveries(status,due_at);
ALTER TABLE notification_outbox ADD COLUMN IF NOT EXISTS policy_metadata jsonb NOT NULL DEFAULT '{}';
INSERT INTO schema_versions(version) VALUES(6) ON CONFLICT DO NOTHING;
