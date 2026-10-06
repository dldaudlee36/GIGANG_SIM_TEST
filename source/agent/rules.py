"""GIGANG Agent 규칙 검사: 복사한 글자에서 민감정보 형태의 '건수'만 센다.

    from rules import scan_text
    scan_text("홍길동 900101-1234568 010-1234-5678")
    # {'phone': 1, 'email': 0, 'rrn': 1, 'rrn_high': 1, 'rrn_mid': 0, 'rrn_low': 0, 'account': 0, 'card': 0}

- 원문은 이 함수 밖으로 나가지 않는다. 서버로는 위 건수만 보낸다.
- 여기서는 "형태가 맞는지"만 본다. '여러 건' 기준값, 부서별 ○×, 등급(기록만/WATCH)은
  서버의 부서 정책 표에서 정한다. (수정계획 5장 구현 원칙)
- 같은 값이 여러 번 나오면 1건으로 센다. (서명에 들어간 내 번호가 반복되는 경우 등)
- 한 번 걸린 부분은 가려 두고 다음 규칙을 돌려서, 같은 숫자를 두 규칙이 겹쳐 세지 않는다.
  순서: 주민번호 → 카드번호 → 전화번호 → 계좌번호 → 이메일
"""
import re
from datetime import date

# 숫자 경계: \b 대신 "앞뒤가 숫자가 아님"으로 본다.
# \b 를 쓰면 "주민번호9001011234567" 처럼 한글에 바로 붙은 경우를 놓친다.
# 앞뒤에 하이픈·점으로 숫자가 더 이어지면(더 긴 번호의 일부) 제외한다.
_START = r'(?<!\d)(?<!\d[-.])'
_END = r'(?![-.]?\d)'

# ---------------------------------------------------------------------------
# 3. 주민번호 (외국인등록번호 포함)
# ---------------------------------------------------------------------------

# 6자리·7자리 사이 구분자: 없음, 하이픈, 각종 대시(긴 대시·전각 대시·마이너스), 점, 공백
_RRN_SEP = r'(?:[ ]?[-‐-―−－.][ ]?|[ ])?'
_RRN = re.compile(_START + r'(\d{6})(' + _RRN_SEP + r')(\d{7})' + _END)
# 표 복사로 열이 나뉜 경우 (6자리 [탭] 7자리)
_RRN_TAB = re.compile(_START + r'(\d{6})\t+(\d{7})' + _END)
# 뒷자리 마스킹 (900101-1******)
_RRN_MASKED = re.compile(_START + r'(\d{6})' + _RRN_SEP + r'(\d)[*xX●•＊]{6}(?![*xX●•＊\d])')

# 성별 자리 → 출생 세기. 외국인등록번호(5~8)와 1800년대(9·0)까지 허용.
_RRN_CENTURY = {'1': 1900, '2': 1900, '5': 1900, '6': 1900,
                '3': 2000, '4': 2000, '7': 2000, '8': 2000,
                '9': 1800, '0': 1800}
_RRN_WEIGHTS = (2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4, 5)
_RRN_MIN_TAB_ROWS = 2      # 탭으로 나뉜 모양은 2줄 이상 반복될 때만 인정
_RRN_MIN_MASKED = 2        # 마스킹은 단독이면 무시, 여러 건이면 인정


def _rrn_date_ok(front, gender):
    """앞 6자리가 실제 날짜이고 미래가 아니면 True. (필수 조건)"""
    try:
        born = date(_RRN_CENTURY[gender] + int(front[:2]), int(front[2:4]), int(front[4:6]))
    except ValueError:
        return False
    return born <= date.today()


def _rrn_checksum_ok(digits):
    """검증번호가 맞으면 True. (가점) 2020.10 이후 발급 번호는 안 맞을 수 있다."""
    total = sum(int(d) * w for d, w in zip(digits[:12], _RRN_WEIGHTS))
    last = int(digits[12])
    if (11 - total % 11) % 10 == last:
        return True
    # 구 외국인등록번호는 11 대신 13 기준으로 계산했다
    return digits[6] in '5678' and (13 - total % 11) % 10 == last


def _rrn_confidence(front, back, separated):
    """'high' / 'mid' / 'low', 형식이 아니면 None."""
    if not _rrn_date_ok(front, back[0]):
        return None
    if _rrn_checksum_ok(front + back):
        return 'high'
    # 검증번호만 안 맞음: 구분자가 있으면 중간, 13자리 연속 숫자면 느슨한 형식으로 보고 낮음
    # (날짜+일련번호 같은 관리번호가 13자리 연속 숫자로 많이 나오기 때문)
    return 'mid' if separated else 'low'


# ---------------------------------------------------------------------------
# 5. 카드번호
# ---------------------------------------------------------------------------

_CARD = re.compile(_START + r'(?:'
                   r'\d{13,19}'                                    # 연속 숫자
                   r'|\d{4}([ -])\d{4}\1\d{4}\1\d{4}(?:\1\d{1,3})?'  # 4-4-4-4(-n)
                   r'|\d{4}([ -])\d{6}\2\d{4,5}'                   # 아멕스·다이너스 4-6-5 / 4-6-4
                   r')' + _END)

# 카드사·결제대행사가 공개한 테스트 번호 (Luhn은 맞지만 실제 카드가 아님)
_CARD_TEST_NUMBERS = {
    '4111111111111111', '4242424242424242', '4000056655665556', '4012888888881881',
    '4222222222222', '5555555555554444', '5500005555555559', '5105105105105100',
    '2223003122003222', '378282246310005', '371449635398431', '378734493671000',
    '6011111111111117', '6011000990139424', '3530111333300000', '3566002020360505',
    '30569309025904', '38520000023237', '6200000000000005',
}


def _luhn_ok(digits):
    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d)
        if i % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def _card_prefix_ok(digits):
    """카드사 앞자리(IIN)와 길이가 맞으면 True."""
    n = len(digits)
    p2, p3, p4 = int(digits[:2]), int(digits[:3]), int(digits[:4])
    if digits[0] == '4':                                   # Visa
        return n in (13, 16, 19)
    if 51 <= p2 <= 55 or 2221 <= p4 <= 2720:               # Mastercard
        return n == 16
    if p2 in (34, 37):                                     # Amex
        return n == 15
    if 3528 <= p4 <= 3589:                                 # JCB
        return 16 <= n <= 19
    if p2 in (36, 38, 39) or 300 <= p3 <= 305:             # Diners
        return 14 <= n <= 19
    if p4 == 6011 or p2 == 65 or 644 <= p3 <= 649:         # Discover
        return 16 <= n <= 19
    if p2 == 62:                                           # UnionPay
        return 16 <= n <= 19
    if digits[0] == '9':                                   # 국내 전용 카드(BC 등)
        return n == 16
    return False


def _card_ok(digits):
    return (len(set(digits)) > 1
            and digits not in _CARD_TEST_NUMBERS
            and _card_prefix_ok(digits)
            and _luhn_ok(digits))


# ---------------------------------------------------------------------------
# 1. 전화번호
# ---------------------------------------------------------------------------

# 휴대폰: 앞자리 010·011·016~019. 구분자 없는 경우는 010 + 8자리만 인정.
_MOBILE = re.compile(_START + r'(?:01[016789][-. ]\d{3,4}[-. ]\d{4}|010\d{8})' + _END)
# 지역번호·인터넷전화: 마지막 구분자는 필수. 구분자 없는 10자리는 주문번호와 구분이 안 됨.
# 1588-XXXX 같은 대표번호는 0으로 시작하지 않아 걸리지 않는다.
_LANDLINE = re.compile(_START + r'\(?(?:02|03[1-3]|04[1-4]|05[1-5]|06[1-4]|070)\)?'
                       r'[-. ]?\d{3,4}[-. ]\d{4}' + _END)


# ---------------------------------------------------------------------------
# 4. 계좌번호
# ---------------------------------------------------------------------------

# 주요 은행 하이픈 자릿수 형식. 실제 도입 시 거래 은행 목록에 맞춰 조정.
_BANK_FORMATS = (
    (6, 2, 6),        # 국민, 농협, 우체국
    (3, 2, 4, 3),     # 국민(구)
    (3, 3, 6),        # 신한, 케이뱅크
    (3, 2, 6),        # 신한(구), SC제일
    (4, 3, 6),        # 우리
    (3, 6, 5),        # 하나
    (3, 4, 4, 2),     # 농협
    (3, 6, 2, 3),     # 기업
    (4, 2, 7),        # 카카오뱅크, 새마을금고
    (4, 4, 4),        # 토스뱅크
)
_ACCOUNT_HYPHEN = re.compile(_START + r'(?:' + '|'.join(
    '-'.join(r'\d{%d}' % n for n in fmt)
    for fmt in sorted(_BANK_FORMATS, key=sum, reverse=True)) + r')' + _END)
# 하이픈 없는 10~14자리는 송장번호·관리번호와 구분이 안 되므로, 앞에 계좌 관련 단어가 있을 때만 인정
_ACCOUNT_KEYWORD = re.compile(
    r'(?:계좌|입금|송금|은행|국민|신한|우리|하나|농협|기업|카카오뱅크|토스|우체국|새마을|account)'
    r'[^\d\n]{0,10}' + _START + r'(\d{10,14})' + _END, re.IGNORECASE)


# ---------------------------------------------------------------------------
# 2. 이메일
# ---------------------------------------------------------------------------

_EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}')
# 회사 공용 메일·시스템 계정. 개인정보가 아니므로 제외.
_SHARED_MAILBOXES = {
    'help', 'helpdesk', 'support', 'info', 'admin', 'administrator', 'contact', 'cs',
    'sales', 'hr', 'recruit', 'webmaster', 'postmaster', 'privacy', 'security', 'abuse',
    'noreply', 'no-reply', 'donotreply', 'do-not-reply', 'mailer-daemon', 'git', 'root',
}
# "icon@2x.png" 같은 파일 이름
_FILE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'js', 'css', 'ts', 'py'}


def _email_key(address):
    """세야 할 이메일이면 소문자 주소, 제외 대상이면 None."""
    address = address.lower().strip('.')
    local, _, domain = address.partition('@')
    if domain.rsplit('.', 1)[-1] in _FILE_EXTENSIONS:
        return None
    if local.split('+', 1)[0] in _SHARED_MAILBOXES:
        return None
    return address


# ---------------------------------------------------------------------------
# 검사 함수
# ---------------------------------------------------------------------------

def _digits(value):
    return re.sub(r'\D', '', value)


def _mask(text, matches):
    """걸린 부분을 같은 길이의 '#'으로 가려 다음 규칙이 다시 세지 않게 한다.
    [수정됨 10-06] 예전엔 걸릴 때마다 문자열 전체를 새로 만들어 건수에 비례해 느려졌다 (4,000줄 1.7초, 19MB CSV 는 수십 분).
    조각을 모아 한 번에 잇는다."""
    parts, pos = [], 0
    for m in sorted(matches, key=lambda m: m.start()):
        start = max(m.start(), pos)
        if m.end() <= start:
            continue
        parts.append(text[pos:start])
        parts.append('#' * (m.end() - start))
        pos = m.end()
    parts.append(text[pos:])
    return ''.join(parts)


def scan_text(text):
    """복사한 글자를 받아 규칙별 건수를 돌려준다. 원문은 돌려주지 않는다.

    반환 키:
      phone, email, account, card  : 규칙별 건수
      rrn                          : 주민번호 전체 건수 (= rrn_high + rrn_mid + rrn_low)
      rrn_high / rrn_mid / rrn_low : 주민번호 신뢰도별 건수
        high  13자리 + 날짜·성별·검증번호 모두 맞음
        mid   검증번호만 안 맞음 (2020.10 이후 발급 번호 등)
        low   마스킹, 13자리 연속 숫자인데 검증번호 안 맞음
    """
    if not isinstance(text, str):
        text = ''
    work = text
    rrn = {'high': set(), 'mid': set(), 'low': set()}
    seen = set()

    def add_rrn(level, key):
        if key not in seen:
            seen.add(key)
            rrn[level].add(key)

    # 3. 주민번호
    taken = []
    for m in _RRN.finditer(work):
        level = _rrn_confidence(m.group(1), m.group(3), bool(m.group(2)))
        if level:
            add_rrn(level, m.group(1) + m.group(3))
            taken.append(m)
    work = _mask(work, taken)

    tab_rows = [m for m in _RRN_TAB.finditer(work)
                if _rrn_confidence(m.group(1), m.group(2), True)]
    if len(tab_rows) >= _RRN_MIN_TAB_ROWS:
        for m in tab_rows:
            add_rrn(_rrn_confidence(m.group(1), m.group(2), True), m.group(1) + m.group(2))
        work = _mask(work, tab_rows)

    masked = [m for m in _RRN_MASKED.finditer(work) if _rrn_date_ok(m.group(1), m.group(2))]
    masked_keys = {m.group(1) + m.group(2) + '*' for m in masked}
    if len(masked_keys) >= _RRN_MIN_MASKED:
        for key in masked_keys:
            add_rrn('low', key)
        work = _mask(work, masked)

    # 5. 카드번호
    cards, taken = set(), []
    for m in _CARD.finditer(work):
        digits = _digits(m.group(0))
        if _card_ok(digits):
            cards.add(digits)
            taken.append(m)
    work = _mask(work, taken)

    # 1. 전화번호
    phones = set()
    for pattern in (_MOBILE, _LANDLINE):
        found = list(pattern.finditer(work))
        phones.update(_digits(m.group(0)) for m in found)
        work = _mask(work, found)

    # 4. 계좌번호
    accounts = set()
    found = list(_ACCOUNT_HYPHEN.finditer(work))
    accounts.update(_digits(m.group(0)) for m in found)
    work = _mask(work, found)
    accounts.update(m.group(1) for m in _ACCOUNT_KEYWORD.finditer(work))

    # 2. 이메일 (숫자 규칙과 겹치지 않으므로 원문 기준)
    emails = {key for key in map(_email_key, _EMAIL.findall(text)) if key}

    return {
        'phone': len(phones),
        'email': len(emails),
        'rrn': sum(len(v) for v in rrn.values()),
        'rrn_high': len(rrn['high']),
        'rrn_mid': len(rrn['mid']),
        'rrn_low': len(rrn['low']),
        'account': len(accounts),
        'card': len(cards),
    }
