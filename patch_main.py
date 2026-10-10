import re

path = "/Users/daras/Documents/Codex/Depth Video/backend/main.py"
with open(path) as f:
    t = f.read()

# Make the import more robust
replacement = """# --- NEW: Import WolfCut API ---
try:
    try:
        from backend.wolfcut_api import router as wolfcut_router
    except ImportError:
        from wolfcut_api import router as wolfcut_router
    app.include_router(wolfcut_router)
    
    # Mount the compiled WolfCut web UI
    WOLFCUT_DIST = os.path.join(_PROJECT_DIR, "scratch", "WolfCut", "desktop", "dist")
    if os.path.exists(WOLFCUT_DIST):
        app.mount("/editor", StaticFiles(directory=WOLFCUT_DIST, html=True), name="editor")
except Exception as e:
    import traceback
    traceback.print_exc()
    print("WolfCut API not loaded:", e)"""

t = re.sub(r'# --- NEW: Import WolfCut API ---.*?except ImportError as e:\n    print\("WolfCut API not loaded:", e\)', replacement, t, flags=re.DOTALL)

with open(path, "w") as f:
    f.write(t)
print("✅ main.py patched")
