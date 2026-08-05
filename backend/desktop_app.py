import os
import sys
import threading
import time

def start_backend():
    try:
        import uvicorn
        from main import app
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")
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
    except Exception as e:
        print(f"❌ Error starting native window: {e}")
        input("Press Enter to exit...")
