"""Create deployment secrets once; never overwrite an existing configuration."""
import base64
import getpass
import os
import secrets
from pathlib import Path

root=Path(__file__).resolve().parent.parent
path=root/'.env'
if path.exists():raise SystemExit('.env already exists; edit it deliberately rather than replacing secrets.')
email=input('Administrator email [admin@bancapp.in]: ').strip() or 'admin@bancapp.in'
if '@' not in email or any(c in email for c in '\n\r$#"\' '):raise SystemExit('Enter a valid email.')
password=getpass.getpass('Initial administrator password (12+ characters; no spaces, quotes or $): ')
if len(password)<12 or any(c in password for c in '\n\r$#"\' '):raise SystemExit('Use at least 12 characters without spaces, quotes, # or $.')
config=f'ADMIN_EMAIL={email}\nADMIN_NAME=Bancapp Administrator\nADMIN_PASSWORD={password}\nPOSTGRES_PASSWORD={secrets.token_hex(32)}\nSETTINGS_ENCRYPTION_KEY={base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()}\nCOOKIE_SECURE=false\nAPP_PORT=8000\n'
fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:f.write(config)
print('Configuration created. Run: docker compose up --build -d')
