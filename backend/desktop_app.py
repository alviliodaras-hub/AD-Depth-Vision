import os
import sys
import threading
import time
import subprocess

def start_backend(port):
    try:
        import uvicorn
        from main import app
        print(f"✅ Starting server on 127.0.0.1:{port}")
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    except Exception as e:
        print(f"❌ Backend server error: {e}")
        import traceback
        traceback.print_exc()

def find_free_port():
    """Find a free port by testing if we can connect to it."""
    import socket
    for port in range(8000, 8011):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                result = s.connect_ex(('127.0.0.1', port))
                if result != 0:  # Port is free (connection refused = nothing listening)
                    return port
        except Exception:
            continue
    return 8000  # Fallback

def wait_for_server(port, timeout=20):
    """Poll the health endpoint until server is ready."""
    import urllib.request
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            req = urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
            if req.status == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

if __name__ == "__main__":
    print("=" * 60)
    print("🔮 Launching AD-Depth Vision Native Desktop App...")
    print("=" * 60)
    
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(backend_dir)
    sys.path.insert(0, backend_dir)

    # Get port from environment (set by run.sh) or find one
    port = int(os.environ.get("AD_DEPTH_PORT", 0))
    if port == 0:
        port = find_free_port()

    # Start backend server in background thread
    server_thread = threading.Thread(target=start_backend, args=(port,), daemon=True)
    server_thread.start()
    
    # Wait for server to be ready
    print(f"⏳ Waiting for server on port {port}...")
    if not wait_for_server(port):
        print("❌ Server failed to start. Please check the error messages above.")
        input("Press Enter to exit...")
        sys.exit(1)
    
    print("✅ Server is ready!")

    # Try pywebview for native window
    try:
        import webview
    except ImportError:
        print("💡 Installing native window package (pywebview)...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pywebview", "--quiet"])
        import webview

    try:
        print(f"🖥️  Opening Native Mac Desktop Window...")
        webview.create_window(
            "AD-Depth Vision",
            f"http://127.0.0.1:{port}/app/?_t={int(time.time())}",
            width=1280,
            height=850,
            resizable=True,
            min_size=(900, 600)
        )
        webview.start()
    except Exception as e:
        print(f"⚠️  Native window failed: {e}")
        print(f"💡 Opening in browser instead...")
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:{port}/app/")
        # Keep server running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
