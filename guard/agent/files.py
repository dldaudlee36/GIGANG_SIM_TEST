"""GIGANG Agent 파일 검사: 기밀 DB에서 받은 파일의 내용을 PC 안에서 규칙 검사하고 '건수'만 돌려준다.

    from files import inspect_file
    inspect_file(r"C:\\Users\\kim\\Downloads\\customers.csv")
    # {'file_kind': 'csv', 'inspectable': True, 'text_length': 5210, 'pattern_hits': {...}}
    inspect_file(r"C:\\Users\\kim\\Downloads\\report.pdf")
    # {'file_kind': 'pdf', 'inspectable': False, 'reason': '내용 검사 미지원 형식'}

- 검사할 수 있는 파일(CSV·TSV·TXT·XLSX)은 rules.scan_text 로 규칙별 건수를 센다 → 서버에서 DL-1 (부서 표 그대로)
- 검사할 수 없는 파일(PDF·이미지·ZIP·암호 걸린 엑셀·너무 큰 파일 등)은 이유만 돌려준다 → 서버에서 DL-2 (1회도 WATCH)
- 파일 내용은 이 함수 밖으로 나가지 않는다.
"""
import os
import re
import zipfile
import xml.etree.ElementTree as ET

from rules import scan_text

TEXT_KINDS = {'csv', 'tsv', 'txt'}
# 이보다 크면 끝까지 검사하지 못하므로 '검사 불가'로 본다 (일부만 보고 0건이라 하면 미탐이 된다)
MAX_TEXT_BYTES = 20 * 1024 * 1024
# XLSX 압축을 풀었을 때의 최대 크기 (압축 폭탄 방지)
MAX_XLSX_XML_BYTES = 100 * 1024 * 1024

_NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
_SHEET = re.compile(r'xl/worksheets/sheet\d+\.xml')


def _decode(data):
    """한국어 엑셀 CSV(CP949)까지 고려해 글자로 바꾼다. 글자가 아닌 파일이면 None."""
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        return data.decode('utf-16', 'replace')
    if b'\x00' in data:
        return None
    for encoding in ('utf-8-sig', 'cp949'):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    return data.decode('utf-8', 'replace')


def _xlsx_text(path):
    """XLSX 의 모든 시트를 '셀은 탭, 행은 줄바꿈'으로 이은 글자로 만든다."""
    with zipfile.ZipFile(path) as book:
        names = book.namelist()
        if sum(info.file_size for info in book.infolist()) > MAX_XLSX_XML_BYTES:
            return None
        shared = []
        if 'xl/sharedStrings.xml' in names:
            root = ET.fromstring(book.read('xl/sharedStrings.xml'))
            shared = [''.join(t.text or '' for t in si.iter(_NS + 't')) for si in root.iter(_NS + 'si')]
        lines = []
        for name in sorted(n for n in names if _SHEET.fullmatch(n)):
            for row in ET.fromstring(book.read(name)).iter(_NS + 'row'):
                cells = []
                for cell in row.iter(_NS + 'c'):
                    kind, value = cell.get('t'), cell.find(_NS + 'v')
                    if kind == 's' and value is not None and (value.text or '').isdigit() \
                            and int(value.text) < len(shared):
                        cells.append(shared[int(value.text)])
                    elif kind == 'inlineStr':
                        cells.append(''.join(t.text or '' for t in cell.iter(_NS + 't')))
                    elif value is not None:
                        cells.append(value.text or '')
                lines.append('\t'.join(cells))
        return '\n'.join(lines)


def inspect_file(path):
    """받은 파일 하나를 검사한다. 내용이 아니라 형식·검사 가능 여부·규칙별 건수만 돌려준다."""
    kind = os.path.splitext(path)[1].lstrip('.').lower()[:16] or 'none'
    result = {'file_kind': kind, 'inspectable': False}
    try:
        size = os.path.getsize(path)
        if kind in TEXT_KINDS:
            if size > MAX_TEXT_BYTES:
                return dict(result, reason='파일이 커서 끝까지 검사 못 함')
            with open(path, 'rb') as f:
                text = _decode(f.read())
            if text is None:
                return dict(result, reason='글자 파일이 아님')
        elif kind == 'xlsx':
            text = _xlsx_text(path)
            if text is None:
                return dict(result, reason='파일이 커서 끝까지 검사 못 함')
        else:
            return dict(result, reason='내용 검사 미지원 형식')
    except zipfile.BadZipFile:
        # 암호를 건 XLSX 는 ZIP 이 아니라 암호화된 다른 형식으로 저장된다
        return dict(result, reason='암호 파일이거나 열 수 없는 형식')
    except (OSError, ValueError, ET.ParseError, KeyError, RuntimeError):
        return dict(result, reason='파일을 읽지 못함')
    return dict(result, inspectable=True, text_length=len(text), pattern_hits=scan_text(text))
