import os
import sys
import threading
import time
import socket
import subprocess

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

PORT = get_free_port()

def start_backend():
    try:
        import uvicorn
        from main import app
        print(f"✅ Starting server on 127.0.0.1:{PORT}")
        uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="error")
    except Exception as e:
        print(f"❌ Backend server error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=" * 60)
    print("🔮 Launching AD-Depth Vision Native Desktop App...")
    print("=" * 60)
    
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(backend_dir)
    sys.path.insert(0, backend_dir)

    # Start backend server silently in background thread
    server_thread = threading.Thread(target=start_backend, daemon=True)
    server_thread.start()
    
    # Wait for server to bind port
    time.sleep(1.5)

    try:
        import webview
    except ImportError:
        print("💡 pywebview not installed. Installing native window package...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pywebview"])
        import webview

    try:
        print(f"🖥️  Opening Native Mac Desktop Window on port {PORT}...")
        webview.create_window(
            "AD-Depth Vision",
            f"http://127.0.0.1:{PORT}/app/",
            width=1280,
            height=850,
            resizable=True,
            min_size=(900, 600)
        )
        webview.start()
    except Exception as e:
        print(f"❌ Error starting native window: {e}")
        input("Press Enter to exit...")
