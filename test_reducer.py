import sys
sys.path.insert(0, '/Users/daras/Documents/Codex/Depth Video')

import json
# We only want to test the reducer logic
with open('/Users/daras/Documents/Codex/Depth Video/backend/wolfcut_api.py') as f:
    code = f.read()
    # Strip out fastapi dependencies
    code = code.replace("from fastapi", "# from fastapi")
    code = code.replace("from pydantic", "# from pydantic")
    code = code.replace("@router.", "# @router.")
    code = code.replace("UploadFile = File(...)", "file = None")
    
    exec(code, globals())

# Now run the test locally on the functions
print("1. Create empty project")
proj = create_empty_project("Test", 1920, 1080)
view = {
    "settings": {"name": "Test", "width": 1920, "height": 1080, "rateNum": 30, "rateDen": 1},
    "project": proj,
    "canUndo": False,
    "canRedo": False,
    "createdId": None
}

print("2. Add Media")
media_item = {
    "id": "m1", "path": "dummy.mp4", "name": "dummy.mp4", "duration": 5.0, "kind": "video",
    "width": 1920, "height": 1080, "frameRate": 30, "frameRateFraction": "30/1",
    "videoCodec": "h264", "audioCodec": "aac", "hasAudio": True
}
view = apply_command(view, {"op": "addMedia", "item": media_item})
assert len(view["project"]["media"]) == 1

print("3. Add Clip")
view = apply_command(view, {"op": "addClip", "mediaId": "m1", "trackId": "T1", "start": 0.0})
clips = view["project"]["timelines"][0]["clips"]
assert len(clips) == 1
clip_id = clips[0]["id"]
assert clips[0]["name"] == "dummy.mp4"

print("4. Set Transform")
view = apply_command(view, {"op": "setClipTransform", "clipId": clip_id, "offsetX": 0.5, "scale": 1.5})
assert clips[0]["offsetX"] == 0.5
assert clips[0]["scale"] == 1.5

print("5. Add Text")
view = apply_command(view, {"op": "addTextClip", "trackId": "T2", "start": 2.0})
clips = view["project"]["timelines"][0]["clips"]
assert len(clips) == 2
assert clips[1]["kind"] == "text"
assert clips[1]["name"] == "New Text"

print("✅ Reducer logic is perfect!")
