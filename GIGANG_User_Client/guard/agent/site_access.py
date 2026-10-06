"""Read central device grants. An unavailable/stale policy never grants access."""
import hashlib
import os
import socket
import threading
import time
from datetime import datetime
import requests


def device_id():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Cryptography', 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            value = winreg.QueryValueEx(key, 'MachineGuid')[0]
    except (ImportError, OSError):
        value = socket.gethostname() + ':' + os.environ.get('COMPUTERNAME', '')
    return hashlib.sha256(('gigang-device:' + value).encode()).hexdigest()


def canonical_host(domain):
    host = domain.lower().rstrip('.')
    return host[4:] if host.startswith('www.') else host


class SiteAccess:
    def __init__(self, base):
        self.base = base
        self.device = device_id()
        self.grants = []
        self.checked = 0
        self.lock = threading.Lock()

    def refresh(self, force=False):
        requested_at = time.monotonic()
        with self.lock:
            # Reuse only a response completed after this request started when forced.
            # Ordinary background/hosts reads have at most a one-second cache.
            if (force and self.checked >= requested_at) or (not force and time.monotonic() - self.checked < 1):
                return
            try:
                response = requests.get(self.base + '/site-access/device', params={'device_id':self.device}, timeout=3)
                response.raise_for_status()
                rows = response.json()['grants']
                if not isinstance(rows, list):
                    raise ValueError('Invalid grants')
                self.grants = rows
            except (requests.RequestException, ValueError, KeyError):
                self.grants = []
            self.checked = time.monotonic()

    def permission(self, domain, force=False):
        self.refresh(force=force)
        now = time.time()
        for grant in self.grants:
            try:
                if canonical_host(grant['domain']) == canonical_host(domain) and datetime.fromisoformat(grant['expires_at']).timestamp() > now:
                    return {'status':'approved', 'grant_id':grant['grant_id'], 'expires_at':grant['expires_at']}
            except (KeyError, TypeError, ValueError):
                continue
        return None

    def effective_domains(self, domains):
        # A parent-domain hosts rule cannot be removed by a narrower child grant.
        self.refresh()
        return [domain for domain in domains if not self.permission(domain)]
