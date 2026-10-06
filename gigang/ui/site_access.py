"""Compact PC/site review panel within the existing pipeline page."""
from datetime import datetime, timezone, timedelta
import hashlib
import math
import requests
import streamlit as st


def render(base, api_key):
    with st.container(border=True):
        st.markdown('### 차단 내역 · 일시 허용 관리')
        st.caption('최근 24시간 · 같은 PC와 사이트의 기록을 묶어 표시합니다. 허용은 해당 PC의 사이트 전체에 적용됩니다.')
        headers = {'X-API-Key':api_key}
        try:
            response = requests.get(base.rstrip('/')+'/site-access', headers=headers, timeout=4)
            response.raise_for_status()
            groups = response.json()['groups']
        except (requests.RequestException, ValueError, KeyError):
            st.warning('일시 허용 정책을 불러오지 못했습니다. 중앙 서버 v3.8 배포 및 연결 상태를 확인해 주세요.')
            return
        if not groups:
            st.info('최근 차단 기록과 현재 일시 허용 중인 사이트가 없습니다.')
            return
        search = st.text_input('PC 또는 사이트 검색', key='site_access_search')
        groups = [g for g in groups if search.lower() in (g['pc_name']+' '+g['domain']).lower()]
        pages = max(1, math.ceil(len(groups)/10))
        if st.session_state.get('site_access_page', 1) > pages:
            st.session_state['site_access_page'] = 1
        page = st.selectbox('페이지', range(1,pages+1), key='site_access_page')
        st.caption(f'{len(groups)}개 PC·사이트 조합 · 붙여넣기·첨부 시 최신 허용 정책을 확인합니다. 통신 지연 시 적용이 늦어질 수 있습니다.')
        for g in groups[(page-1)*10:page*10]:
            key = hashlib.sha256((g['device_id']+g['domain']).encode()).hexdigest()[:20]
            expires = datetime.fromisoformat(g['expires_at']) if g.get('expires_at') else None
            remaining = max(0, math.ceil((expires-datetime.now(timezone.utc)).total_seconds()/60)) if expires else 0
            a,b,c,d,e = st.columns([2,2,1,1.5,1.5])
            a.write(g['pc_name'])
            b.write(g['domain'])
            c.write(f"{g['attempts']}건")
            d.write(f'허용 설정 · {remaining}분 남음' if remaining else '차단 유지')
            if remaining:
                if e.button('다시 차단', key='revoke_'+key):
                    change(base, headers, g, 0)
            else:
                if e.button('일시 허용', key='allow_'+key):
                    st.session_state['site_access_selected'] = key
            action = {'PASTE_ATTEMPT':'텍스트 붙여넣기', 'FILE_UPLOAD_ATTEMPT':'파일·이미지 첨부', 'SITE_BLOCKED':'사이트 접속'}.get(g.get('last_action'), '기록 없음')
            stamp = datetime.fromisoformat(g['last_time']).astimezone(timezone(timedelta(hours=9))).strftime('%m-%d %H:%M:%S') if g.get('last_time') else '-'
            with st.expander(f'최근 {action} · {stamp} · 상세'):
                st.write(f"PC: {g['pc_name']} · 사이트: {g['domain']}")
                st.caption('동일 PC·사이트의 반복 기록을 합산한 건수입니다. 개별 이벤트는 아래 수집 로그에서 확인할 수 있습니다.')
                st.code(g['device_id'], language=None)
            if st.session_state.get('site_access_selected') == key and not remaining:
                with st.form('grant_form_'+key):
                    st.write(f"{g['pc_name']} · {g['domain']} 일시 허용")
                    st.caption('텍스트 붙여넣기 · 이미지 · 파일 첨부를 함께 허용합니다. 기록은 유지되며 만료 후 자동으로 차단 정책이 복원됩니다.')
                    minutes = st.selectbox('허용 시간', [15,30,60], index=1, format_func=lambda n:f'{n}분')
                    ok,cancel = st.columns(2)
                    if ok.form_submit_button('허용 적용'):
                        change(base, headers, g, minutes)
                    if cancel.form_submit_button('취소'):
                        st.session_state.pop('site_access_selected',None)
                        st.rerun()


def change(base, headers, group, minutes):
    try:
        response = requests.post(base.rstrip('/')+'/site-access', headers=headers,
                                 json={**{k:group[k] for k in ('device_id','domain','pc_name')},'minutes':minutes},timeout=5)
        response.raise_for_status()
    except requests.RequestException:
        st.error('정책 변경에 실패했습니다. 현재 권한은 바뀌지 않았을 수 있으니 새로고침 후 확인해 주세요.')
        return
    st.session_state.pop('site_access_selected', None)
    st.rerun()
