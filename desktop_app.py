import os
import sys
import time
import socket
import threading
import uvicorn
import urllib.request

# Ensure correct base path whether running as script or bundled in PyInstaller
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = sys._MEIPASS
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = APP_DIR

os.chdir(APP_DIR)

from app import app

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

def start_server(port):
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

def wait_for_server(port, timeout=10):
    start = time.time()
    url = f"http://127.0.0.1:{port}/api/browsers"
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.15)
    return False

def main():
    port = 8000
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', port))
    except Exception:
        port = get_free_port()

    # Start the backend server in a background daemon thread
    server_thread = threading.Thread(target=start_server, args=(port,), daemon=True)
    server_thread.start()

    # Wait until server is listening
    wait_for_server(port)
    app_url = f"http://127.0.0.1:{port}"

    # Launch as a TRUE native Windows Desktop Application Window via pywebview
    try:
        import webview
        window = webview.create_window(
            title='YouTube Downloader Pro',
            url=app_url,
            width=1050,
            height=880,
            min_size=(850, 600),
            background_color='#0b0f19'
        )
        # webview.start() blocks until the desktop window is closed by the user
        webview.start()
        sys.exit(0)
    except Exception as e:
        # Fallback to edge app window if webview encounters system rendering issue
        edge_exe = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        if os.path.exists(edge_exe):
            import subprocess
            subprocess.run([
                edge_exe,
                f"--app={app_url}",
                "--window-size=1050,880"
            ])
        else:
            import webbrowser
            webbrowser.open(app_url)

if __name__ == "__main__":
    main()
