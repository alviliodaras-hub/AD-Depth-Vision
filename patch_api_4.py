import re
path = "/Users/daras/Documents/Codex/Depth Video/backend/wolfcut_api.py"
with open(path) as f:
    t = f.read()

# Fix the binary routes to return raw bytes, not JSON Response
from_str = """@router.post("/extract_filmstrip")
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
        return JSONResponse(content={"bytes": ""})"""

to_str = """from fastapi.responses import Response

@router.post("/extract_filmstrip")
async def extract_filmstrip(req: dict):
    import base64
    return Response(content=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="), media_type="image/png")

@router.post("/extract_peaks")
async def extract_peaks(req: dict):
    return Response(content=b"", media_type="application/octet-stream")

@router.post("/read_media_bytes")
async def read_media_bytes(req: dict):
    try:
        with open(req["path"], "rb") as f:
            return Response(content=f.read(), media_type="application/octet-stream")
    except:
        return Response(content=b"", media_type="application/octet-stream")"""

t = t.replace(from_str, to_str)

# Also fix preview_frame which had the same bug
prev_from = """@router.post("/preview_frame")
async def preview_frame(req: dict):
    # Returns a blank 1x1 png arraybuffer as a stub
    import base64
    return JSONResponse(content={"bytes": base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")})"""

prev_to = """@router.post("/preview_frame")
async def preview_frame(req: dict):
    import base64
    return Response(content=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="), media_type="image/png")"""

t = t.replace(prev_from, prev_to)

with open(path, "w") as f:
    f.write(t)
print("✅ Binary responses patched")
