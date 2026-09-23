# 🛡️ GIGANG (v2.0)
### Zero Trust 기반 사내 위험행위 상관분석 & Shadow AI 거버넌스 플랫폼

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://gigang-aleph.streamlit.app/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

> **사내 사용자의 외부 서비스 이용 행동(Web/DNS)과 내부 DB·방화벽 로그를 2단계 위험 상태 기계(Risk State Machine)로 연결하여, 데이터 반출 이전 선제 감시(WATCH) 및 실시간 유출(HIGH)을 정확히 판별하는 차세대 SecOps 솔루션**

---

## 📌 핵심 아키텍처 및 2단계 판단 모델

`	ext
[1단계: 사전 감시 (Pre-exfiltration)]
  민감 DB SELECT + 미승인 AI/클라우드 접속
  ➔ 위험 상태 기계: 'WATCH' 상태 승격 (TTL 30분) & 1차 알림 (화면 선제 노출)

[2단계: 유출 확정 (Incident Confirmation)]
  'WATCH' 상태 사용자 외부 데이터 전송 발생
  ➔ 위험 상태: 'HIGH' 인시던트 확정 & 2차 긴급 알림

[자가 치유 안전장치 (Self-Healing)]
  전송 없이 30분 경과 시 ➔ 'NORMAL' 자동 복귀 (오탐 자동 해제)
`

`mermaid
stateDiagram-v2
    [*] --> NORMAL: 기본 정상 상태
    NORMAL --> WATCH: 민감 DB 조회 + 미승인 AI 접속 (1차 사전 알림)
    WATCH --> HIGH: 외부 데이터 전송 발생 (2차 긴급 알림 & Incident 확정)
    WATCH --> NORMAL: 30분 경과 (추가 행동 없음, 오탐 자동 해제)
    HIGH --> CRITICAL: 대용량 / 야간 / 반복 전송 가중
    HIGH --> NORMAL: 24시간 경과 또는 보안관리자 조치 완료
`

---

## 📸 대시보드 화면 미리보기

| 대시보드 종합 관제 (Overview) | 섀도우 AI·IT 거버넌스 (Shadow AI) |
| :---: | :---: |
| ![대시보드 종합 관제](./docs/screenshots/capture_1_overview.png) | ![섀도우 AI 거버넌스](./docs/screenshots/capture_3_shadow_ai.png) |

| 침해사고 킬체인 분석 (Lateral Movement) | 프로젝트 전체 요약 인포그래픽 |
| :---: | :---: |
| ![침해사고 킬체인](./docs/screenshots/capture_2_killchain.png) | ![인포그래픽](./docs/screenshots/project_infographic.png) |

---

## 📖 주요 문서

- [📋 프로젝트 개선 요구사항 명세서 v2.0 (상태 기계 보강 통합안)](./docs/GIGANG_Improvement_Specification_v2.md)
- [📝 원본 Notion 기획 제안서](./GIGANG_Notion_Proposal.md)

---

## 🚀 빠른 시작 가이드

`ash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 대시보드 실행
streamlit run app.py
`
