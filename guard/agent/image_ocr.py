"""Local Windows OCR. Image bytes and text never go to Railway or an external AI."""
import base64
import binascii
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading

MAX_BYTES = 8 * 1024 * 1024
_slot = threading.BoundedSemaphore(1)


def recognize_image(data):
    encoded = data.get('image_base64') if isinstance(data, dict) else None
    if not isinstance(encoded, str) or not 0 < len(encoded) <= ((MAX_BYTES + 2) // 3) * 4:
        raise ValueError('IMAGE_TOO_LARGE_OR_EMPTY')
    try:
        image = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError('INVALID_IMAGE') from None
    if len(image) > MAX_BYTES:
        raise ValueError('IMAGE_TOO_LARGE')
    if not (image.startswith(b'\x89PNG\r\n\x1a\n') or image.startswith(b'\xff\xd8\xff')):
        raise ValueError('PNG_OR_JPEG_REQUIRED')
    if not _slot.acquire(blocking=False):
        return {'status': 'error', 'error': 'OCR_BUSY'}
    try:
        # A short-lived private temp directory is removed on success/failure/timeout.
        with tempfile.TemporaryDirectory(prefix='gigang-ocr-') as folder:
            path = Path(folder) / 'image.bin'
            path.write_bytes(image)
            powershell = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
            try:
                run = subprocess.run(
                    [str(powershell), '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                     '-File', str(Path(__file__).with_suffix('.ps1')), '-ImagePath', str(path)],
                    capture_output=True, encoding='utf-8-sig', errors='replace', timeout=25,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                )
                result = json.loads(run.stdout.strip())
                if result.get('status') == 'ok' and isinstance(result.get('lines'), list):
                    return result
                return {'status': 'error', 'error': result.get('error', 'OCR_FAILED')}
            except subprocess.TimeoutExpired:
                return {'status': 'error', 'error': 'OCR_TIMEOUT'}
            except (OSError, ValueError, AttributeError):
                return {'status': 'error', 'error': 'OCR_UNAVAILABLE'}
    finally:
        _slot.release()
