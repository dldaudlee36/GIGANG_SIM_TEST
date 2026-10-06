from pathlib import Path
import ctypes
import os
import subprocess
import sys

APP = Path(__file__).resolve().parents[1]
MODES = {'all': ('agent', 'dashboard'), 'admin': ('dashboard',), 'user': ('agent',)}
BEGIN = b'# BEGIN GIGANG MANAGED BLOCK'
END = b'# END GIGANG MANAGED BLOCK'

def strip_managed(data):
    output = []
    inside = False
    for line in data.splitlines(keepends=True):
        marker = line.strip()
        bom = b'\xef\xbb\xbf' if not output and marker.startswith(b'\xef\xbb\xbf') else b''
        if bom:
            marker = marker[len(bom):]
        if marker == BEGIN:
            if inside:
                raise ValueError('Nested hosts markers; hosts file left unchanged.')
            if bom:
                output.append(bom)
            inside = True
        elif marker == END:
            if not inside:
                raise ValueError('Unbalanced hosts markers; hosts file left unchanged.')
            inside = False
        elif not inside:
            output.append(line)
    if inside:
        raise ValueError('Unclosed hosts marker; hosts file left unchanged.')
    return b''.join(output)

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode not in MODES:
        raise ValueError('Choose all, admin or user.')
    if not ctypes.windll.shell32.IsUserAnAdmin():
        args = subprocess.list2cmdline([str(Path(__file__).resolve()), mode])
        result = ctypes.windll.shell32.ShellExecuteW(None, 'runas', sys.executable, args, str(APP), 1)
        if result <= 32:
            raise RuntimeError('Windows administrator permission was cancelled or failed.')
        return
    subprocess.check_call(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                           '-File', str(APP / 'tools' / 'stop_processes.ps1'), '-Mode', mode])
    if 'agent' in MODES[mode]:
        hosts = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'System32/drivers/etc/hosts'
        original = hosts.read_bytes()
        cleaned = strip_managed(original)
        if cleaned != original:
            backup = APP / 'launcher-logs' / 'hosts-before-stop.bin'
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(original)
            if hosts.read_bytes() != original:
                raise RuntimeError('Hosts file changed concurrently. Run STOP again.')
            hosts.write_bytes(cleaned)
            subprocess.run(['ipconfig', '/flushdns'], check=True, stdout=subprocess.DEVNULL)
        print('[OK] GIGANG local hosts blocking removed. Central policy is unchanged.')
        from lifecycle import ensure_bridge, publish
        ensure_bridge()
        publish('stopped')
        print('[OK] Chrome extension checks paused. START resumes them automatically.')
    print('[OK] Stop completed. The Chrome extension remains installed.')
    input('Press Enter to close...')

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'[ERROR] {exc}')
        input('Press Enter to close...')
        sys.exit(1)
