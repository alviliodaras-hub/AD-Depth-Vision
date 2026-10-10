import re
path = "/Users/daras/Documents/Codex/Depth Video/backend/wolfcut_api.py"
with open(path) as f:
    t = f.read()

# 1. Add missing filmstrip / peak routes
stubs = """
@router.post("/extract_filmstrip")
async def extract_filmstrip(req: dict):
    # Empty PNG arraybuffer
    import base64
    return JSONResponse(content={"bytes": base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")})

@router.post("/extract_peaks")
async def extract_peaks(req: dict):
    # Empty peaks array
    return JSONResponse(content={"bytes": ""})

@router.post("/read_media_bytes")
async def read_media_bytes(req: dict):
    # Actual file bytes if possible
    try:
        with open(req["path"], "rb") as f:
            import base64
            return JSONResponse(content={"bytes": base64.b64encode(f.read()).decode("utf-8")})
    except:
        return JSONResponse(content={"bytes": ""})
"""

if "/extract_filmstrip" not in t:
    t = t.replace("# ── Stubs for audio/preview/tts so UI doesn't crash ────────────────────────", 
                  "# ── Stubs for audio/preview/tts so UI doesn't crash ────────────────────────\n" + stubs)

# 2. Fix addTextClip
bad_text = """        tl["clips"].append({
            "id": cid, "kind": "text", "mediaId": "", "trackId": cmd["trackId"] or tl["tracks"][-1]["id"],
            "name": cmd.get("style", {}).get("text", "Text"),
            "start": cmd["start"], "duration": cmd.get("duration", 3.0), "sourceStart": 0.0,
            "volume": 1.0, "fadeIn": 0.0, "fadeOut": 0.0, "speed": 1.0, "preservePitch": True,
            "scale": 1.0, "offsetX": 0.0, "offsetY": cmd.get("offsetY", 0.0), "rotation": 0.0, "opacity": 1.0,
            "muted": False, "filters": [], "videoEffects": [],
            "text": cmd.get("style", {})
        })"""
good_text = """        style = cmd.get("style")
        if not style:
            style = {"text": "New Text", "family": "Inter", "weight": 400, "italic": False, "color": "#ffffff"}
        
        # UI expects "name" of the clip to mirror the text content initially
        tl["clips"].append({
            "id": cid, "kind": "text", "mediaId": "", "trackId": cmd["trackId"] or tl["tracks"][-1]["id"],
            "name": style.get("text", "Text"),
            "start": cmd["start"], "duration": cmd.get("duration", 3.0), "sourceStart": 0.0,
            "volume": 1.0, "fadeIn": 0.0, "fadeOut": 0.0, "speed": 1.0, "preservePitch": True,
            "scale": 1.0, "offsetX": 0.0, "offsetY": cmd.get("offsetY", 0.0) if cmd.get("offsetY") is not None else 0.0, "rotation": 0.0, "opacity": 1.0,
            "muted": False, "filters": [], "videoEffects": [],
            "text": style
        })"""
t = t.replace(bad_text, good_text)

# 3. Add setClipTransform support
if 'elif op == "setClipTransform":' not in t:
    t = t.replace('    elif op == "updateClip":', 
                  '    elif op == "setClipTransform":\n'
                  '        clip = next((c for c in tl["clips"] if c["id"] == cmd["clipId"]), None)\n'
                  '        if clip:\n'
                  '            for k in ["scale", "offsetX", "offsetY", "rotation"]:\n'
                  '                if k in cmd: clip[k] = cmd[k]\n'
                  '    elif op == "updateClip":')

with open(path, "w") as f:
    f.write(t)
print("✅ Fixed missing routes and text/transform commands")
