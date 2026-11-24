ALTER TABLE attachments ADD COLUMN IF NOT EXISTS category text NOT NULL DEFAULT 'supporting_document';
UPDATE attachments SET category='media' WHERE lower(name) ~ '\.(png|jpe?g|webp|gif|mp4|webm|mov)$';
INSERT INTO schema_versions(version) VALUES(4) ON CONFLICT DO NOTHING;
