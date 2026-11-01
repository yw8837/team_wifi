"""Explicit local, closed-beta, and public-release settings. Missing production safeguards stop startup."""
import os
from urllib.parse import urlsplit


MODE = os.getenv('MODU_ENV', 'local')
BETA = MODE == 'beta'
PUBLIC_RELEASE = MODE == 'public_release'
DEPLOYED = BETA or PUBLIC_RELEASE


def deployed():
    return BETA or PUBLIC_RELEASE


PUBLIC_ORIGIN = (os.getenv('PUBLIC_ORIGIN') or os.getenv('RENDER_EXTERNAL_URL', '')).rstrip('/')
SUPPORT_EMAIL = os.getenv('SUPPORT_EMAIL', '')
RATE_LIMIT_SECRET = os.getenv('RATE_LIMIT_SECRET', '')
HOSTING_LOCATION = os.getenv('HOSTING_LOCATION', '')
DATABASE_LOCATION = os.getenv('DATABASE_LOCATION', '')
STATIC_DIR = os.getenv('STATIC_DIR', '')
ORIGINS = ['https://localhost'] if DEPLOYED else [
    'http://127.0.0.1:5173', 'http://localhost:5173', 'https://localhost', 'http://localhost']
if PUBLIC_ORIGIN:
    ORIGINS.append(PUBLIC_ORIGIN)


def validate():
    if MODE not in ('local', 'beta', 'public_release'):
        raise RuntimeError('MODU_ENV must be local, beta, or public_release.')
    if not deployed():
        return
    url = urlsplit(PUBLIC_ORIGIN)
    if url.scheme != 'https' or not url.hostname or url.hostname in ('localhost', '127.0.0.1') or url.path or url.username or url.query or url.fragment:
        raise RuntimeError('Deployed mode requires a public HTTPS origin.')
    if not os.getenv('DATABASE_URL', '').startswith('postgresql+psycopg://'):
        raise RuntimeError('Deployed mode requires a dedicated PostgreSQL database.')
    if len(RATE_LIMIT_SECRET) < 32:
        raise RuntimeError('Deployed mode requires a strong rate-limit hashing secret.')
    if not SUPPORT_EMAIL or '@' not in SUPPORT_EMAIL or not HOSTING_LOCATION or not DATABASE_LOCATION:
        raise RuntimeError('Deployed mode requires support contact and hosting/database disclosure.')


validate()
