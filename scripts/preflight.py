"""Non-secret deployment checks. Run from any directory; no services are changed."""
import argparse
import base64
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--https', action='store_true')
    args = parser.parse_args()
    path = ROOT / '.env'
    if not path.is_file():
        raise SystemExit('Missing .env. Run python scripts/configure.py first.')
    values = {}
    for line in path.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            values[key.strip()] = value.strip()
    for key in ['ADMIN_EMAIL', 'ADMIN_PASSWORD', 'POSTGRES_PASSWORD', 'SETTINGS_ENCRYPTION_KEY']:
        if not values.get(key) or 'replace-with' in values[key]:
            raise SystemExit(f'Missing or placeholder configuration: {key}')
    if len(values['ADMIN_PASSWORD']) < 12:
        raise SystemExit('Bootstrap password must have at least 12 characters.')
    if any(c not in '0123456789abcdefABCDEF' for c in values['POSTGRES_PASSWORD']):
        raise SystemExit('Use the generated hex database password for URL-safe Compose configuration.')
    try:
        if len(base64.urlsafe_b64decode(values['SETTINGS_ENCRYPTION_KEY'].encode())) != 32:
            raise ValueError()
    except Exception:
        raise SystemExit('Invalid settings encryption key; preserve the original key on an upgrade.')
    if args.https and not values.get('APP_DOMAIN'):
        raise SystemExit('Set APP_DOMAIN in .env before enabling the HTTPS proxy.')
    if not shutil.which('docker'):
        raise SystemExit('Docker is not installed or is not on PATH.')
    compose = ['docker', 'compose', '-f', 'compose.yaml']
    if args.https:
        compose += ['-f', 'compose.https.yaml']
    for command in [ ['docker', 'info', '--format', '{{.ServerVersion}}'], compose + ['config', '--quiet'] ]:
        result = subprocess.run(command, cwd=ROOT, capture_output=True)
        if result.returncode:
            raise SystemExit('Docker daemon or Compose configuration check failed. Run docker info and docker compose config --quiet locally; do not share expanded secret values.')
    print('PASS: configuration, Docker daemon and Compose syntax. No services started; no secrets displayed.')

if __name__ == '__main__':
    main()
