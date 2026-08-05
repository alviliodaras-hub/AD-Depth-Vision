import os
import sys
import webbrowser
import threading
import time

def open_browser():
    time.sleep(2)
    print("🌐 Opening web browser...")
    webbrowser.open("http://127.0.0.1:8000/app/")

if __name__ == "__main__":
    print("=" * 60)
    print("🔮 AD-Depth Vision Local Server Starting...")
    print("=" * 60)
    
    # Ensure current directory is backend
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(backend_dir)
    sys.path.insert(0, backend_dir)

    # Launch browser thread
    threading.Thread(target=open_browser, daemon=True).start()

    try:
        import uvicorn
        from main import app
        print("✅ Backend loaded successfully. Listening on http://127.0.0.1:8000/app/")
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
    except ModuleNotFoundError as e:
        print(f"\n❌ Missing package: {e}")
        print("💡 Installing missing dependencies automatically...")
        os.system(f"{sys.executable} -m pip install -r requirements.txt")
        print("🔄 Restarting server...")
        import uvicorn
        from main import app
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
    except Exception as e:
        print(f"\n❌ Server Error: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
