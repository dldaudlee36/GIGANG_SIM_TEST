from pathlib import Path
import ctypes
import importlib
import os
import socket
import subprocess
import sys
import time
import webbrowser

APP = Path(__file__).resolve().parents[1]
MODES = {'all': ('agent', 'dashboard'), 'admin': ('dashboard',), 'user': ('agent',)}

def commands(mode):
    result = []
    for role in MODES[mode]:
        if role == 'agent':
            cmd = [sys.executable, str(APP / 'guard' / 'agent' / 'agent.py')]
            port = 8765
        else:
            cmd = [sys.executable, '-m', 'streamlit', 'run', str(APP / 'app.py'),
                   '--server.address', '127.0.0.1', '--server.port', '8501', '--server.headless', 'true']
            port = 8501
        result.append((role, port, cmd))
    return result

def listening(port):
    with socket.socket() as sock:
        sock.settimeout(.3)
        return sock.connect_ex(('127.0.0.1', port)) == 0

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode not in MODES:
        raise ValueError('Choose all, admin or user.')
    if '--plan' in sys.argv:
        for role, port, cmd in commands(mode):
            print(role, port, subprocess.list2cmdline(cmd))
        return
    os.chdir(APP)
    if 'agent' in MODES[mode] and not ctypes.windll.shell32.IsUserAnAdmin():
        args = subprocess.list2cmdline([str(Path(__file__).resolve()), mode])
        result = ctypes.windll.shell32.ShellExecuteW(None, 'runas', sys.executable, args, str(APP), 1)
        if result <= 32:
            raise RuntimeError('Windows administrator permission was cancelled or failed.')
        return
    if 'agent' in MODES[mode]:
        from lifecycle import mode as lifecycle_mode, publish, ensure_bridge
        was_stopped = lifecycle_mode() == 'stopped'
        publish('running')
        ensure_bridge()
        if was_stopped:
            time.sleep(1.6)  # Let all short-lived STOP permissions expire before startup.
    required = ['requests', 'dotenv', 'PIL']
    if 'dashboard' in MODES[mode]:
        required += ['streamlit', 'pydantic', 'pandas', 'google.genai']
    missing = False
    for module in required:
        try:
            importlib.import_module(module)
        except ImportError:
            missing = True
    if missing:
        install = ['-r', str(APP / 'requirements.txt')] if 'dashboard' in MODES[mode] else ['requests', 'python-dotenv', 'Pillow>=10.0.0']
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', *install])
    for role, port, cmd in commands(mode):
        if listening(port):
            print(f'[SKIP] Port {port} is already in use. No duplicate {role} was started.')
            print('If this is an older version, close its window and run this launcher again.')
            continue
        child = subprocess.Popen(cmd, cwd=APP, creationflags=subprocess.CREATE_NEW_CONSOLE)
        deadline = time.monotonic() + 20
        while not listening(port):
            if child.poll() is not None:
                raise RuntimeError(f'{role} exited. Check its console window.')
            if time.monotonic() >= deadline:
                raise RuntimeError(f'{role} is not ready yet. Check its console window before retrying.')
            time.sleep(.25)
        print(f'[OK] {role}: 127.0.0.1:{port}')
    if 'dashboard' in MODES[mode]:
        webbrowser.open('http://127.0.0.1:8501')
    print('Keep the Agent / dashboard console windows open while using GIGANG.')
    time.sleep(2)

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'[ERROR] {exc}')
        input('Press Enter to close...')
        sys.exit(1)
