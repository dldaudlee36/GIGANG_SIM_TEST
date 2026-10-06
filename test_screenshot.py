"""Agent 기밀 DB 스크린샷 감지(SCREEN_CAPTURE) 테스트

실행:  python test_screenshot.py
 - Railway로 실제 전송하지 않는다. (send_to_railway 를 가짜로 바꿔 보낸 내용만 모은다)
 - 실제 캡처 단축키는 누르지 않는다. 단축키 판단과 '누른 순간' 기록은 함수를 직접 불러 시험하고,
   클립보드에는 빈 이미지를 넣어 캡처가 들어온 것처럼 만든다. 끝나면 원래 글자로 되돌린다.
"""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'source', 'agent'))
sys.path.insert(0, ROOT)

import agent

DB = 'desktop-oli.tail2bbbea.ts.net'
agent.CONFIDENTIAL_URLS = [DB]
fail = 0


def check(name, ok, detail=''):
    global fail
    if not ok:
        fail += 1
    print(f"{'OK  ' if ok else 'FAIL'} {name}" + ('' if ok else f'   {detail}'))


def powershell(script, **env):
    subprocess.run(['powershell', '-NoProfile', '-STA', '-Command', script],
                   env={**os.environ, **env}, check=True)


def set_clipboard_image(width, height):
    powershell('Add-Type -AssemblyName System.Windows.Forms, System.Drawing; '
               f'[System.Windows.Forms.Clipboard]::SetImage((New-Object System.Drawing.Bitmap {width}, {height}))')


def set_clipboard_text(text):
    powershell('Set-Clipboard -Value $env:GIGANG_CLIP', GIGANG_CLIP=text)


def get_clipboard_text():
    if not agent.open_clipboard():
        return None
    try:
        data = agent.clipboard_bytes(agent.CF_UNICODETEXT)
        return data.decode('utf-16-le', 'ignore').split('\x00', 1)[0] if data else None
    finally:
        agent.user32.CloseClipboard()


def reset():
    agent.PENDING_CAPTURE = None
    agent._last_shortcut = (None, 0.0)


print('=== 캡처 단축키 판단 ===')
def held(*keys):
    return lambda vk: vk in keys
check('PrtSc', agent.capture_shortcut(agent.VK_SNAPSHOT, True, held()) == 'PrtSc')
check('PrtSc 뗌 신호만 와도', agent.capture_shortcut(agent.VK_SNAPSHOT, False, held()) == 'PrtSc')
check('Alt+PrtSc', agent.capture_shortcut(agent.VK_SNAPSHOT, True, held(agent.VK_MENU)) == 'Alt+PrtSc')
check('Win+Shift+S', agent.capture_shortcut(agent.VK_S, True, held(agent.VK_LWIN, agent.VK_SHIFT)) == 'Win+Shift+S')
check('오른쪽 Win+Shift+S', agent.capture_shortcut(agent.VK_S, True, held(agent.VK_RWIN, agent.VK_SHIFT)) == 'Win+Shift+S')
check('Shift+S (대문자 S) 는 아님', agent.capture_shortcut(agent.VK_S, True, held(agent.VK_SHIFT)) is None)
check('Win+S (검색) 는 아님', agent.capture_shortcut(agent.VK_S, True, held(agent.VK_LWIN)) is None)
check('일반 키는 아님', agent.capture_shortcut(0x41, True, held(agent.VK_SHIFT)) is None)

print('\n=== 확장 → Agent 탭 주소 (/active-tab) ===')
server = ThreadingHTTPServer(('127.0.0.1', 0), agent.ExtensionEventHandler)
threading.Thread(target=server.serve_forever, daemon=True).start()
port = server.server_address[1]


def post_tab(body):
    request = urllib.request.Request(f'http://127.0.0.1:{port}/active-tab', data=body,
                                     headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


check('기밀 DB 탭', post_tab(json.dumps({'url': f'https://{DB}/customers'}).encode()) == 200
      and agent.ACTIVE_TAB['source'] == DB, agent.ACTIVE_TAB)
check('다른 탭', post_tab(json.dumps({'url': 'https://mail.google.com/'}).encode()) == 200
      and agent.ACTIVE_TAB['source'] is None, agent.ACTIVE_TAB)
check('빈 주소 (chrome:// 등)', post_tab(json.dumps({'url': ''}).encode()) == 200
      and agent.ACTIVE_TAB['source'] is None, agent.ACTIVE_TAB)
check('형식 틀림 → 400', post_tab(b'{"url": 3}') == 400)
check('JSON 아님 → 400', post_tab(b'not json') == 400)
server.shutdown()

print('\n=== 단축키를 누른 순간의 화면 판단 ===')
foreground = {'value': 'chrome.exe'}
agent.foreground_process = lambda: foreground['value']

agent.ACTIVE_TAB['source'] = DB
reset(); agent.note_capture('Win+Shift+S')
check('브라우저 + 기밀 DB 탭 → 대기', agent.PENDING_CAPTURE and agent.PENDING_CAPTURE[:2] == (DB, 'Win+Shift+S'),
      agent.PENDING_CAPTURE)
foreground['value'] = 'notepad.exe'
reset(); agent.note_capture('PrtSc')
check('메모장이 맨 앞 → 대기 없음', agent.PENDING_CAPTURE is None, agent.PENDING_CAPTURE)
foreground['value'] = 'msedge.exe'
agent.ACTIVE_TAB['source'] = None
reset(); agent.note_capture('PrtSc')
check('브라우저 + 다른 탭 → 대기 없음', agent.PENDING_CAPTURE is None, agent.PENDING_CAPTURE)

print('\n=== 실제 클립보드 ===')
original = get_clipboard_text()
sent = []
agent.send_to_railway = lambda e: sent.append(e) or True
foreground['value'] = 'chrome.exe'
agent.ACTIVE_TAB['source'] = DB
stop = threading.Event()
threading.Thread(target=agent.watch_clipboard, args=(stop,), daemon=True).start()
try:
    time.sleep(0.5)
    reset(); agent.note_capture('Win+Shift+S')
    set_clipboard_image(320, 200)
    time.sleep(1.5)
    check('기밀 DB 캡처 → 1건 전송', len(sent) == 1, f'{len(sent)}건')
    if sent:
        e = sent[0]
        check('이벤트 내용', (e['event_type'], e['target'], e['shortcut'], e['image_width'], e['image_height'])
              == ('SCREEN_CAPTURE', DB, 'Win+Shift+S', 320, 200), e)
        check('이미지·주소 미포함', set(e) == {'user', 'pc_name', 'local_ip', 'event_type', 'target', 'agent_version',
                                         'source', 'shortcut', 'image_width', 'image_height'}, sorted(e))
    check('보낸 뒤 대기 해제', agent.PENDING_CAPTURE is None, agent.PENDING_CAPTURE)

    reset()
    set_clipboard_image(100, 100)
    time.sleep(1.5)
    check('단축키 없이 들어온 이미지 → 전송 안 함', len(sent) == 1, f'{len(sent)}건')

    reset(); agent.note_capture('PrtSc')
    set_clipboard_text('메모 붙여넣기')
    time.sleep(1.5)
    check('캡처 대신 글자가 들어옴 → 전송 안 함, 계속 대기', len(sent) == 1 and agent.PENDING_CAPTURE is not None,
          f'{len(sent)}건, 대기={agent.PENDING_CAPTURE}')

    agent.PENDING_CAPTURE = (DB, 'PrtSc', time.monotonic() - 1)
    set_clipboard_image(100, 100)
    time.sleep(1.5)
    check(f'{agent.CAPTURE_WAIT_SECONDS}초 지난 뒤 이미지 → 전송 안 함', len(sent) == 1, f'{len(sent)}건')
finally:
    stop.set()
    if original:
        set_clipboard_text(original)

print('\n=== 키보드 후크 설치 ===')
hook_thread = threading.Thread(target=agent.watch_capture_keys, daemon=True)
hook_thread.start()
time.sleep(0.5)
check('후크 설치 후 대기 중 (실패하면 바로 끝남)', hook_thread.is_alive())

print('\n=== 대시보드 변환 (WEB_ACCESS 로 잘못 잡히지 않는지) ===')
try:
    from gigang.collectors import team_collector
except ImportError as error:
    print(f'SKIP 대시보드 모듈을 불러올 수 없음: {error}')
else:
    team_collector.fetch_railway_events = lambda: [
        {'id': 1, 'event_time': '2026-10-05T10:00:00', 'user_name': 'kim', 'event_type': 'SCREEN_CAPTURE',
         'source': 'windows-agent', 'target': DB,
         'raw_data': json.dumps({'shortcut': 'PrtSc', 'image_width': 1920, 'image_height': 1080})},
        {'id': 2, 'event_time': '2026-10-05T10:01:00', 'user_name': 'kim', 'event_type': 'WEB_ACCESS',
         'source': 'windows-agent', 'target': 'chatgpt.com'},
    ]
    team_collector.fetch_remote_db_logs = lambda: []
    team_collector.fetch_activity_log_events = lambda: []
    converted = {e.target.domain: e for e in team_collector.get_team_security_events()}
    capture = converted.get(DB)
    check('SCREEN_CAPTURE → 캡처 이벤트 (WEB_ACCESS 아님)', capture is not None and capture.action.value == 'SCREEN_CAPTURE',
          capture and capture.action)
    check('단축키·크기 전달', capture is not None and (capture.payload.extra['shortcut'], capture.payload.extra['image_width'])
          == ('PrtSc', 1920), capture and capture.payload.extra)
    check('기존 WEB_ACCESS 는 그대로', 'chatgpt.com' in converted and converted['chatgpt.com'].action.value == 'WEB_ACCESS',
          list(converted))

print('\n전체 PASS' if fail == 0 else f'\n실패 {fail}건')
sys.exit(1 if fail else 0)
