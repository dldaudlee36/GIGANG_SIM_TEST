"""Agent 기밀 DB 복사 감지(CLIPBOARD_COPY) 연결 테스트

실행:  python test_clipboard.py
 - Railway로 실제 전송하지 않는다. (send_to_railway 를 가짜로 바꿔 보낸 내용만 모은다)
 - 테스트 중에 클립보드 내용이 바뀐다. 끝나면 원래 글자로 되돌린다.
 - 기밀 DB 주소는 테스트용 값(http://10.0.0.30:8080/vault)을 쓴다.
"""
import json
import os
import subprocess
import sys
import threading
import time
import types

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'source', 'agent'))
sys.path.insert(0, ROOT)

try:
    import requests  # noqa: F401
except ImportError:
    # requests 가 없어도 Agent 함수는 시험할 수 있게 빈 모듈을 끼워 둔다
    sys.modules['requests'] = types.SimpleNamespace(RequestException=Exception, post=None)

import agent

DB_URL = 'http://10.0.0.30:8080/vault'
agent.CONFIDENTIAL_URLS = [DB_URL, 'db.gigang.local']
fail = 0


def check(name, ok, detail=''):
    global fail
    if not ok:
        fail += 1
    print(f"{'OK  ' if ok else 'FAIL'} {name}" + ('' if ok else f'   {detail}'))


# 브라우저에서 복사한 것처럼 글자 + HTML(SourceURL 포함)을 함께 넣는다. url 이 없으면 메모장 복사처럼 글자만.
# 한글이 깨지지 않게 값은 환경변수로 넘긴다.
_SET_CLIPBOARD = r'''
Add-Type -AssemblyName System.Windows.Forms
$data = New-Object System.Windows.Forms.DataObject
$data.SetData([System.Windows.Forms.DataFormats]::UnicodeText, $env:GIGANG_CLIP)
if ($env:GIGANG_URL) {
    $html = "Version:0.9`r`nStartHTML:-1`r`nEndHTML:-1`r`nStartFragment:-1`r`nEndFragment:-1`r`nSourceURL:$env:GIGANG_URL`r`n<html><body>table</body></html>"
    $data.SetData([System.Windows.Forms.DataFormats]::Html, $html)
}
[System.Windows.Forms.Clipboard]::SetDataObject($data, $true)
'''


def set_clipboard(text, url=''):
    subprocess.run(['powershell', '-NoProfile', '-STA', '-Command', _SET_CLIPBOARD],
                   env={**os.environ, 'GIGANG_CLIP': text, 'GIGANG_URL': url}, check=True)


def get_clipboard_text():
    if not agent.open_clipboard():
        return None
    try:
        data = agent.clipboard_bytes(agent.CF_UNICODETEXT)
        return data.decode('utf-16-le', 'ignore').split('\x00', 1)[0] if data else None
    finally:
        agent.user32.CloseClipboard()


SAMPLE = '홍길동 900101-1234568 010-1234-5678\n김영희 880315-2345670 kim@corp.co.kr'

print('=== 주소 판단 ===')
check('기밀 DB 페이지', agent.confidential_source(DB_URL + '/customers?id=17') == DB_URL)
check('https·대소문자 무시', agent.confidential_source('HTTPS://10.0.0.30:8080/Vault/') == DB_URL)
check('호스트만 적은 항목', agent.confidential_source('https://db.gigang.local/salary') == 'db.gigang.local')
check('비슷한 경로는 제외', agent.confidential_source('http://10.0.0.30:8080/vault2') is None)
check('비슷한 호스트는 제외', agent.confidential_source('https://db.gigang.local.evil.com/') is None)
check('다른 사이트', agent.confidential_source('https://mail.google.com/') is None)
check('주소 없음', agent.confidential_source(None) is None)

print('\n=== SourceURL 꺼내기 ===')
header = b'Version:0.9\r\nStartHTML:0000000105\r\nSourceURL:http://10.0.0.30:8080/vault/c\r\n<html>SourceURL:http://fake</html>'
check('머리말에서만 꺼냄', agent.source_url(header) == 'http://10.0.0.30:8080/vault/c', agent.source_url(header))
check('HTML 없음', agent.source_url(None) is None)

print('\n=== 보내는 내용 ===')
event = agent.clipboard_event(SAMPLE, DB_URL)
hits = event['pattern_hits']
check('이벤트 종류', event['event_type'] == 'CLIPBOARD_COPY', event['event_type'])
check('대상 = 목록 값', event['target'] == DB_URL, event['target'])
check('글자 수', event['text_length'] == len(SAMPLE), event['text_length'])
check('규칙 건수', (hits['rrn'], hits['rrn_high'], hits['phone'], hits['email']) == (2, 2, 1, 1), hits)
body = json.dumps(event, ensure_ascii=False)
check('원문 미포함', not any(part in body for part in ('홍길동', '900101', '010-1234', 'kim@corp')), body)

print('\n=== 실제 클립보드 ===')
original = get_clipboard_text()
sent = []
agent.send_to_railway = lambda e: sent.append(e) or True
stop = threading.Event()
threading.Thread(target=agent.watch_clipboard, args=(stop,), daemon=True).start()
try:
    time.sleep(0.5)
    set_clipboard(SAMPLE, DB_URL + '/customers?id=17')
    time.sleep(1.5)
    check('기밀 DB 페이지에서 복사 → 1건 전송', len(sent) == 1, f'{len(sent)}건')
    if sent:
        check('전송 대상·건수', (sent[0]['target'], sent[0]['pattern_hits']['rrn']) == (DB_URL, 2),
              (sent[0]['target'], sent[0]['pattern_hits']))
        check('주소의 고객번호 미포함', 'id=17' not in json.dumps(sent[0]), sent[0])

    set_clipboard('메일 본문 010-9999-8888', 'https://mail.google.com/')
    time.sleep(1.5)
    check('다른 사이트에서 복사 → 전송 안 함', len(sent) == 1, f'{len(sent)}건')

    set_clipboard('메모장 900101-1234568')
    time.sleep(1.5)
    check('주소 없는 복사(메모장) → 전송 안 함', len(sent) == 1, f'{len(sent)}건')
finally:
    stop.set()
    if original:
        set_clipboard(original)

print('\n=== 대시보드 변환 (WEB_ACCESS 로 잘못 잡히지 않는지) ===')
try:
    from gigang.collectors import team_collector
except ImportError as error:
    print(f'SKIP 대시보드 모듈을 불러올 수 없음: {error}')
else:
    team_collector.fetch_railway_events = lambda: [
        {'id': 1, 'event_time': '2026-10-05T10:00:00', 'user_name': 'kim', 'event_type': 'CLIPBOARD_COPY',
         'source': 'windows-agent', 'target': DB_URL, 'pattern_hits': hits},
        {'id': 2, 'event_time': '2026-10-05T10:01:00', 'user_name': 'kim', 'event_type': 'WEB_ACCESS',
         'source': 'windows-agent', 'target': 'chatgpt.com'},
    ]
    team_collector.fetch_remote_db_logs = lambda: []
    team_collector.fetch_activity_log_events = lambda: []
    converted = {e.target.domain: e for e in team_collector.get_team_security_events()}
    copy = converted.get(DB_URL)
    check('CLIPBOARD_COPY → 복사 이벤트 (WEB_ACCESS 아님)', copy is not None and copy.action.value == 'CLIPBOARD_COPY',
          copy and copy.action)
    check('규칙 건수 전달', copy is not None and copy.payload.extra['pattern_hits'] == hits, copy and copy.payload.extra)
    check('기존 WEB_ACCESS 는 그대로', 'chatgpt.com' in converted and converted['chatgpt.com'].action.value == 'WEB_ACCESS',
          list(converted))

print('\n전체 PASS' if fail == 0 else f'\n실패 {fail}건')
sys.exit(1 if fail else 0)
