# GIGANG 프로젝트 인수인계 및 작업 연속 가이드 (Handoff Prompt)

> **💡 다른 컴퓨터의 Antigravity에서 사용하는 방법**
> 1. 다른 컴퓨터에서 Git 최신 코드를 pull 받거나 폴더를 엽니다.
> 2. Antigravity 채팅창에 **"GIGANG_Handoff_Prompt.md 읽고 작업을 이어서 진행해줘"** 라고 한 줄만 입력하면, AI가 이 문서를 읽고 즉시 모든 맥락을 이어받습니다.
> 3. 또는 아래 프롬프트 본문을 그대로 복사하여 채팅창에 붙여넣으셔도 완벽하게 동작합니다.

---

## 📋 [Antigravity 프롬프트 본문]

먼저 GitHub 원격 저장소의 최신 변경 사항을 확인하고 로컬 파일을 업데이트해줘.
현재 작업 폴더(또는 `gigang_sim_test`)에서 `git pull`을 실행하여 최신 커밋 상태로 동기화하고, 누락된 의존성(`pip install -r requirements.txt`)이나 충돌 여부를 점검해줘.

동기화가 끝나면 아래의 프로젝트 컨텍스트와 직전 작업 내역을 숙지한 뒤 인수인계 상태를 확인해줘.

---

### [프로젝트 기본 정보]
- **프로젝트명**: GIGANG (기강, 구 NexusGuard에서 전면 변경됨)
- **저장소**: https://github.com/dldaudlee36/gigang_sim_test.git
- **핵심 목표**: Zero Trust 기반 엔드포인트-DB-웹 상관분석 보안 관제 플랫폼
  - 내부 DB 대량/민감 조회 행위 발생 후, 외부 생성형 AI 사이트(ChatGPT, Claude 등)로의 데이터 유출(복사·붙여넣기, 파일 업로드 등) 킬체인을 상태 머신(FSM)과 Gemini LLM 거버넌스 평가를 결합하여 실시간 탐지/차단

### [시스템 아키텍처 및 핵심 구성요소]
1. **GIGANG 단말 에이전트** (`guard/agent/agent.py`):
   - 로컬 포트 `8765`에서 백그라운드 구동, 브라우저 확장 프로그램 및 엔드포인트 이벤트 수집
2. **관제 대시보드** (`app.py`):
   - Streamlit 기반 웹 대시보드 (포트 `8501`)
   - 실시간 위협 모니터링, FSM 킬체인 시각화, 로그 분석 및 인시던트 관리
3. **상관분석 및 거버넌스 엔진** (`gigang/engine/`):
   - `correlation.py`: 이벤트 상관분석 및 위협 레벨 산출
   - `governance.py`: Gemini 기반 사이트 위험도 및 데이터 유출 평가
4. **원클릭 런처**:
   - `start_all.bat`: 에이전트(8765) + 대시보드(8501) 백그라운드 구동 및 브라우저 자동 실행
   - `stop_all.bat`: 8501, 8765 점유 프로세스 일괄 정상 종료

---

### [직전 세션에서 완료된 작업 내역]
1. **저장소 및 파일 전면 동기화**:
   - `gigang_sim_test` 최신 main 브랜치 클론 및 코드베이스 반영
2. **프로젝트 명칭 100% 교체 완료 ("NexusGuard" ➔ "GIGANG")**:
   - 파이썬 패키지 디렉토리(`nexusguard/` ➔ `gigang/`) 및 모든 내부 `import` 구문 변경
   - 프롬프트 식별자(`Aegis-GenAI` ➔ `GIGANG-GenAI`) 및 UI 텍스트, 문서 일괄 수정
   - 레거시 호환용 별칭 제거 및 0건 잔존 검증 완료
3. **검증 테스트 통과**:
   - `python test_dedup.py` (PASS)
   - `python test_paste.py` (PASS)
   - `python run_demo.py` (PASS, 20개 모의 이벤트 시나리오 무오류 완주)
4. **로컬 실행 스크립트 작성**:
   - `start_all.bat` 및 `stop_all.bat` (경로 이스케이프 버그 수정 및 브라우저 자동 오픈 탑재)
5. **긴급 회의 피드백 문서 정리**:
   - `docs/GIGANG_Emergency_Meeting_Feedback.md` (팀 회의 결과, 오해 정정, DB 로그 연계 방안 정리)

---

### [현재 진행할 작업 및 확인 요청]
1. 저장소 최신화(`git pull` 등) 상태 및 파일 무결성 확인
2. `start_all.bat` 및 주요 파이썬 모듈(`guard/agent/agent.py`, `app.py`)의 구동 환경 정상 여부 점검
3. 확인이 완료되면 현재 상태를 간략히 요약하고, 다음 작업(회의 피드백 반영, 시나리오 고도화 등)에 대해 안내해줘.
