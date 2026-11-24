"""Create a PostgreSQL custom-format backup without shell redirection or secret output."""
import argparse
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    parser.add_argument('--project-name', help='Existing Compose project, if deployed with -p')
    args = parser.parse_args()
    destination = (args.output or ROOT / 'backups' / ('tracker-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.dump')).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise SystemExit('Output exists; choose another path. No backup overwritten.')
    partial = destination.with_name(destination.name + '.partial')
    command = ['docker', 'compose']
    if args.project_name:
        command += ['-p', args.project_name]
    command += ['-f', 'compose.yaml', 'exec', '-T', 'db', 'pg_dump', '-U', 'tracker', '-d', 'tracker', '-Fc']
    created_partial = False
    try:
        fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created_partial = True
        with os.fdopen(fd, 'wb') as stream:
            result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.PIPE)
        if result.returncode:
            raise RuntimeError('pg_dump failed; check local database service logs.')
        if partial.stat().st_size < 5 or partial.open('rb').read(5) != b'PGDMP':
            raise RuntimeError('Backup is not a PostgreSQL custom-format dump.')
        # Same-directory hard link is exclusive: a competing writer cannot be overwritten.
        os.link(partial, destination)
        partial.unlink()
    except Exception:
        if created_partial:
            partial.unlink(missing_ok=True)
        raise
    print(f'Backup created: {destination}')
    print('Contains records, attachments, encrypted integration secrets and audit history. Store securely with the matching encryption key kept separately.')

if __name__ == '__main__':
    main()
