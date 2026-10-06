"""GIGANG Agent v3.5.1: event collection + Railway central policy + Windows hosts blocking."""
import ctypes
import getpass
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import requests
from link_metadata import link_metadata
from image_ocr import recognize_image
import clipboard_watch
from site_access import SiteAccess

VERSION = '3.8.3'
PROJECT_ROOT = Path(__file__).resolve().parents[2]

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / '.env')
except Exception:
    pass

SERVER_URL = os.getenv('RAILWAY_URL', 'https://bountiful-nature-production-22ec.up.railway.app/events')
SERVER_BASE = SERVER_URL.rsplit('/', 1)[0] if SERVER_URL.rstrip('/').endswith('/events') else SERVER_URL.rstrip('/')
POLICY_URL = os.getenv('RAILWAY_POLICY_URL', SERVER_BASE + '/policy')
SITE_ACCESS = SiteAccess(SERVER_BASE)
SERVER_DOMAIN = urlsplit(SERVER_URL).hostname
LOCAL_EXTENSION_PORT = int(os.getenv('GIGANG_EXTENSION_PORT', '8765'))
POLICY_SYNC_SECONDS = max(1, int(os.getenv('GIGANG_POLICY_SYNC_SECONDS', '1')))
USER_NAME = getpass.getuser()
PC_NAME = socket.gethostname()
BLOCKLIST_FILE = PROJECT_ROOT / 'runtime' / 'blocked_domains.json'
_policy_status = {'ok': None, 'last_success': None, 'error': None}
_hosts_status = {'ok': None, 'last_apply': None, 'error': None, 'blocked_count': 0}
HOSTS_BEGIN = '# BEGIN GIGANG MANAGED BLOCK'
HOSTS_END = '# END GIGANG MANAGED BLOCK'
HOSTS_PATH = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'System32' / 'drivers' / 'etc' / 'hosts'

def normalize_domain(value):
    if not isinstance(value, str):
        return ''
    value = value.strip().lower()
    value = re.sub(r'^https?://', '', value)
    value = value.split('/', 1)[0].split(':', 1)[0].strip('.')
    if not value or len(value) > 253 or not re.fullmatch(r'[a-z0-9.-]+', value):
        return ''
    return value

def load_blocklist():
    try:
        payload = json.loads(BLOCKLIST_FILE.read_text(encoding='utf-8'))
        raw = payload.get('blocked_domains', []) if isinstance(payload, dict) else []
        source_updated_at = payload.get('updated_at') if isinstance(payload, dict) else None
    except (FileNotFoundError, OSError, ValueError, TypeError):
        raw, source_updated_at = [], None
    domains = sorted({normalize_domain(item) for item in raw if normalize_domain(item)})
    return {
        'blocked_domains': domains,
        'updated_at': source_updated_at,
        'central_sync': dict(_policy_status),
    }

def save_blocklist(domains, updated_at=None):
    clean = sorted({normalize_domain(item) for item in domains if normalize_domain(item)})
    BLOCKLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'blocked_domains': clean,
        'updated_at': updated_at or datetime.now(timezone.utc).isoformat(),
        'source': 'railway-central-policy',
    }
    temp = BLOCKLIST_FILE.with_suffix('.tmp')
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(BLOCKLIST_FILE)
    return clean

def _strip_managed_hosts_block(lines):
    out = []
    inside = False
    for line in lines:
        marker = line.strip()
        if marker == HOSTS_BEGIN:
            inside = True
            continue
        if inside and marker == HOSTS_END:
            inside = False
            continue
        if not inside:
            out.append(line)
    return out

def _hosts_domains(domains):
    result = set()
    for item in domains:
        domain = normalize_domain(item)
        if not domain or domain in {'localhost', SERVER_DOMAIN}:
            continue
        result.add(domain)
        if not domain.startswith('www.'):
            result.add('www.' + domain)
    return sorted(result)

def apply_windows_blocklist(domains):
    """Apply central policy directly to the Windows hosts file.

    USER_START runs elevated, so Chrome/Edge/etc. do not need an extension.
    Only the GIGANG-managed marker block is replaced; other hosts entries remain untouched.
    """
    targets = _hosts_domains(domains)
    try:
        try:
            original = HOSTS_PATH.read_text(encoding='utf-8', errors='ignore').splitlines()
        except FileNotFoundError:
            original = []
        kept = _strip_managed_hosts_block(original)
        while kept and not kept[-1].strip():
            kept.pop()
        block = []
        if targets:
            block = [HOSTS_BEGIN]
            for domain in targets:
                block.append(f'0.0.0.0 {domain} # GIGANG')
                block.append(f':: {domain} # GIGANG')
            block.append(HOSTS_END)
        merged = kept + ([''] if kept and block else []) + block
        text = '\r\n'.join(merged) + '\r\n'
        current = HOSTS_PATH.read_text(encoding='utf-8', errors='ignore') if HOSTS_PATH.exists() else ''
        if current.replace('\r\n','\n') != text.replace('\r\n','\n'):
            HOSTS_PATH.write_text(text, encoding='utf-8', newline='')
            subprocess.run(['ipconfig','/flushdns'], capture_output=True, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        _hosts_status.update(ok=True, last_apply=datetime.now(timezone.utc).isoformat(), error=None, blocked_count=len(targets))
        return True
    except (OSError, PermissionError) as error:
        _hosts_status.update(ok=False, error=type(error).__name__)
        print(f'[차단 적용 실패] Windows hosts 수정 권한을 확인하세요: {type(error).__name__}', flush=True)
        return False

def apply_saved_policy():
    policy = load_blocklist()
    return apply_windows_blocklist(SITE_ACCESS.effective_domains(policy.get('blocked_domains', [])))

def sync_central_policy():
    try:
        response = requests.get(POLICY_URL, timeout=5, headers={'Cache-Control': 'no-cache'})
        response.raise_for_status()
        payload = response.json()
        raw = payload.get('blocked_domains', []) if isinstance(payload, dict) else None
        if not isinstance(raw, list):
            raise ValueError('invalid policy payload')
        clean = save_blocklist(raw, payload.get('updated_at'))
        hosts_ok = apply_windows_blocklist(SITE_ACCESS.effective_domains(clean))
        _policy_status.update(ok=True, last_success=datetime.now(timezone.utc).isoformat(), error=None)
        return hosts_ok
    except (requests.RequestException, ValueError, TypeError) as error:
        _policy_status.update(ok=False, error=type(error).__name__)
        apply_saved_policy()
        return False

def policy_sync_loop():
    # 시작 즉시 한 번 받고, 이후 주기적으로 중앙 정책을 동기화한다.
    while True:
        sync_central_policy()
        time.sleep(POLICY_SYNC_SECONDS)

def get_local_ip():
    try:
        value = socket.gethostbyname(socket.gethostname())
        if not ipaddress.ip_address(value).is_loopback:
            return value
    except (OSError, ValueError):
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect((SERVER_DOMAIN, 443))
            return probe.getsockname()[0]
    except OSError:
        return 'unknown'

def base_event(kind, target):
    return {'user':USER_NAME, 'pc_name':PC_NAME, 'local_ip':get_local_ip(),
            'event_type':kind, 'target':target, 'agent_version':VERSION, 'device_id':SITE_ACCESS.device}

def extension_event(path, data):
    if not isinstance(data, dict):
        raise ValueError('JSON object required')
    target = data.get('target')
    if not isinstance(target, str) or not target.strip() or len(target)>253:
        raise ValueError('Valid site hostname required')
    kind = {'/download-event': data.get('event_type'), '/copy-event': 'COPY_ATTEMPT', '/paste-event': 'PASTE_ATTEMPT', '/upload-event': 'FILE_UPLOAD_ATTEMPT'}[path]
    result = base_event(kind, target)
    result['source'] = 'chrome-extension'
    if path == '/download-event' or kind == 'COPY_ATTEMPT':
        if target != 'desktop-oli.tail2bbbea.ts.net':
            raise ValueError('Only the internal DB portal is monitored')
        if kind == 'COPY_ATTEMPT':
            if data.get('source_path') != '/db' or data.get('detection_scope') != 'customer_table':
                raise ValueError('Customer table selection required')
            result.update(source_path='/db', detection_scope='customer_table')
        else:
            states = {'DOWNLOAD_STARTED':'in_progress', 'DOWNLOAD_COMPLETED':'complete', 'DOWNLOAD_INTERRUPTED':'interrupted'}
            if kind not in states or data.get('download_state') != states[kind] or data.get('source_path') != '/db/download':
                raise ValueError('Invalid download event')
            if type(data.get('download_id')) is not int or data['download_id'] < 0:
                raise ValueError('Invalid download ID')
            name = data.get('file_name', '')
            if not isinstance(name, str) or len(name) > 1024:
                raise ValueError('Invalid file name')
            result.update(source_path='/db/download', download_id=data['download_id'], download_state=states[kind], file_name=name)
            size = data.get('file_size')
            if size is not None:
                if type(size) is not int or size < 0: raise ValueError('Invalid file size')
                result['file_size'] = size
    elif kind == 'PASTE_ATTEMPT':
        length = data.get('text_length')
        if type(length) is not int or not 0 < length <= 100_000_000:
            raise ValueError('text_length must be a positive integer')
        result['text_length'] = length
    elif kind == 'FILE_UPLOAD_ATTEMPT':
        name, size = data.get('file_name'), data.get('file_size')
        if not isinstance(name, str) or len(name)>1024:
            raise ValueError('Valid file name required')
        if type(size) is not int or size<0:
            raise ValueError('Valid file size required')
        result.update(file_name=name, file_size=size)
    stamp = data.get('timestamp')
    if stamp is not None:
        if not isinstance(stamp,str) or len(stamp)>64:
            raise ValueError('Valid timestamp required')
        parsed = datetime.fromisoformat(stamp.replace('Z','+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('Timestamp must include timezone')
        result['client_event_time'] = parsed.astimezone(timezone.utc).isoformat()
    result.update(link_metadata(data, kind, target))
    return result

def attach_authorization(event, data):
    requested = data.get('authorization')
    if isinstance(requested, dict):
        grant = SITE_ACCESS.permission(event['target'])
        if grant and requested.get('grant_id') == grant['grant_id']:
            event['authorization'] = grant

def send_to_railway(event):
    try:
        response = requests.post(SERVER_URL, json=event, timeout=8)
        response.raise_for_status()
        print(f"[서버 전송 성공] {event['event_type']} {event['target']}", flush=True)
        return True
    except requests.RequestException as error:
        print(f"[서버 전송 실패] {type(error).__name__} {event['event_type']}", flush=True)
        return False

class ExtensionEventHandler(BaseHTTPRequestHandler):
    def respond(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Access-Control-Allow-Headers','Content-Type')
        self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.respond(200,{})

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path == '/health':
            policy = load_blocklist()
            self.respond(200,{'service':'GIGANGAgent','version':VERSION,
                              'blocked_count':len(policy['blocked_domains']),
                              'central_policy_ok':_policy_status['ok'],
                              'central_policy_last_success':_policy_status['last_success'],
                              'windows_blocking_ok':_hosts_status['ok'],
                              'windows_blocked_hostnames':_hosts_status['blocked_count'],
                              'device_id':SITE_ACCESS.device, 'clipboard_watch':dict(clipboard_watch.status)})
        elif path == '/site-permission':
            domain = normalize_domain(parse_qs(urlsplit(self.path).query).get('domain', [''])[0])
            grant = SITE_ACCESS.permission(domain, force=True)
            self.respond(200, {'allowed':bool(grant), 'authorization':grant})
        elif path == '/blocklist':
            self.respond(200, load_blocklist())
        elif path == '/sync-policy':
            ok = sync_central_policy()
            self.respond(200 if ok else 502, load_blocklist())
        else:
            self.respond(404,{'error':'Not found'})

    def do_POST(self):
        if self.path in ('/image-ocr', '/image-event', '/image-baseline', '/site-blocked'):
            origin = self.headers.get('Origin', '')
            if not re.fullmatch(r'chrome-extension://[a-p]{32}', origin):
                self.respond(403, {'error':'EXTENSION_ORIGIN_REQUIRED'})
                return
            try:
                count = int(self.headers.get('Content-Length','0'))
                limit = 11_200_000 if self.path == '/image-ocr' else 2_000_000 if self.path == '/image-baseline' else 16384
                if not 0 < count <= limit:
                    self.respond(413, {'error':'IMAGE_REQUEST_TOO_LARGE'})
                    return
                self.connection.settimeout(15)
                data = json.loads(self.rfile.read(count).decode('utf-8'))
                if self.path == '/site-blocked':
                    target = normalize_domain(data.get('target'))
                    if not target: raise ValueError('Invalid target')
                    event = base_event('SITE_BLOCKED', target)
                    event['source'] = 'chrome-extension'
                    saved = send_to_railway(event)
                    self.respond(200 if saved else 502, {'status':'saved' if saved else 'failed'})
                    return
                if self.path == '/image-baseline':
                    clipboard_watch.save_baseline(origin, data)
                    self.respond(200, {'status':'ready'})
                    return
                if self.path == '/image-ocr':
                    result = recognize_image(data)
                    self.respond(200 if result.get('status') == 'ok' else 422, result)
                    return
                event = extension_event('/upload-event', data)
                guard = data.get('image_guard')
                if not isinstance(guard, dict) or guard.get('outcome') not in ('blocked_match','held_error','no_match') or guard.get('channel') not in ('paste','file','drop'):
                    raise ValueError('Invalid image outcome')
                if (guard['outcome'] == 'blocked_match') != (event.get('match_status') == 'matched'):
                    raise ValueError('Inconsistent image result')
                error = guard.get('error')
                if error is not None and (not isinstance(error,str) or not re.fullmatch(r'[A-Z_]{1,64}',error)):
                    raise ValueError('Invalid image error')
                event['image_guard'] = {'outcome':guard['outcome'],'channel':guard['channel'],
                    'error':error,'cache_hit':guard.get('cache_hit') is True}
                event['bytes_sent'] = 0
                attach_authorization(event, data)
                saved = send_to_railway(event)
                self.respond(200 if saved else 502, {'status':'saved' if saved else 'failed', 'event_type':'FILE_UPLOAD_ATTEMPT'})
            except (ValueError, UnicodeError, OSError):
                self.respond(400, {'status':'error','error':'INVALID_IMAGE_REQUEST'})
            return
        if self.path not in ('/upload-event','/paste-event','/copy-event','/download-event'):
            self.respond(404,{'error':'Not found'})
            return
        try:
            count = int(self.headers.get('Content-Length','0'))
            if not 0 < count <= 16384:
                self.respond(413,{'error':'Metadata payload too large or empty'})
                return
            data = json.loads(self.rfile.read(count).decode('utf-8'))
            event = extension_event(self.path, data)
        except (ValueError, UnicodeError):
            self.respond(400,{'error':'Invalid event metadata'})
            return
        attach_authorization(event, data)
        success = send_to_railway(event)
        if success:
            self.respond(200,{'status':'saved', 'event_type':event['event_type']})
        else:
            self.respond(502,{'error':'Railway delivery failed'})

    def log_message(self,*args):
        pass

def get_domains():
    try:
        result = subprocess.run(['ipconfig','/displaydns'],capture_output=True,text=True,
                                encoding='utf-8',errors='ignore',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except OSError:
        return set()
    return {line.strip().lower() for line in result.stdout.splitlines()
            if re.fullmatch(r'[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',line.strip())}

def main():
    from lifecycle import mode as lifecycle_mode, publish, ensure_bridge
    was_stopped = lifecycle_mode() == 'stopped'
    publish('running')
    ensure_bridge()
    if was_stopped:
        time.sleep(1.6)
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    BLOCKLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        server = ThreadingHTTPServer(('127.0.0.1',LOCAL_EXTENSION_PORT),ExtensionEventHandler)
    except OSError:
        print(f'포트 {LOCAL_EXTENSION_PORT} 사용 중: 기존 Agent 또는 테스트 서버를 종료하세요.',flush=True)
        return 1
    # Offline start also reapplies the last saved central policy before the first network sync.
    apply_saved_policy()
    threading.Thread(target=server.serve_forever,daemon=True).start()
    threading.Thread(target=policy_sync_loop,daemon=True).start()
    clipboard_watch.start(recognize_image, base_event, send_to_railway)
    print(f'GIGANG Agent {VERSION}\nPC: {PC_NAME}\n로컬 IP: {get_local_ip()}\n로컬 상태 API: 127.0.0.1:{LOCAL_EXTENSION_PORT}',flush=True)
    print(f'Windows 직접 차단: 사용 (Chrome 확장자 불필요)', flush=True)
    print(f'중앙 차단 정책 동기화: {POLICY_URL} (약 {POLICY_SYNC_SECONDS}초 간격)', flush=True)
    known = get_domains()
    try:
        while True:
            current = get_domains()
            for domain in sorted(current-known):
                if domain != SERVER_DOMAIN:
                    event = base_event('WEB_ACCESS',domain)
                    event['source']='windows-agent'
                    send_to_railway(event)
            known=current
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
