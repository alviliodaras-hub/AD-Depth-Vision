import re

path = "/Users/daras/Documents/Codex/Depth Video/backend/main.py"
with open(path) as f:
    t = f.read()

# Make sure it prints loudly if the mount fails, and move the mount OUTSIDE the wolfcut_api import try block
# just in case wolfcut_api has some weird import error so the UI still loads
replacement = """# --- NEW: Import WolfCut API ---
try:
    try:
        from backend.wolfcut_api import router as wolfcut_router
    except ImportError:
        from wolfcut_api import router as wolfcut_router
    app.include_router(wolfcut_router)
except Exception as e:
    import traceback
    traceback.print_exc()
    print("WolfCut API routing not loaded:", e)

try:
    from fastapi.staticfiles import StaticFiles
    WOLFCUT_DIST = os.path.join(_PROJECT_DIR, "scratch", "WolfCut", "desktop", "dist")
    if os.path.exists(WOLFCUT_DIST):
        app.mount("/editor", StaticFiles(directory=WOLFCUT_DIST, html=True), name="editor")
        print("Mounted /editor successfully ->", WOLFCUT_DIST)
    else:
        print("WOLFCUT_DIST not found:", WOLFCUT_DIST)
except Exception as e:
    print("Failed to mount /editor:", e)
"""

t = re.sub(r'# --- NEW: Import WolfCut API ---.*?print\("WolfCut API not loaded:", e\)', replacement, t, flags=re.DOTALL)

with open(path, "w") as f:
    f.write(t)
print("✅ main.py mount patched")
