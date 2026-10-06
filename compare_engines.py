"""기존 엔진(GitHub main 3ee8af7) vs 새 엔진 비교. 사용: python run_compare.py <프로젝트 폴더> <결과 json>
같은 시나리오 로그를 넣고 사용자별 최종 상태·점수·인시던트·근거 규칙을 모은다.
그 버전에 없는 이벤트 종류(CLIPBOARD_COPY 등: 기존엔 Agent 가 안 보냄)는 건너뛴다."""
import json, os, re, sys
from datetime import datetime, timedelta

root, out = sys.argv[1], sys.argv[2]
sys.path.insert(0, root); os.chdir(root)
from gigang.engine.correlation import CorrelationEngine
from gigang.schemas.event import SecurityEvent, LogSource, EventAction, Actor, Target, PayloadMetadata

T0 = datetime(2026, 10, 6, 10, 0)
engine = CorrelationEngine(enable_mock_incidents=False)
engine.store.clear_all()
if hasattr(engine, "policy"):
    engine.policy["users"] = {"hr_normal": "HR", "hr_leak": "HR", "hr_unrel": "HR", "cs_file": "CS",
                              "cs_small": "CS", "no_db": "CS", "no_db_files": "CS"}
seq = iter(range(1, 10000))
skipped = []


def ev(user, minute, action, source="WINDOWS_AGENT", domain="desktop-oli.tail2bbbea.ts.net", **payload):
    if not hasattr(EventAction, action) or not hasattr(LogSource, source):
        skipped.append(f"{user}:{action}")
        return None
    extra = payload.pop("extra", {})
    return SecurityEvent(event_id=f"CMP-{next(seq)}", timestamp=T0 + timedelta(minutes=minute),
                         log_source=getattr(LogSource, source), actor=Actor(user_id=user, src_ip="10.0.0.5"),
                         target=Target(domain=domain, hostname="PC"), action=getattr(EventAction, action),
                         payload=PayloadMetadata(extra=extra, **payload))


def db_select(user, m):      # 기밀 DB 포털 조회 → DB 감사 로그 (기존·새 엔진 모두 받음)
    return ev(user, m, "SELECT", "DB", "gigang_db", table_name="customer_vault",
              query_string="SELECT ... FROM customer_vault LIMIT 50")


def ai(user, m):
    return ev(user, m, "WEB_ACCESS", "WINDOWS_AGENT", "chatgpt.com")


def copy(user, m, hits, length):
    return ev(user, m, "CLIPBOARD_COPY", extra={"pattern_hits": hits, "text_length": length})


def paste(user, m, length):
    return ev(user, m, "PASTE_ATTEMPT", "CHROME_EXTENSION", "chatgpt.com", extra={"text_length": length})


def download(user, m, name, size, hits):
    return ev(user, m, "DB_DOWNLOAD", file_name=name, file_size=size,
              extra={"file_name": name, "file_size": size, "inspectable": True, "pattern_hits": hits, "file_kind": "xlsx"})


def upload(user, m, name, size):
    return ev(user, m, "FILE_UPLOAD_ATTEMPT", "CHROME_EXTENSION", "chatgpt.com", file_name=name, file_size=size)


SCENARIOS = {
    "hr_normal": ("① 정상 복사: 인사가 DB 조회 후 주민번호 5건 복사, AI 탭은 열려 있음, AI 입력 없음",
                  [ai("hr_normal", 0), db_select("hr_normal", 2), copy("hr_normal", 3, {"rrn_high": 5}, 300)]),
    "hr_leak": ("② 기밀 자료 AI 입력: ①과 같이 복사한 뒤 그 내용을 AI 에 붙여넣기",
                [ai("hr_leak", 0), db_select("hr_leak", 2), copy("hr_leak", 3, {"rrn_high": 5}, 300), paste("hr_leak", 5, 300)]),
    "hr_unrel": ("③ 무관한 내용 AI 입력: ①과 같이 업무 복사 후, 자기가 쓴 짧은 글을 AI 에 붙여넣기",
                 [ai("hr_unrel", 0), db_select("hr_unrel", 2), copy("hr_unrel", 3, {"rrn_high": 5}, 300), paste("hr_unrel", 5, 40)]),
    "no_db": ("④ 무관한 내용 AI 입력: DB 를 안 본 사람이 글을 AI 에 붙여넣기",
              [ai("no_db", 0), paste("no_db", 2, 400)]),
    "cs_file": ("⑤ 파일 첨부: 고객지원이 DB 엑셀(전화·이메일 50건) 다운로드 → AI 에 첨부",
                [ai("cs_file", 0), db_select("cs_file", 2), download("cs_file", 3, "gigang_customer_data_cs.xlsx", 8480, {"phone": 50, "email": 50}),
                 upload("cs_file", 5, "gigang_customer_data_cs.xlsx", 8480)]),
    "no_db_files": ("⑥ 무관한 파일 첨부: DB 를 안 본 사람이 자기 파일을 AI 에 두 번 첨부",
                    [ai("no_db_files", 0), upload("no_db_files", 2, "my_resume.pdf", 50000), upload("no_db_files", 4, "photo.png", 90000)]),
    "cs_small": ("⑦ 소량 반복 복사: 고객지원이 전화 4건씩 3번 복사 (합 12건, 평소 10건)",
                 [ai("cs_small", 0), db_select("cs_small", 1), copy("cs_small", 2, {"phone": 4}, 80),
                  copy("cs_small", 4, {"phone": 4}, 80), copy("cs_small", 6, {"phone": 4}, 80)]),
}

for user, (_, events) in SCENARIOS.items():
    # AI 탭을 열어 두면 백그라운드 접속 로그가 몇 분마다 계속 찍힌다 (실측: chatgpt 탭 → cdn.openai.com 등)
    last = max(e.timestamp for e in events if e is not None)
    background = [ai(user, m) for m in range(1, int((last - T0).total_seconds() // 60) + 3, 2)]
    engine.ingest_events(sorted([e for e in events + background if e is not None], key=lambda e: e.timestamp))

result = {}
incidents = engine.store.get_all_incidents()
for user, (desc, _) in SCENARIOS.items():
    risk = engine.store.get_active_risk(user)
    hist = [h for h in engine.store.get_risk_history(limit=1000) if h["user"] == user]
    rules = sorted({r for h in hist for r in re.findall(r"\[((?:COM|CS|HR|FIN|DEV|SS|DL|ZERO)[-\w()]*)\]", h["reason"] or "")})
    result[user] = {"desc": desc, "state": risk["state"] if risk else "NORMAL", "score": risk["score"] if risk else None,
                    "incident": any(f"'{user}'" in (i.title or "") for i in incidents), "rules": rules,
                    "path": [f"{h['from_state']}→{h['to_state']}" for h in hist if h["from_state"] != h["to_state"]]}
result["_skipped"] = skipped
json.dump(result, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("done", out)
