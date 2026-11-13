"""Informational client signals; authorization depends on server roles, not device hints."""
import re


def mobile_client(request, *, platform=None):
    headers = request.headers
    return bool(platform == 'android' or headers.get('X-Moduyuga-Client') == 'android'
                or headers.get('Origin') in ('https://localhost', 'capacitor://localhost')
                or headers.get('Sec-CH-UA-Mobile') == '?1'
                or re.search(r'Android|iPhone|iPad|iPod|Mobile', headers.get('User-Agent', ''), re.I))
