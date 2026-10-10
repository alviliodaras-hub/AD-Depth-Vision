"""
WolfCut Web Backend — Python reducer + REST API replacing the Rust Tauri engine.

Provides all endpoints that engine-web.ts calls via fetch/WebSocket, implementing
the full command reducer with undo/redo history, proper ID minting, and stubs for
preview/audio/TTS/transcription features.
"""

import os, json, uuid, time, shutil, zipfile, copy, subprocess, mimetypes
from fastapi import APIRouter, UploadFile, File, Form, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, FileResponse, Response, StreamingResponse
from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Set
import asyncio

router = APIRouter(prefix="/wolfcut", tags=["wolfcut"])

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_BACKEND_DIR)
_BASE_PROCESSED = os.environ.get("PROCESSED_DIR", os.path.join(_PROJECT_DIR, "processed"))
_BASE_UPLOADS = os.environ.get("UPLOAD_DIR", os.path.join(_PROJECT_DIR, "uploads"))
PROJECTS_DIR = os.path.join(_BASE_PROCESSED, "wolfcut_projects")
MEDIA_DIR = os.path.join(_BASE_UPLOADS, "wolfcut_media")
os.makedirs(PROJECTS_DIR, exist_ok=True)
os.makedirs(MEDIA_DIR, exist_ok=True)

# ── Tiny 1x1 PNG for preview stubs ────────────────────────────────────────
import base64
PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)

# ── State Management ──────────────────────────────────────────────────────

# Single-user session store
sessions: Dict[str, dict] = {}          # pdir -> EditorView
undo_stack: Dict[str, list] = {}        # pdir -> [EditorView snapshots]
redo_stack: Dict[str, list] = {}        # pdir -> [EditorView snapshots]
media_counter: Dict[str, int] = {}      # pdir -> running counter for media IDs
timeline_counter: Dict[str, int] = {}   # pdir -> running counter for timeline IDs

# WebSocket clients for event broadcasting
ws_clients: Set[WebSocket] = set()


def _active_pdir() -> Optional[str]:
    """Return the single active project directory, or None."""
    if not sessions:
        return None
    return list(sessions.keys())[-1]


def _next_media_id(pdir: str) -> str:
    """Mint a media ID like the Rust engine does: m1, m2, ..."""
    c = media_counter.get(pdir, 0) + 1
    media_counter[pdir] = c
    return f"m{c}"


def _next_timeline_id(pdir: str) -> str:
    c = timeline_counter.get(pdir, 0) + 1
    timeline_counter[pdir] = c
    return f"TL{c}"


def create_empty_project(name: str, w: int, h: int) -> dict:
    return {
        "media": [],
        "fonts": [],
        "activeTimelineId": "TL1",
        "timelines": [{
            "id": "TL1",
            "name": "Timeline 1",
            "tracks": [
                {"id": f"T{i}", "name": f"Track {i}", "visible": True, "muted": False}
                for i in range(1, 5)
            ],
            "clips": []
        }]
    }


def _active_tl(proj: dict) -> dict:
    """Return the active timeline from a project dict."""
    aid = proj.get("activeTimelineId", "TL1")
    for t in proj.get("timelines", []):
        if t["id"] == aid:
            return t
    if proj["timelines"]:
        return proj["timelines"][0]
    # Fallback: create one
    tl = {"id": "TL1", "name": "Timeline 1", "tracks": [], "clips": []}
    proj["timelines"] = [tl]
    proj["activeTimelineId"] = "TL1"
    return tl


def apply_command(view: dict, cmd: dict, pdir: str) -> dict:
    """Apply a single editor command to the view, mutating in place. Returns view."""
    op = cmd.get("op")
    proj = view["project"]
    tl = _active_tl(proj)

    # Clear createdId by default; individual ops set it when they create something
    view.pop("createdId", None)

    if op == "addMedia":
        item = dict(cmd["item"])  # copy so we don't mutate the input
        mid = item.get("id") or _next_media_id(pdir)
        item["id"] = mid
        existing = next((m for m in proj["media"] if m.get("path") == item.get("path") or m.get("id") == mid), None)
        if not existing:
            proj["media"].append(item)
            view["createdId"] = mid
        else:
            view["createdId"] = existing["id"]

    elif op == "removeMedia":
        proj["media"] = [m for m in proj["media"] if m["id"] != cmd["mediaId"]]

    elif op == "setMediaPlaceholder":
        for m in proj["media"]:
            if m["id"] == cmd["mediaId"]:
                m["placeholder"] = cmd["placeholder"]
                break

    elif op == "fillSlot":
        item = dict(cmd["item"])
        mid = item.get("id") or _next_media_id(pdir)
        item["id"] = mid
        # Replace the slot media with the new item
        proj["media"] = [item if m["id"] == cmd["mediaId"] else m for m in proj["media"]]
        view["createdId"] = mid

    elif op == "batch":
        last_created = None
        for c in cmd.get("commands", []):
            apply_command(view, c, pdir)
            if view.get("createdId"):
                last_created = view["createdId"]
        if last_created:
            view["createdId"] = last_created

    elif op == "addClipAtFirstFree":
        cid = str(uuid.uuid4())
        media = next((m for m in proj["media"] if m.get("id") == cmd["mediaId"]), None)
        if not media:
            media = next((m for m in proj["media"] if m.get("path") == cmd["mediaId"]), None)
        if not media and proj.get("media"):
            media = proj["media"][0]
        duration = media.get("duration") or 5.0 if media else 5.0
        kind = media.get("kind", "video") if media else "video"
        name = media.get("name", "Clip") if media else "Clip"
        media_id = media.get("id", cmd.get("mediaId", "m1")) if media else cmd.get("mediaId", "m1")
        start = max(0.0, float(cmd.get("start", 0.0)))
        track_id = _find_free_track(tl, start, duration)
        tl["clips"].append(_make_clip(cid, kind, media_id, track_id, name, start, duration))
        view["createdId"] = cid

    elif op == "addClip":
        cid = str(uuid.uuid4())
        media = next((m for m in proj["media"] if m.get("id") == cmd["mediaId"]), None)
        if not media:
            media = next((m for m in proj["media"] if m.get("path") == cmd["mediaId"]), None)
        if not media and proj.get("media"):
            media = proj["media"][0]
        duration = media.get("duration") or 5.0 if media else 5.0
        kind = media.get("kind", "video") if media else "video"
        name = media.get("name", "Clip") if media else "Clip"
        media_id = media.get("id", cmd.get("mediaId", "m1")) if media else cmd.get("mediaId", "m1")
        start = max(0.0, float(cmd.get("start", 0.0)))
        track_id = cmd.get("trackId")
        if not track_id or not any(t["id"] == track_id for t in tl.get("tracks", [])):
            track_id = tl["tracks"][0]["id"] if tl.get("tracks") else "T1"
        tl["clips"].append(_make_clip(
            cid, kind, media_id,
            track_id, name,
            start, duration
        ))
        view["createdId"] = cid

    elif op == "addTextClip":
        cid = str(uuid.uuid4())
        style = cmd.get("style") or {}
        text_content = style.get("content") or style.get("text") or "New Text"
        text_obj = {
            "content": text_content,
            "fontFamily": style.get("fontFamily") or style.get("family") or "Inter",
            "fontSize": style.get("fontSize", 0.08),
            "fontWeight": style.get("fontWeight") or style.get("weight") or 400,
            "italic": style.get("italic", False),
            "color": style.get("color", "#ffffff"),
            "align": style.get("align", "center"),
            "opacity": style.get("opacity", 1.0),
            "strokeWidth": style.get("strokeWidth", 0.0),
            "strokeColor": style.get("strokeColor", "#000000"),
            "shadow": style.get("shadow", True),
            "background": style.get("background", ""),
            "lineHeight": style.get("lineHeight", 1.2),
            "tracking": style.get("tracking", 0.0)
        }
        track_id = cmd.get("trackId")
        if not track_id and tl.get("tracks"):
            track_id = tl["tracks"][-1]["id"]
        elif not track_id:
            track_id = "T1"
        clip = _make_clip(
            cid, "text", "", track_id,
            text_content,
            max(0.0, float(cmd.get("start", 0.0))),
            max(0.1, float(cmd.get("duration", 3.0)))
        )
        clip["text"] = text_obj
        if cmd.get("offsetY") is not None:
            clip["offsetY"] = cmd["offsetY"]
        tl["clips"].append(clip)
        view["createdId"] = cid

    elif op == "addAdjustmentClip":
        cid = str(uuid.uuid4())
        track_id = cmd.get("trackId")
        if not track_id and tl.get("tracks"):
            track_id = tl["tracks"][0]["id"]
        elif not track_id:
            track_id = "T1"
        start = max(0.0, float(cmd.get("start", 0.0)))
        duration = max(0.1, float(cmd.get("duration", 5.0)))
        adjust_count = sum(1 for c in tl.get("clips", []) if c.get("kind") == "adjustment") + 1
        clip = _make_clip(
            cid, "adjustment", "", track_id,
            f"Adjust {adjust_count}",
            start, duration
        )
        clip["adjustments"] = cmd.get("adjustments") or {
            "temp": 0, "tint": 0, "saturation": 0,
            "exposure": 0, "contrast": 0, "highlight": 0, "shadow": 0,
            "whites": 0, "blacks": 0, "brilliance": 0,
            "sharpen": 0, "clarity": 0, "particles": 0, "fade": 0, "vignette": 0,
            "lut": "None", "lutIntensity": 100
        }
        tl["clips"].append(clip)
        view["createdId"] = cid

    elif op == "setClipAdjustments":
        clip = next((c for c in tl.get("clips", []) if c["id"] == cmd.get("clipId")), None)
        if clip:
            clip["adjustments"] = {**clip.get("adjustments", {}), **cmd.get("adjustments", {})}

    elif op == "setClipAnimation":
        clip = next((c for c in tl.get("clips", []) if c["id"] == cmd.get("clipId")), None)
        if clip:
            clip["animation"] = {**clip.get("animation", {}), **cmd.get("animation", {})}

    elif op == "moveClips":
        for move in cmd.get("moves", []):
            clip = next((c for c in tl["clips"] if c["id"] == move["clipId"]), None)
            if clip:
                clip["start"] = move["start"]
                clip["trackId"] = move["trackId"]

    elif op == "trimClip":
        clip = next((c for c in tl["clips"] if c["id"] == cmd["clipId"]), None)
        if clip:
            d = cmd["delta"]
            if cmd["edge"] == "head":
                clip["start"] += d
                clip["sourceStart"] += d
                clip["duration"] -= d
            else:
                clip["duration"] += d

    elif op == "splitClips":
        new_clips = []
        for cid in cmd.get("clipIds", []):
            clip = next((c for c in tl["clips"] if c["id"] == cid), None)
            if clip and clip["start"] < cmd["time"] < (clip["start"] + clip["duration"]):
                c2 = dict(clip)
                c2["id"] = str(uuid.uuid4())
                cut = cmd["time"] - clip["start"]
                clip["duration"] = cut
                c2["start"] = cmd["time"]
                c2["sourceStart"] = c2.get("sourceStart", 0) + cut
                c2["duration"] -= cut
                new_clips.append(c2)
        tl["clips"].extend(new_clips)

    elif op == "mergeClips":
        # Merge adjacent clips back together
        ids = set(cmd.get("clipIds", []))
        targets = [c for c in tl["clips"] if c["id"] in ids]
        if len(targets) >= 2:
            targets.sort(key=lambda c: c["start"])
            merged = targets[0]
            for t in targets[1:]:
                merged["duration"] += t["duration"]
            tl["clips"] = [c for c in tl["clips"] if c["id"] not in ids or c["id"] == merged["id"]]

    elif op == "removeClips":
        ids = set(cmd.get("clipIds", []))
        tl["clips"] = [c for c in tl["clips"] if c["id"] not in ids]

    elif op == "updateClip":
        clip = next((c for c in tl["clips"] if c["id"] == cmd["clipId"]), None)
        if clip:
            clip.update(cmd.get("patch", {}))

    elif op == "setClipTransform":
        clip = next((c for c in tl["clips"] if c["id"] == cmd["clipId"]), None)
        if clip:
            for k in ["scale", "offsetX", "offsetY", "rotation"]:
                if k in cmd:
                    clip[k] = cmd[k]

    elif op == "setClipSpeed":
        clip = next((c for c in tl["clips"] if c["id"] == cmd["clipId"]), None)
        if clip:
            clip["speed"] = cmd["speed"]

    elif op == "detachAudio":
        clip = next((c for c in tl["clips"] if c["id"] == cmd["clipId"]), None)
        if clip and clip.get("kind") == "video":
            # Create a new audio-only clip linked to this one
            aid = str(uuid.uuid4())
            audio_clip = _make_clip(
                aid, "audio", clip["mediaId"],
                clip["trackId"], clip["name"] + " (Audio)",
                clip["start"], clip["duration"]
            )
            audio_clip["detachedFrom"] = clip["id"]
            tl["clips"].append(audio_clip)
            clip["muted"] = True
            view["createdId"] = aid

    elif op == "reattachAudio":
        # Find the detached audio clip and rejoin it
        clip = next((c for c in tl["clips"] if c["id"] == cmd["clipId"]), None)
        if clip:
            # If it's the audio clip, find the video
            if clip.get("detachedFrom"):
                video = next((c for c in tl["clips"] if c["id"] == clip["detachedFrom"]), None)
                if video:
                    video["muted"] = False
                tl["clips"] = [c for c in tl["clips"] if c["id"] != clip["id"]]
            else:
                # If it's the video clip, find the detached audio
                audio = next((c for c in tl["clips"] if c.get("detachedFrom") == clip["id"]), None)
                if audio:
                    clip["muted"] = False
                    tl["clips"] = [c for c in tl["clips"] if c["id"] != audio["id"]]

    elif op == "setTrackFlag":
        track = next((t for t in tl["tracks"] if t["id"] == cmd["trackId"]), None)
        if track:
            track[cmd["flag"]] = cmd["value"]

    elif op == "addTrack":
        tid = str(uuid.uuid4())
        tl["tracks"].insert(0, {"id": tid, "name": "New Track", "visible": True, "muted": False})
        view["createdId"] = tid

    elif op == "removeTrack":
        tl["tracks"] = [t for t in tl["tracks"] if t["id"] != cmd["trackId"]]

    elif op == "renameTrack":
        track = next((t for t in tl["tracks"] if t["id"] == cmd["trackId"]), None)
        if track:
            track["name"] = cmd["name"]

    elif op == "addTimeline":
        pdir_key = _active_pdir() or "default"
        tlid = _next_timeline_id(pdir_key)
        new_tl = {
            "id": tlid, "name": f"Timeline {len(proj['timelines']) + 1}",
            "tracks": [{"id": str(uuid.uuid4()), "name": f"Track {i}", "visible": True, "muted": False} for i in range(1, 5)],
            "clips": []
        }
        proj["timelines"].append(new_tl)
        proj["activeTimelineId"] = tlid
        view["createdId"] = tlid

    elif op == "removeTimeline":
        proj["timelines"] = [t for t in proj["timelines"] if t["id"] != cmd["timelineId"]]
        if proj["timelines"] and proj["activeTimelineId"] == cmd["timelineId"]:
            proj["activeTimelineId"] = proj["timelines"][0]["id"]

    elif op == "renameTimeline":
        for t in proj["timelines"]:
            if t["id"] == cmd["timelineId"]:
                t["name"] = cmd["name"]
                break

    elif op == "selectTimeline":
        proj["activeTimelineId"] = cmd["timelineId"]

    elif op == "moveTimeline":
        idx = next((i for i, t in enumerate(proj["timelines"]) if t["id"] == cmd["timelineId"]), None)
        if idx is not None:
            tl_item = proj["timelines"].pop(idx)
            new_idx = min(cmd["index"], len(proj["timelines"]))
            proj["timelines"].insert(new_idx, tl_item)

    elif op == "addFont":
        proj.setdefault("fonts", []).append({"family": cmd["family"], "path": cmd["path"]})

    elif op == "removeFont":
        proj["fonts"] = [f for f in proj.get("fonts", []) if f["family"] != cmd["family"]]

    return view


def _find_free_track(tl: dict, start: float, duration: float) -> str:
    """Find the first track that has no clip overlapping [start, start+duration)."""
    for track in tl["tracks"]:
        occupied = False
        for clip in tl["clips"]:
            if clip["trackId"] == track["id"]:
                c_end = clip["start"] + clip.get("duration", 0)
                if clip["start"] < start + duration and c_end > start:
                    occupied = True
                    break
        if not occupied:
            return track["id"]
    # All tracks occupied: use first track
    return tl["tracks"][0]["id"] if tl["tracks"] else "T1"


def _make_clip(cid: str, kind: str, media_id: str, track_id: str,
               name: str, start: float, duration: float) -> dict:
    """Create a clip dict with all required fields."""
    return {
        "id": cid, "kind": kind, "mediaId": media_id, "trackId": track_id,
        "name": name,
        "start": max(0.0, start), "duration": duration, "sourceStart": 0.0,
        "volume": 1.0, "fadeIn": 0.0, "fadeOut": 0.0,
        "speed": 1.0, "preservePitch": True,
        "scale": 1.0, "offsetX": 0.0, "offsetY": 0.0, "rotation": 0.0, "opacity": 1.0,
        "muted": False, "filters": [], "videoEffects": [],
        "adjustments": {
            "temp": 0, "tint": 0, "saturation": 0,
            "exposure": 0, "contrast": 0, "highlight": 0, "shadow": 0,
            "whites": 0, "blacks": 0, "brilliance": 0,
            "sharpen": 0, "clarity": 0, "particles": 0, "fade": 0, "vignette": 0,
            "lut": "None", "lutIntensity": 100
        },
        "animation": {"in": "none", "out": "none", "combo": "none", "duration": 0.5}
    }


def _snapshot(view: dict) -> dict:
    """Deep copy a view for the undo stack."""
    return json.loads(json.dumps(view))


def _init_session_counters(pdir: str, proj: dict):
    """Initialise media/timeline counters from existing project data."""
    max_m = 0
    for m in proj.get("media", []):
        mid = m.get("id", "")
        if mid.startswith("m") and mid[1:].isdigit():
            max_m = max(max_m, int(mid[1:]))
    media_counter[pdir] = max_m

    max_tl = 0
    for t in proj.get("timelines", []):
        tid = t.get("id", "")
        if tid.startswith("TL") and tid[2:].isdigit():
            max_tl = max(max_tl, int(tid[2:]))
    timeline_counter[pdir] = max_tl


# ── WebSocket Events Endpoint ─────────────────────────────────────────────

@router.websocket("/events")
async def ws_events(websocket: WebSocket):
    await websocket.accept()
    ws_clients.add(websocket)
    try:
        while True:
            # Keep connection alive; we push events, not receive them
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_clients.discard(websocket)
    except Exception:
        ws_clients.discard(websocket)


async def broadcast_event(event: str, payload: Any = None):
    """Send an event to all connected WebSocket clients."""
    msg = json.dumps({"event": event, "payload": payload})
    dead = set()
    for ws in ws_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    ws_clients.difference_update(dead)


# ── Media Probe ────────────────────────────────────────────────────────────

@router.post("/import_lut")
async def import_lut(file: UploadFile = File(...)):
    """Upload a custom LUT (.cube or image) to the LUTs directory."""
    luts_dir = os.path.join(_PROJECT_DIR, "processed", "luts")
    os.makedirs(luts_dir, exist_ok=True)
    filename = file.filename or f"lut_{uuid.uuid4().hex[:8]}.cube"
    dest = os.path.join(luts_dir, filename)
    with open(dest, "wb") as f:
        content = await file.read()
        f.write(content)
    lut_name = os.path.splitext(filename)[0].replace("_", " ").title()
    return {"name": lut_name, "filename": filename, "path": dest}


@router.get("/luts")
async def list_luts():
    """List available built-in and imported LUTs."""
    luts_dir = os.path.join(_PROJECT_DIR, "processed", "luts")
    os.makedirs(luts_dir, exist_ok=True)
    builtin = [
        {"name": "None", "category": "General"},
        {"name": "Cinematic Warm", "category": "Movie"},
        {"name": "Moody Teal & Orange", "category": "Movie"},
        {"name": "Vintage Film", "category": "Retro"},
        {"name": "Golden Hour", "category": "Scenery"},
        {"name": "Cyberpunk Neon", "category": "Stylized"},
        {"name": "Clean 4K Pop", "category": "General"},
        {"name": "Noir Monochrome", "category": "B&W"},
        {"name": "Pastel Dream", "category": "Stylized"},
    ]
    imported = []
    if os.path.exists(luts_dir):
        for fname in os.listdir(luts_dir):
            if fname.lower().endswith(('.cube', '.png', '.look', '.3dl')):
                name = os.path.splitext(fname)[0].replace("_", " ").title()
                imported.append({"name": name, "filename": fname, "category": "Imported"})
    return {"builtin": builtin, "imported": imported}


@router.post("/probe_media")
async def probe_media(req: dict):
    path = req["path"]
    dur = 5.0
    width, height, fps = 1920, 1080, 30.0
    fps_frac = "30/1"
    audio_codec = "aac"
    video_codec = "h264"
    has_audio = True

    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate",
             "-of", "json", path],
            capture_output=True, text=True, timeout=10
        )
        info = json.loads(result.stdout) if result.stdout.strip() else {}
        fmt = info.get("format", {})
        if fmt.get("duration"):
            dur = float(fmt["duration"])
        streams = info.get("streams", [])
        for s in streams:
            if s.get("codec_type") == "video":
                video_codec = s.get("codec_name", "h264")
                width = s.get("width", 1920)
                height = s.get("height", 1080)
                rfr = s.get("r_frame_rate", "30/1")
                fps_frac = rfr
                parts = rfr.split("/")
                if len(parts) == 2 and int(parts[1]) > 0:
                    fps = int(parts[0]) / int(parts[1])
            if s.get("codec_type") == "audio":
                audio_codec = s.get("codec_name", "aac")
    except Exception:
        pass

    is_vid = path.lower().endswith(('.mp4', '.mov', '.mkv', '.webm', '.avi', '.m4v'))
    is_img = path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff', '.avif', '.gif'))
    is_aud = path.lower().endswith(('.mp3', '.wav', '.flac', '.aac', '.m4a', '.ogg', '.opus'))
    kind = "image" if is_img else ("audio" if is_aud else "video")

    return {
        "path": path, "duration": None if is_img else dur, "kind": kind,
        "video": {
            "index": 0, "codec": video_codec, "width": width, "height": height,
            "frameRate": fps, "frameRateFraction": fps_frac
        } if kind != "audio" else None,
        "audio": {
            "index": 1, "codec": audio_codec, "sampleRate": 48000, "channels": 2
        } if kind != "image" else None
    }


# ── Engine version ─────────────────────────────────────────────────────────

@router.get("/engine_version")
async def engine_version():
    return "0.2.0-web"


# ── File upload ────────────────────────────────────────────────────────────

@router.post("/upload_media")
async def upload_media(file: UploadFile = File(...)):
    # Sanitize filename
    fname = file.filename or f"upload_{uuid.uuid4()}"
    path = os.path.join(MEDIA_DIR, fname)
    # Handle name collision
    base, ext = os.path.splitext(fname)
    counter = 1
    while os.path.exists(path):
        path = os.path.join(MEDIA_DIR, f"{base}_{counter}{ext}")
        counter += 1
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"path": path}


@router.get("/media")
async def serve_media(path: str, request: Request):
    if not os.path.exists(path) or not os.path.isfile(path):
        raise HTTPException(404, "File not found")

    file_size = os.path.getsize(path)
    content_type, _ = mimetypes.guess_type(path)
    if not content_type:
        content_type = "video/mp4" if path.lower().endswith((".mp4", ".mov", ".m4v", ".webm")) else "application/octet-stream"

    range_header = request.headers.get("range")
    if range_header:
        try:
            h = range_header.replace("bytes=", "").strip()
            parts = h.split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1
            start = max(0, min(start, file_size - 1))
            end = max(start, min(end, file_size - 1))
            chunk_length = end - start + 1

            def iter_chunk():
                with open(path, "rb") as f:
                    f.seek(start)
                    bytes_left = chunk_length
                    while bytes_left > 0:
                        read_size = min(bytes_left, 1024 * 1024)
                        data = f.read(read_size)
                        if not data:
                            break
                        bytes_left -= len(data)
                        yield data

            headers = {
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(chunk_length),
                "Content-Type": content_type,
            }
            return StreamingResponse(iter_chunk(), status_code=206, headers=headers)
        except Exception:
            pass

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(file_size),
        "Content-Type": content_type,
    }
    return FileResponse(path, headers=headers)


# ── Projects ──────────────────────────────────────────────────────────────

@router.post("/create_project")
async def create_project(req: dict):
    pid = str(uuid.uuid4())
    pdir = os.path.join(PROJECTS_DIR, pid)
    os.makedirs(pdir, exist_ok=True)
    info = {
        "path": pdir, "name": req["name"],
        "width": req.get("width", 1920), "height": req.get("height", 1080),
        "rateNum": req.get("rateNum", 30), "rateDen": req.get("rateDen", 1),
        "openedAt": int(time.time() * 1000)
    }
    with open(os.path.join(pdir, "meta.json"), "w") as f:
        json.dump(info, f)
    return info


@router.post("/open_project")
async def open_project(req: dict):
    pdir = req["path"]
    mpath = os.path.join(pdir, "meta.json")
    if os.path.exists(mpath):
        with open(mpath) as f:
            return json.load(f)
    raise HTTPException(404, "Project not found")


@router.get("/recent_projects")
async def recent_projects():
    projs = []
    if os.path.exists(PROJECTS_DIR):
        for d in os.listdir(PROJECTS_DIR):
            mpath = os.path.join(PROJECTS_DIR, d, "meta.json")
            if os.path.exists(mpath):
                try:
                    with open(mpath) as f:
                        projs.append(json.load(f))
                except Exception:
                    pass
    return sorted(projs, key=lambda p: p.get("openedAt", 0), reverse=True)


@router.post("/forget_project")
@router.post("/delete_project")
async def forget_project(req: dict):
    pdir = req.get("path", "") if isinstance(req, dict) else ""
    target_deleted = False

    # 1. Direct path check
    if pdir and os.path.exists(pdir):
        try:
            shutil.rmtree(pdir, ignore_errors=True)
            target_deleted = True
        except Exception as e:
            print(f"Error removing {pdir}: {e}")

    # 2. Check if basename / PID is in PROJECTS_DIR
    if pdir:
        pid = os.path.basename(pdir.rstrip("/\\"))
        alt_path = os.path.join(PROJECTS_DIR, pid)
        if os.path.exists(alt_path):
            try:
                shutil.rmtree(alt_path, ignore_errors=True)
                target_deleted = True
            except Exception:
                pass

    # 3. Check every project in PROJECTS_DIR to match path or name
    if os.path.exists(PROJECTS_DIR) and pdir:
        for d in os.listdir(PROJECTS_DIR):
            proj_folder = os.path.join(PROJECTS_DIR, d)
            mpath = os.path.join(proj_folder, "meta.json")
            if os.path.exists(mpath):
                try:
                    with open(mpath) as f:
                        meta = json.load(f)
                    if meta.get("path") == pdir or d == pdir or os.path.basename(meta.get("path", "")) == pid:
                        shutil.rmtree(proj_folder, ignore_errors=True)
                        target_deleted = True
                except Exception:
                    pass

    # 4. Purge from in-memory state
    for k in list(sessions.keys()):
        if k == pdir or (pdir and os.path.basename(k.rstrip("/\\")) == pid):
            sessions.pop(k, None)
            undo_stack.pop(k, None)
            redo_stack.pop(k, None)
            media_counter.pop(k, None)
            timeline_counter.pop(k, None)

    return {"status": "ok", "deleted": target_deleted}


@router.post("/project_preview")
async def project_preview(req: dict):
    return Response(content=PIXEL_PNG, media_type="image/png")


# ── Desktop dir / path helpers ────────────────────────────────────────────

@router.get("/desktop_dir")
async def get_desktop_dir():
    return {"path": os.path.expanduser("~/Desktop")}


# ── Editor Session ────────────────────────────────────────────────────────

@router.post("/editor/open")
async def editor_open(req: dict):
    pdir = req["path"]
    doc_path = os.path.join(pdir, "document.json")
    if os.path.exists(doc_path):
        with open(doc_path) as f:
            view = json.load(f)
    else:
        view = {
            "settings": {
                "name": req.get("name", "Untitled"),
                "width": req.get("width", 1920),
                "height": req.get("height", 1080),
                "rateNum": req.get("rateNum", 30),
                "rateDen": req.get("rateDen", 1)
            },
            "project": create_empty_project(
                req.get("name", "Untitled"),
                req.get("width", 1920),
                req.get("height", 1080)
            ),
            "canUndo": False,
            "canRedo": False,
        }
    sessions[pdir] = view
    undo_stack[pdir] = []
    redo_stack[pdir] = []
    _init_session_counters(pdir, view.get("project", {}))
    return view


@router.post("/editor/apply")
async def editor_apply(req: dict):
    pdir = _active_pdir()
    if not pdir:
        raise HTTPException(400, "No editor session open")
    view = sessions[pdir]

    cmd = req.get("command", {})
    # Push current state to undo stack
    undo_stack.setdefault(pdir, []).append(_snapshot(view))
    redo_stack[pdir] = []  # Clear redo on new action

    # Cap undo history at 100 steps
    if len(undo_stack[pdir]) > 100:
        undo_stack[pdir] = undo_stack[pdir][-100:]

    new_view = _snapshot(view)
    new_view = apply_command(new_view, cmd, pdir)
    new_view["canUndo"] = len(undo_stack.get(pdir, [])) > 0
    new_view["canRedo"] = False
    sessions[pdir] = new_view
    return new_view


@router.post("/editor/undo")
async def editor_undo():
    pdir = _active_pdir()
    if not pdir:
        raise HTTPException(400, "No editor session open")
    stack = undo_stack.get(pdir, [])
    if not stack:
        return sessions[pdir]
    # Push current state to redo
    redo_stack.setdefault(pdir, []).append(_snapshot(sessions[pdir]))
    prev = stack.pop()
    prev["canUndo"] = len(stack) > 0
    prev["canRedo"] = True
    sessions[pdir] = prev
    return prev


@router.post("/editor/redo")
async def editor_redo():
    pdir = _active_pdir()
    if not pdir:
        raise HTTPException(400, "No editor session open")
    stack = redo_stack.get(pdir, [])
    if not stack:
        return sessions[pdir]
    # Push current state to undo
    undo_stack.setdefault(pdir, []).append(_snapshot(sessions[pdir]))
    nxt = stack.pop()
    nxt["canUndo"] = True
    nxt["canRedo"] = len(stack) > 0
    sessions[pdir] = nxt
    return nxt


@router.post("/editor/save")
async def editor_save(req: dict):
    pdir = _active_pdir()
    if not pdir:
        return {}
    view = sessions[pdir]
    # Update settings if provided
    if req and view.get("settings"):
        if req.get("width"):
            view["settings"]["width"] = req["width"]
        if req.get("height"):
            view["settings"]["height"] = req["height"]
        if req.get("name"):
            view["settings"]["name"] = req["name"]
    os.makedirs(pdir, exist_ok=True)
    with open(os.path.join(pdir, "document.json"), "w") as f:
        json.dump(view, f)
    return {}


@router.get("/editor/state")
async def editor_state():
    pdir = _active_pdir()
    if not pdir:
        raise HTTPException(400, "No editor session open")
    return sessions[pdir]


@router.post("/editor/close")
async def editor_close():
    pdir = _active_pdir()
    if pdir:
        sessions.pop(pdir, None)
        undo_stack.pop(pdir, None)
        redo_stack.pop(pdir, None)
    return {}


# ── Export to CapCut ──────────────────────────────────────────────────────

@router.post("/export")
async def export_project(req: dict):
    pdir = _active_pdir()
    if not pdir:
        return "No active session"
    view = sessions[pdir]
    proj = view["project"]
    tl = proj["timelines"][0] if proj["timelines"] else {"tracks": [], "clips": []}

    capcut = {
        "materials": {"videos": [], "audios": [], "texts": []},
        "tracks": []
    }

    for m in proj.get("media", []):
        capcut["materials"]["videos"].append({
            "id": m.get("id", ""), "path": m.get("path", ""),
            "type": "video" if m.get("kind") == "video" else "photo"
        })

    for track in tl.get("tracks", []):
        t_clips = [c for c in tl.get("clips", []) if c["trackId"] == track["id"]]
        if not t_clips:
            continue
        c_track = {"type": "video", "segments": []}
        for c in t_clips:
            if c.get("kind") in ("video", "image"):
                c_track["segments"].append({
                    "material_id": c["mediaId"],
                    "source_timerange": {"start": int(c.get("sourceStart", 0) * 1e6), "duration": int(c["duration"] * 1e6)},
                    "target_timerange": {"start": int(c["start"] * 1e6), "duration": int(c["duration"] * 1e6)}
                })
        if c_track["segments"]:
            capcut["tracks"].append(c_track)

    export_dir = os.path.join(pdir, "CapCut_Export")
    os.makedirs(export_dir, exist_ok=True)
    with open(os.path.join(export_dir, "draft_content.json"), "w") as f:
        json.dump(capcut, f, indent=2)

    meta_info = {
        "draft_materials": [],
        "draft_name": req.get("request", {}).get("output", "WolfCut_Export").split("/")[-1],
        "draft_root_path": "", "draft_timeline_materials_size": 0
    }
    with open(os.path.join(export_dir, "draft_meta_info.json"), "w") as f:
        json.dump(meta_info, f, indent=2)

    zip_path = os.path.join(pdir, "CapCut_Project.zip")
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.write(os.path.join(export_dir, "draft_content.json"), arcname="draft_content.json")
        zf.write(os.path.join(export_dir, "draft_meta_info.json"), arcname="draft_meta_info.json")

    return zip_path


@router.post("/export/cancel")
async def cancel_export():
    return {}


# ── Media bytes / filmstrip / peaks ───────────────────────────────────────

@router.post("/read_media_bytes")
async def read_media_bytes(req: dict):
    path = req.get("path", "")
    if os.path.exists(path):
        return FileResponse(path, media_type="application/octet-stream")
    return Response(content=b"", media_type="application/octet-stream")


@router.post("/extract_filmstrip")
async def extract_filmstrip(req: dict):
    path = req.get("path", "")
    count = req.get("count", 1)
    height = req.get("height", 40)

    # Try to generate real filmstrip using ffmpeg
    if os.path.exists(path):
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", path],
                capture_output=True, text=True, timeout=5
            )
            dur = float(result.stdout.strip()) if result.stdout.strip() else 5.0
            # Calculate aspect ratio for width
            width = int(height * 16 / 9)
            # Generate a filmstrip: extract frames and tile horizontally
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name
            # Use ffmpeg to extract N frames and tile them
            subprocess.run(
                ["ffmpeg", "-y", "-i", path,
                 "-vf", f"fps={count}/{dur},scale={width}:{height},tile={count}x1",
                 "-frames:v", "1", tmp_path],
                capture_output=True, timeout=15
            )
            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                with open(tmp_path, "rb") as f:
                    data = f.read()
                os.unlink(tmp_path)
                return Response(content=data, media_type="image/png")
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass

    return Response(content=PIXEL_PNG, media_type="image/png")


@router.post("/extract_peaks")
async def extract_peaks(req: dict):
    # Return empty waveform data
    return Response(content=b"\x00" * 256, media_type="application/octet-stream")


# ── Artwork / Cache ───────────────────────────────────────────────────────

@router.get("/artwork/{project:path}/{key}")
async def read_artwork(project: str, key: str):
    art_path = os.path.join(project, "artwork", key)
    if os.path.exists(art_path):
        return FileResponse(art_path, media_type="application/octet-stream")
    return Response(content=PIXEL_PNG, media_type="image/png")


@router.post("/write_artwork")
async def write_artwork(
    project: str = Form(...),
    key: str = Form(...),
    data: UploadFile = File(...)
):
    art_dir = os.path.join(project, "artwork")
    os.makedirs(art_dir, exist_ok=True)
    art_path = os.path.join(art_dir, key)
    with open(art_path, "wb") as f:
        shutil.copyfileobj(data.file, f)
    return {}


# ── Audio / Transport ────────────────────────────────────────────────────

@router.post("/audio_set_clips")
async def audio_set_clips(req: dict):
    return {}

@router.post("/transport_play")
async def transport_play(req: dict):
    return {}

@router.post("/transport_pause")
async def transport_pause():
    return {}

@router.post("/transport_seek")
async def transport_seek(req: dict):
    return {}


# ── Preview ───────────────────────────────────────────────────────────────

@router.post("/preview_frame")
async def preview_frame(req: dict):
    """
    Generate a preview frame. For now returns a placeholder.
    In a full implementation this would composite the timeline at a given time.
    """
    return Response(content=PIXEL_PNG, media_type="image/png")


@router.post("/preview_prefetch")
async def preview_prefetch(req: dict):
    return {}


# ── Templates ─────────────────────────────────────────────────────────────

@router.get("/templates")
async def template_list():
    return []


@router.post("/templates/save")
async def template_save(req: dict):
    pdir = _active_pdir()
    return {
        "path": pdir or "", "name": req.get("name", "Template"),
        "width": 1920, "height": 1080, "rateNum": 30, "rateDen": 1,
        "slots": [], "hasPoster": False
    }


@router.post("/templates/instantiate")
async def template_instantiate(req: dict):
    # Create a new project from template
    return await create_project({
        "name": req.get("name", "From Template"),
        "location": req.get("location", ""),
        "width": 1920, "height": 1080, "rateNum": 30, "rateDen": 1
    })


@router.post("/templates/delete")
async def template_delete(req: dict):
    return {}


@router.post("/templates/poster")
async def template_poster(req: dict):
    return Response(content=PIXEL_PNG, media_type="image/png")


# ── Transcription stubs ──────────────────────────────────────────────────

@router.get("/transcribe/status")
async def transcriber_status():
    return {
        "binary": None, "bundled": False,
        "modelsDir": "", "models": []
    }

@router.post("/transcribe/set_binary")
async def set_transcriber_binary(req: dict):
    return await transcriber_status()

@router.post("/transcribe/download_model")
async def download_transcriber_model(req: dict):
    return {}

@router.post("/transcribe/cancel_download")
async def cancel_model_download():
    return {}

@router.post("/transcribe/delete_model")
async def delete_transcriber_model(req: dict):
    return {}

@router.post("/transcribe/clip")
async def transcribe_clip(req: dict):
    return []

@router.post("/transcribe/cancel")
async def cancel_transcribe():
    return {}


# ── TTS stubs ────────────────────────────────────────────────────────────

@router.get("/tts/status")
async def tts_status():
    return {"modelsDir": "", "models": [], "voices": []}

@router.post("/tts/download_model")
async def download_tts_model(req: dict):
    return {}

@router.post("/tts/cancel_download")
async def cancel_tts_model_download():
    return {}

@router.post("/tts/delete_model")
async def delete_tts_model(req: dict):
    return {}

@router.post("/tts/speak")
async def speak_text(req: dict):
    return {"path": "", "duration": 0}

@router.post("/tts/cancel")
async def cancel_speak():
    return {}
