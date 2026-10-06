const params = new URLSearchParams(location.search);
document.getElementById('site').textContent = params.get('site') || '';
const matched = params.get('reason') === 'matched';
const imageBlocked = params.get('reason') === 'image_blocked';
document.getElementById('title').textContent = imageBlocked ? '사내 자료 외부 전송 차단' : matched ? '사내 자료 외부 입력 감지' : '관리자 정책으로 제한된 사이트';
document.getElementById('reason').textContent = imageBlocked
    ? '보안 정책에 따라 이미지 붙여넣기 또는 업로드가 차단되었습니다.'
    : matched
    ? '사내 DB 자료와 같은 내용의 붙여넣기 또는 파일 선택이 감지되어 이 탭을 보안 안내 화면으로 전환했습니다.'
    : '관리자가 차단 목록에 등록한 사이트입니다. 사이트 이용이 제한됩니다.';
document.getElementById('detail').textContent = imageBlocked
    ? '요청한 이미지 첨부는 허용되지 않습니다.'
    : matched
    ? '감지 후 화면 전환입니다. 이미 페이지에 전달된 내용이나 시작된 업로드의 취소를 보장하지 않습니다. 기록 저장 여부는 확장 팝업에서 확인하세요.'
    : 'Agent의 중앙 차단 정책을 기준으로 표시합니다. 연결이 끊기면 마지막으로 받은 정책을 사용합니다.';
document.getElementById('close').addEventListener('click', () => window.close());
