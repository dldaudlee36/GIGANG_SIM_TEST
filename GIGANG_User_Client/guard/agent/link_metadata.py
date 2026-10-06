"""Whitelist provenance only. Never forward browser fingerprints or plaintext."""
from datetime import datetime
from uuid import UUID


def link_metadata(data, kind, target):
    result = {}
    if 'trace_id' in data:
        result['trace_id'] = str(UUID(data['trace_id']))
    status = data.get('match_status', 'not_checked')
    if status not in ('matched', 'no_match', 'not_checked', 'source_recorded', 'internal_destination'):
        raise ValueError('Invalid match status')
    result['match_status'] = status
    if status != 'matched':
        return result
    source = data.get('match')
    if not isinstance(source, dict) or kind not in ('PASTE_ATTEMPT', 'FILE_UPLOAD_ATTEMPT'):
        raise ValueError('Invalid match evidence')
    if target == 'desktop-oli.tail2bbbea.ts.net':
        raise ValueError('Internal destination is not an external match')
    expected = ('COPY_ATTEMPT', '/db', 'salted_sha256_text_lf') if kind == 'PASTE_ATTEMPT' else (
        'DOWNLOAD_COMPLETED', '/db/download', 'sha256_file_bytes')
    if (kind == 'FILE_UPLOAD_ATTEMPT' and isinstance(data.get('image_guard'), dict)
            and data['image_guard'].get('outcome') == 'blocked_match'
            and data['image_guard'].get('channel') in ('paste','file','drop')):
        expected = ('DB_SCREEN_VIEW', '/db', 'windows_ocr_db_cells')
    if (source.get('source_kind'), source.get('source_path'), source.get('method')) != expected:
        raise ValueError('Mismatched provenance kind')
    if source.get('source_domain') != 'desktop-oli.tail2bbbea.ts.net':
        raise ValueError('Unknown provenance source')
    age, count = source.get('age_seconds'), source.get('candidate_count')
    if type(age) is not int or not 0 <= age <= 1800 or type(count) is not int or not 1 <= count <= 100:
        raise ValueError('Invalid provenance age/count')
    stamp = source.get('source_time')
    if not isinstance(stamp, str) or len(stamp) > 64:
        raise ValueError('Invalid source timestamp')
    parsed = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Source timestamp needs timezone')
    result['match'] = dict(
        source_trace_id=str(UUID(source['source_trace_id'])),
        source_kind=expected[0], source_domain=source['source_domain'], source_path=expected[1],
        source_time=stamp, method=expected[2], age_seconds=age, candidate_count=count)
    return result
