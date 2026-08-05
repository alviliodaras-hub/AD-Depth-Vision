import os
import sys
import threading
import time

def start_backend():
    import uvicorn
    from main import app
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")

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
    time.sleep(1.5)

    try:
        import webview
        print("🖥️  Opening Native Mac Desktop Window...")
        webview.create_window(
            "AD-Depth Vision",
            "http://127.0.0.1:8000/app/",
            width=1280,
            height=850,
            resizable=True,
            min_size=(900, 600)
        )
        webview.start()
    except ImportError:
        print("💡 pywebview not installed. Installing native window package...")
        os.system(f"{sys.executable} -m pip install pywebview")
        import webview
        webview.create_window(
            "AD-Depth Vision",
            "http://127.0.0.1:8000/app/",
            width=1280,
            height=850,
            resizable=True,
            min_size=(900, 600)
        )
        webview.start()
