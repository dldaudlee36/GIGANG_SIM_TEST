# GIGANG Upload & Paste Sensor

이 크롬 확장은 **사이트 차단을 하지 않습니다.**
차단은 `USER_START.bat`으로 실행되는 Windows Agent가 중앙 정책을 받아 Windows `hosts`에 적용합니다.

확장의 역할은 두 가지뿐입니다.

1. 파일 선택 시도 → `FILE_UPLOAD_ATTEMPT`
2. 텍스트 붙여넣기 → `PASTE_ATTEMPT`

파일 내용이나 붙여넣은 텍스트 원문은 보내지 않습니다. 파일 이름·크기, 붙여넣기 글자 수, 대상 도메인, 시각 같은 메타데이터만 로컬 Agent(`127.0.0.1:8765`)로 전달합니다.

## 설치

1. 먼저 `USER_START.bat` 실행
2. Chrome에서 `chrome://extensions` 열기
3. 개발자 모드 켜기
4. `압축해제된 확장 프로그램을 로드` 클릭
5. 이 `browser_extension` 폴더 선택
6. 감지할 사이트 탭 새로고침

## 확인

- 파일을 선택하면 개발자 콘솔에 `[GIGANG] FILE_UPLOAD_ATTEMPT`
- 텍스트를 붙여넣으면 `[GIGANG] PASTE_ATTEMPT`
- 확장 아이콘을 누르면 Agent 연결과 마지막 감지 결과 확인

## 역할 분리

- **Windows Agent:** 중앙 차단 정책 동기화 + 실제 사이트 차단 + WEB_ACCESS 수집
- **Chrome 확장:** 파일 선택/붙여넣기 메타데이터 감지 전용
- **관리자 대시보드:** 중앙 정책 관리

## 한계

- 일반적인 `<input type="file">` 파일 선택을 감지합니다.
- 드래그앤드롭 업로드는 현재 감지 대상이 아닙니다.
- 파일을 실제 서버에 전송 완료했는지가 아니라 **파일을 선택한 시점의 시도**를 기록합니다.
- 비밀번호 입력칸의 붙여넣기는 수집하지 않습니다.
