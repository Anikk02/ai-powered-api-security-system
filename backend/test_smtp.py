import sys, os
sys.path.insert(0, '.')

from dotenv import load_dotenv

import smtplib
from app.core.config import settings

host = settings.SMTP_HOST
port = settings.SMTP_PORT
user = settings.SMTP_USER
pwd  = settings.SMTP_PASSWORD

print(f'SMTP_HOST = {host}')
print(f'SMTP_PORT = {port}')
print(f'SMTP_USER = {user}')
print(f'SMTP_PASSWORD = {"*" * len(pwd) if pwd else "(empty)"}')
print()

if not host:
    print('ERROR: SMTP_HOST is empty in .env')
elif 'your_gmail' in user:
    print('ERROR: SMTP credentials are still placeholder values in .env!')
else:
    try:
        print('Connecting to SMTP...')
        with smtplib.SMTP(host, port, timeout=10) as s:
            s.ehlo()
            s.starttls()
            print('TLS: OK')
            s.login(user, pwd)
            print('Login: OK - credentials are valid!')
    except smtplib.SMTPAuthenticationError as e:
        print(f'AUTH ERROR: Wrong password or App Password not used. Detail: {e}')
    except Exception as e:
        print(f'SMTP ERROR: {type(e).__name__}: {e}')
