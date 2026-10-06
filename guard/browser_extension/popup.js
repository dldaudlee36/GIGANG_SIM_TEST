const element = id => document.getElementById(id);
const failures = {
    AGENT_UNREACHABLE: 'Agent에 연결하지 못했습니다. USER_START.bat을 실행하세요.',
    HTTP_502: 'Agent는 받았지만 Railway 저장에 실패했습니다. 인터넷 연결을 확인하세요.',
    HTTP_400: '이벤트 형식이 맞지 않습니다. 확장과 Agent 버전을 확인하세요.',
    HTTP_404: '이전 Agent가 실행 중일 수 있습니다. USER_START를 다시 실행하세요.',
    TIMEOUT: '전송 시간이 초과됐습니다.',
    INVALID_AGENT_RESPONSE: '다른 프로그램이 연결 포트를 사용 중입니다.'
};

function renderRecord(kind, record, statusId, detailsId) {
    const status = element(statusId);
    const details = element(detailsId);
    if (!record) {
        status.textContent = '아직 감지 기록이 없습니다.';
        status.className = '';
        details.textContent = '';
        return;
    }
    status.textContent = record.status === 'saved' ? 'Railway 서버 저장 완료' : failures[record.error] || `전송 실패 (${record.error})`;
    status.className = record.status === 'saved' ? 'ok' : 'failed';
    const labels={matched:'사내 자료와 내용 일치',no_match:'일치 기록 없음',not_checked:'내용 비교 안 됨',source_recorded:'비교용 출처 기록됨',internal_destination:'사내 사이트 입력'};
    status.textContent += ' · ' + (labels[record.match_status] || '');
    if(record.match)status.textContent += ` · 출처 ${record.match.source_domain}${record.match.source_path}`;
    if (kind === 'download') {
        details.textContent = `${record.target} · ${record.file_name || '파일'} · ${{DOWNLOAD_STARTED:'시작',DOWNLOAD_COMPLETED:'완료',DOWNLOAD_INTERRUPTED:'중단'}[record.event_type]} · ${new Date(record.timestamp).toLocaleString('ko-KR')}`;
    } else if (kind === 'copy') {
        details.textContent = `${record.target} · ${new Date(record.timestamp).toLocaleString('ko-KR')}`;
    } else if (kind === 'paste') {
        details.textContent = `${record.target} · ${record.text_length}자 · ${new Date(record.timestamp).toLocaleString('ko-KR')}`;
    } else {
        details.textContent = `${record.target} · ${record.file_name} · ${record.file_size} bytes · ${new Date(record.timestamp).toLocaleString('ko-KR')}`;
    }
}

async function refresh() {
    element('refresh').disabled = true;
    try {
        const status = await chrome.runtime.sendMessage({type: 'GIGANG_STATUS'});
        if (!status || status.error) throw new Error('EXTENSION_ERROR');
        element('version').textContent = `확장 ${status.version} · 이미지 첨부 전 검사`;
        element('agent').textContent = status.agent.ok ? `연결됨 · Agent ${status.agent.version}` : '연결 안 됨 · USER_START.bat을 실행하세요.';
        element('agent').className = status.agent.ok ? 'ok' : 'failed';
        const policy = element('policy');
        if (status.agent.ok) {
            policy.textContent = status.agent.windowsBlockingOk === false ?
                `Agent 연결됨 · Windows 차단 적용 실패` :
                `Agent가 Windows 차단 담당 · 중앙 정책 ${status.agent.blockedCount || 0}개`;
            policy.className = status.agent.windowsBlockingOk === false ? 'failed' : 'ok';
        } else {
            policy.textContent = 'Agent가 꺼져 있어 차단 상태를 확인할 수 없습니다.';
            policy.className = 'failed';
        }
        renderRecord('upload', status.lastUpload, 'upload', 'uploadDetails');
        renderRecord('download', status.lastDownload, 'download', 'downloadDetails');
        renderRecord('copy', status.lastCopy, 'copy', 'copyDetails');
        renderRecord('paste', status.lastPaste, 'paste', 'pasteDetails');
        const img=status.lastImage;
        element('image').textContent=img ? ({blocked_match:'보안 정책에 따라 이미지 첨부 차단',held_error:'보안 확인 미완료 · 첨부 보류',no_match:'보안 확인 완료'}[img.outcome]||'상태 확인 필요') : '아직 이미지 검사 기록이 없습니다.';
        element('image').className=img?.outcome==='blocked_match'||img?.outcome==='held_error'?'failed':'ok';
        element('imageDetails').textContent=img ? `${img.target} · ${{paste:'이미지 붙여넣기',file:'이미지 업로드',drop:'이미지 드래그 첨부'}[img.channel]||'이미지 첨부'} · ${new Date(img.timestamp).toLocaleString('ko-KR')}` : '';
    } catch {
        element('agent').textContent = '확장을 새로고침한 뒤 다시 열어주세요.';
        element('agent').className = 'failed';
    } finally {
        element('refresh').disabled = false;
    }
}
element('refresh').addEventListener('click', refresh);
void refresh();
