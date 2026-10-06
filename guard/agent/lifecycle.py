"""Read-only loopback status bridge. Only elevated START/STOP writes the mode file."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import urlopen

PORT = 8766
STATE = Path(os.environ.get('ProgramData', r'C:\ProgramData'))/'GIGANG'/'lifecycle.json'


def mode():
    try:
        value = json.loads(STATE.read_text(encoding='utf-8'))
        return 'stopped' if value.get('mode') == 'stopped' else 'running'
    except (OSError, ValueError):
        return 'running'  # A missing/broken marker never authorizes a bypass.


def publish(value):
    if value not in ('running', 'stopped'):
        raise ValueError('Invalid mode')
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE.with_name(f'lifecycle-{os.getpid()}.tmp')
    temporary.write_text(json.dumps({'mode':value}), encoding='utf-8')
    os.replace(temporary, STATE)


def ensure_bridge():
    def ready():
        try:
            with urlopen(f'http://127.0.0.1:{PORT}/mode', timeout=1) as response:
                return json.load(response).get('service') == 'GIGANGLifecycle'
        except Exception:
            return False
    if ready():
        return
    subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--serve'],
                     creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(20):
        if ready():
            return
        time.sleep(.1)
    raise RuntimeError('Extension status service could not start on port 8766.')


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/mode':
            self.send_error(404)
            return
        body=json.dumps({'service':'GIGANGLifecycle','mode':mode()}).encode()
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self,*args):
        pass


if __name__ == '__main__' and '--serve' in sys.argv:
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
