> 💡 **Notion 활용 팁**: 전체 복사(Ctrl + A ➔ Ctrl + C) 후 노션에 붙여넣기(Ctrl + V)하면 최적의 서식으로 자동 변환됩니다.

---

# 3. <1차 공식 회의> 역할 분담, WBS 및 주차별 로드맵

### 📌 회의 개요
| 항목 | 내용 |
| :--- | :--- |
| **일시** | 2026년 8월 25일 (월) 10:00 ~ 13:00 |
| **장소** | 캡스톤 연구실 세미나룸 |
| **참석자** | 팀원 전원 (4명) |
| **회의 목적** | 공통 데이터 표준 스키마 합의, 4인 전원 첫날 병렬 개발을 위한 R&R 확정 및 6주 WBS 수립 |
| **진행 상태** | `[완료]` 공통 스키마 배포 및 주차별 마일스톤 확정 |

---

### 3.1 공통 데이터 표준 스키마 (`Unified JSON`) 규격 합의

서로 다른 모듈 개발자가 상대방의 작업 완료를 기다리지 않고 첫날(Day 1)부터 더미 데이터를 이용해 독립적으로 개발할 수 있도록 단일 표준 스키마를 확정했습니다.

```json
{
  "event_id": "EVT-20260904-00108",
  "timestamp": "2026-09-04T10:05:33Z",
  "log_source": "dns | auth | firewall | db | web | windows-agent",
  "actor": {
    "user_id": "kim_marketing",
    "src_ip": "192.168.10.45",
    "src_port": 53120
  },
  "target": {
    "dst_ip": "10.0.3.50",
    "dst_port": 3306,
    "domain": "chatgpt.com",
    "hostname": "DESKTOP-OF0CMDB"
  },
  "action": "LOGIN_FAIL | LOGIN_SUCCESS | SELECT | WEB_ACCESS | FILE_UPLOAD_ATTEMPT",
  "payload": {
    "query_string": "SELECT * FROM customer_vault",
    "bytes_sent": 48291040,
    "file_name": "customer_summary.zip"
  }
}
```

---

### 3.2 4인 팀원 역할 분담 (R&R) — 병목 없는 병렬 개발

| 담당 파트 | 주요 업무 범위 | 세부 개발 태스크 |
| :--- | :--- | :--- |
| **① 인프라 & 실시간 수집** | 수집 파이프라인 및 에이전트 | • Railway 클라우드 중앙 수집 서버(Flask + PostgreSQL) 구축<br>• Windows 엔드포인트 에이전트(`GIGANGAgent.exe`) 패키징<br>• Chrome 브라우저 확장 프로그램(`Upload Detector`) 개발 |
| **② 파서 & 데이터 전처리** | 이기종 로그 정규화 | • DNS, Syslog, Apache Web, MySQL Audit 로그 파서 모듈화<br>• 비정형 텍스트 로그를 `Unified JSON` 표준 포맷으로 실시간 변환<br>• 예외/결측 로그 방어 처리 |
| **③ 상관분석 & AI 엔진** | 위협 탐지 및 인텔리전스 | • 듀얼 상관분석 엔진(외부 침투 피보팅 + 내부 AI 유출) 구현<br>• 슬라이딩 윈도우 스코어링 알고리즘 및 TTL 자가치유 타이머<br>• Google Gemini LLM API 연동 (도메인 분석 및 조치 소견 도출) |
| **④ 대시보드 & SOAR** | 통합 보안 관제 UI | • Streamlit 다크 테마 관제 대시보드 풀스크린 구축<br>• 네트워크 토폴로지 맵 시각화 및 킬체인 타임라인 렌더링<br>• AI 거버넌스 양성화 관리 센터 및 Slack 알림 웹훅 연동 |

---

### 3.3 6주차 상세 WBS 로드맵 (3주차 MVP)

```
[1주차] 기획 확정 + 공통 스키마 정의 + Mock 대시보드 (화면 먼저 띄우기)
   ↓
[2주차] 인프라 구축 + Railway 수집 서버 + Windows Agent 연동 + 파서 개발
   ↓
[3주차 (MVP)] 실시간 수집 + 듀얼 상관분석 E2E 관통 (실제 화면에 사건 자동 생성)
   ↓
[4주차] 대시보드 고도화 + 네트워크 토폴로지 맵 + Gemini AI 진단기 통합
   ↓
[5주차] SOAR 원클릭 긴급 대응 + AI 거버넌스 양성화 워크플로 + UI 반응형 최적화
   ↓
[6주차] 실환경 모의 침투 종합 테스트 + 최종 시연 영상 촬영 + 최종 발표
```

* **3주차 MVP의 핵심 목표**:
  * 단말 에이전트와 DB 감사 로그가 Railway에 수집되어, 상관분석 엔진을 거쳐 **외부 침투 Incident 1건**과 **김대리 AI 유출 Incident 1건**이 웹 화면에 자동으로 생성되는 End-to-End 전체 파이프라인 완성.

---

### 3.4 회의 결정 사항 및 즉시 실천 과제 (Action Items)
- [x] GitHub 저장소(`GIGANG`) 생성 및 기본 폴더 구조 배포
- [x] Python 가상환경 의존성(`requirements.txt`) 초기화
- [x] 1주차 프로토타입 UI 골격 제작 및 각자 PC 실행 테스트
- [x] Google Gemini API 발급 및 환경변수(`.env`) 세팅 가이드 배포

---
