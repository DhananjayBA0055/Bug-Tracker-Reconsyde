ALTER TABLE work_cycles ADD COLUMN IF NOT EXISTS response_due_at timestamptz;
INSERT INTO schema_versions(version) VALUES(3) ON CONFLICT DO NOTHING;
