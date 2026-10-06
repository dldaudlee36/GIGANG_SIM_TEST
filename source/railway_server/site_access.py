"""Per-device, exact-host temporary grants and grouped blocked-attempt history."""
import re
import uuid
from datetime import datetime, timezone
from flask import request, jsonify


def install(app, connect, dict_cursor, api_key, normalize):
    raw_normalize = normalize
    def normalize(value):
        host = raw_normalize(value)
        return host[4:] if host.startswith('www.') else host

    def ensure(cur):
        cur.execute('''CREATE TABLE IF NOT EXISTS site_grants (
            device_id TEXT NOT NULL, domain TEXT NOT NULL, grant_id TEXT NOT NULL,
            pc_name TEXT NOT NULL, expires_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY(device_id, domain));
            CREATE TABLE IF NOT EXISTS site_blocks (
            id BIGSERIAL PRIMARY KEY, device_id TEXT NOT NULL, domain TEXT NOT NULL,
            pc_name TEXT NOT NULL, user_name TEXT NOT NULL, action TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
            CREATE INDEX IF NOT EXISTS site_blocks_time ON site_blocks(created_at);
            CREATE TABLE IF NOT EXISTS site_grant_audit (
            id BIGSERIAL PRIMARY KEY, device_id TEXT NOT NULL, domain TEXT NOT NULL,
            action TEXT NOT NULL, minutes INTEGER NOT NULL, grant_id TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());''')

    def opened():
        conn = connect()
        cur = conn.cursor(cursor_factory=dict_cursor)
        ensure(cur)
        conn.commit()
        return conn, cur

    def active(cur, device, domain):
        cur.execute('SELECT grant_id, expires_at FROM site_grants WHERE device_id=%s AND domain=%s AND expires_at>NOW()', (device, domain))
        return cur.fetchone()

    @app.route('/site-access/device', methods=['GET'])
    def device_grants():
        device = request.args.get('device_id', '')
        if not re.fullmatch('[a-f0-9]{64}', device):
            return jsonify(error='Invalid device'), 400
        conn, cur = opened()
        try:
            cur.execute('SELECT domain, grant_id, expires_at FROM site_grants WHERE device_id=%s AND expires_at>NOW()', (device,))
            return jsonify(grants=[dict(r, expires_at=r['expires_at'].isoformat()) for r in cur.fetchall()])
        finally:
            cur.close(); conn.close()

    @app.route('/site-access', methods=['GET', 'POST'])
    def manage():
        if request.headers.get('X-API-Key') != api_key:
            return jsonify(error='Unauthorized'), 401
        conn, cur = opened()
        try:
            if request.method == 'POST':
                data = request.get_json(silent=True) or {}
                device, domain = data.get('device_id', ''), normalize(data.get('domain'))
                minutes = data.get('minutes')
                if not re.fullmatch('[a-f0-9]{64}', str(device)) or not domain or type(minutes) is not int or minutes not in (0, 15, 30, 60):
                    return jsonify(error='Invalid grant'), 400
                grant_id = str(uuid.uuid4())
                cur.execute('''INSERT INTO site_grants(device_id, domain, grant_id, pc_name, expires_at)
                    VALUES(%s,%s,%s,%s,NOW() + %s * INTERVAL '1 minute')
                    ON CONFLICT(device_id,domain) DO UPDATE SET grant_id=EXCLUDED.grant_id,
                    pc_name=EXCLUDED.pc_name, expires_at=EXCLUDED.expires_at, updated_at=NOW()''',
                    (device, domain, grant_id, str(data.get('pc_name', ''))[:255], minutes))
                cur.execute('INSERT INTO site_grant_audit(device_id,domain,action,minutes,grant_id) VALUES(%s,%s,%s,%s,%s)',
                            (device,domain,'allow' if minutes else 'revoke',minutes,grant_id))
                conn.commit()
                return jsonify(status='allowed' if minutes else 'blocked')
            # Aggregate in PostgreSQL so bursts beyond /events' latest 100 do not disappear.
            cur.execute('''WITH recent AS (
                SELECT device_id,domain,MAX(pc_name) AS pc_name,COUNT(*) AS attempts,
                       MAX(created_at) AS last_time,
                       (ARRAY_AGG(action ORDER BY created_at DESC))[1] AS last_action
                FROM site_blocks WHERE created_at > NOW()-INTERVAL '24 hours'
                GROUP BY device_id,domain)
                SELECT COALESCE(r.device_id,g.device_id) AS device_id,
                       COALESCE(r.domain,g.domain) AS domain,
                       COALESCE(r.pc_name,g.pc_name) AS pc_name, COALESCE(r.attempts,0) AS attempts,
                       r.last_time,r.last_action,g.expires_at
                FROM recent r FULL OUTER JOIN
                (SELECT * FROM site_grants WHERE expires_at>NOW()) g
                ON r.device_id=g.device_id AND r.domain=g.domain
                ORDER BY r.last_time DESC NULLS LAST''')
            return jsonify(groups=[dict(r, last_time=r['last_time'].isoformat() if r['last_time'] else None,
                                        expires_at=r['expires_at'].isoformat() if r['expires_at'] else None) for r in cur.fetchall()])
        finally:
            cur.close(); conn.close()

    def classify(data):
        # Do not trust a client-supplied "approved" flag.
        requested = data.pop('authorization', None)
        device, domain = data.get('device_id', ''), normalize(data.get('target'))
        if not re.fullmatch('[a-f0-9]{64}', str(device)) or not domain:
            return
        kind = data.get('event_type')
        if kind not in ('PASTE_ATTEMPT','FILE_UPLOAD_ATTEMPT','SITE_BLOCKED'):
            return
        conn, cur = opened()
        try:
            grant = active(cur, device, domain)
            if isinstance(requested, dict) and grant and requested.get('grant_id') == grant['grant_id']:
                data['authorization'] = {'status':'approved', 'grant_id':grant['grant_id'], 'verified':True}
            elif (data.get('match_status') == 'matched' or kind == 'SITE_BLOCKED' or
                  (data.get('image_guard') or {}).get('outcome') == 'held_error'):
                cur.execute('INSERT INTO site_blocks(device_id,domain,pc_name,user_name,action) VALUES(%s,%s,%s,%s,%s)',
                            (device,domain,str(data.get('pc_name',''))[:255],str(data.get('user',''))[:255],kind))
            conn.commit()
        finally:
            cur.close(); conn.close()
    return classify
