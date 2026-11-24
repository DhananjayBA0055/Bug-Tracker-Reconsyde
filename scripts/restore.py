"""Restore to an EMPTY isolated Compose database. Never drops or cleans an existing DB."""
import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dump', type=Path)
    parser.add_argument('--project-name', required=True, help='Dedicated recovery project, not the live project')
    parser.add_argument('--confirm-empty-restore', action='store_true', required=True)
    args = parser.parse_args()
    if not args.dump.is_file() or args.dump.open('rb').read(5) != b'PGDMP':
        raise SystemExit('Provide an existing PostgreSQL custom-format dump.')
    base = ['docker', 'compose', '-p', args.project_name, '-f', 'compose.yaml']
    # Do not start app/worker: they would migrate/seed an empty recovery database.
    subprocess.run(base + ['up', '-d', '--wait', 'db'], cwd=ROOT, check=True)
    state = subprocess.run(base + ['ps', '--status', 'running', '--services'], cwd=ROOT, capture_output=True, text=True, check=True)
    if set(state.stdout.splitlines()) & {'app', 'worker'}:
        raise SystemExit('App/worker are running in this project. Use a new isolated recovery project. Nothing restored.')
    query = "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema')"
    count = subprocess.run(base + ['exec', '-T', 'db', 'psql', '-U', 'tracker', '-d', 'tracker', '-Atc', query], cwd=ROOT, capture_output=True, text=True, check=True)
    if count.stdout.strip() != '0':
        raise SystemExit('Recovery database is not empty. Refusing to overwrite data. Use a new recovery project.')
    with args.dump.open('rb') as stream:
        result = subprocess.run(base + ['exec', '-T', 'db', 'pg_restore', '-U', 'tracker', '-d', 'tracker', '--no-owner', '--no-privileges', '--exit-on-error', '--single-transaction'], cwd=ROOT, stdin=stream)
    if result.returncode:
        raise SystemExit('Restore failed; transaction rolled back. App and worker were not started.')
    quarantine = "UPDATE settings SET data=jsonb_set(data,'{enabled}','false'::jsonb) WHERE key='mail'; UPDATE settings SET data=jsonb_set(data,'{provider}','\"retrieval\"'::jsonb) WHERE key='ai';"
    subprocess.run(base + ['exec', '-T', 'db', 'psql', '-U', 'tracker', '-d', 'tracker', '-v', 'ON_ERROR_STOP=1', '-c', quarantine], cwd=ROOT, check=True)
    print('Database restored. App and worker remain stopped.')
    print('Recovery safety settings applied: outbound mail disabled and AI set to retrieval. Before starting, preserve the original SETTINGS_ENCRYPTION_KEY and choose a distinct APP_PORT. Re-enable integrations only after review.')

if __name__ == '__main__':
    main()
