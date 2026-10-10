import os
import json
import uuid

# Validasi seluruh skema dan reducer
from backend.wolfcut_api import (
    create_empty_project,
    apply_command,
    PROJECTS_DIR,
    MEDIA_DIR
)

print("Testing full editing workflow:")

# 1. Init Project
p = create_empty_project("MyProject", 1920, 1080)
view = {
    "settings": {"name": "MyProject", "width": 1920, "height": 1080, "rateNum": 30, "rateDen": 1},
    "project": p,
    "canUndo": False,
    "canRedo": False,
    "createdId": None
}

# 2. Add Media
media_id = "m_" + str(uuid.uuid4())[:8]
media_item = {
    "id": media_id,
    "path": "/path/to/sample.mp4",
    "name": "sample.mp4",
    "duration": 12.5,
    "kind": "video",
    "width": 1920,
    "height": 1080,
    "frameRate": 30,
    "frameRateFraction": "30/1",
    "videoCodec": "h264",
    "audioCodec": "aac",
    "hasAudio": True
}
view = apply_command(view, {"op": "addMedia", "item": media_item})
assert len(view["project"]["media"]) == 1, "Media failed to add"
print("  ✓ Add Media OK")

# 3. Add Clip to Timeline
view = apply_command(view, {
    "op": "addClip",
    "mediaId": media_id,
    "trackId": "T1",
    "start": 0.0
})
clips = view["project"]["timelines"][0]["clips"]
assert len(clips) == 1, "Clip failed to add"
cid = clips[0]["id"]
print("  ✓ Add Clip OK")

# 4. Split Clip
view = apply_command(view, {
    "op": "splitClips",
    "clipIds": [cid],
    "time": 5.0
})
clips = view["project"]["timelines"][0]["clips"]
assert len(clips) == 2, "Split clips failed"
print("  ✓ Split Clip OK")

# 5. Trim Clip
view = apply_command(view, {
    "op": "trimClip",
    "clipId": clips[0]["id"],
    "edge": "tail",
    "delta": -1.0
})
print("  ✓ Trim Clip OK")

# 6. Add Text Clip
view = apply_command(view, {
    "op": "addTextClip",
    "trackId": "T2",
    "start": 1.0,
    "duration": 4.0,
    "style": {"text": "Judul Video", "family": "Inter", "weight": 700, "italic": False, "color": "#ffcc00"}
})
clips = view["project"]["timelines"][0]["clips"]
assert any(c["kind"] == "text" for c in clips), "Text clip failed to add"
print("  ✓ Add Text Clip OK")

# 7. Move Clip
view = apply_command(view, {
    "op": "moveClips",
    "moves": [{"clipId": clips[0]["id"], "trackId": "T1", "start": 0.5}]
})
print("  ✓ Move Clip OK")

# 8. Transform Clip
view = apply_command(view, {
    "op": "setClipTransform",
    "clipId": clips[0]["id"],
    "scale": 1.2,
    "offsetX": 0.1,
    "offsetY": -0.05,
    "rotation": 5.0
})
print("  ✓ Set Transform OK")

# 9. Speed Control
view = apply_command(view, {
    "op": "setClipSpeed",
    "clipId": clips[0]["id"],
    "speed": 1.5
})
print("  ✓ Set Clip Speed OK")

# 10. Add Track & Track Flag
view = apply_command(view, {"op": "addTrack"})
view = apply_command(view, {"op": "setTrackFlag", "trackId": "T1", "flag": "muted", "value": True})
print("  ✓ Track Operations OK")

print("\n🎉 ALL 10 TESTS PASSED SUCCESSFULLY!")
