import sys
sys.path.insert(0, '/Users/daras/Documents/Codex/Depth Video')

import asyncio
from backend.wolfcut_api import editor_open, editor_apply, probe_media, extract_filmstrip

async def run_test():
    print("1. Opening project...")
    view = await editor_open({
        "path": "/Users/daras/Documents/Codex/Depth Video/processed/wolfcut_projects/test1",
        "name": "Test Project",
        "width": 1920,
        "height": 1080,
        "rateNum": 30,
        "rateDen": 1
    })
    assert view["settings"]["name"] == "Test Project"
    
    print("2. Probing media...")
    media_info = await probe_media({"path": "dummy.mp4"})
    assert media_info["duration"] == 5.0
    
    print("3. Adding media to bin...")
    media_item = {
        "id": "m1",
        "path": "dummy.mp4",
        "name": "dummy.mp4",
        "duration": 5.0,
        "kind": "video",
        "width": 1920,
        "height": 1080,
        "frameRate": 30,
        "frameRateFraction": "30/1",
        "videoCodec": "h264",
        "audioCodec": "aac",
        "hasAudio": True
    }
    view = await editor_apply({"command": {"op": "addMedia", "item": media_item}})
    assert len(view["project"]["media"]) == 1
    
    print("4. Adding clip to timeline...")
    view = await editor_apply({"command": {
        "op": "addClip", 
        "mediaId": "m1",
        "trackId": "T1",
        "start": 0.0
    }})
    clips = view["project"]["timelines"][0]["clips"]
    assert len(clips) == 1
    clip_id = clips[0]["id"]
    
    print("5. Moving clip...")
    view = await editor_apply({"command": {
        "op": "setClipTransform",
        "clipId": clip_id,
        "offsetX": 0.5,
        "scale": 1.5
    }})
    clips = view["project"]["timelines"][0]["clips"]
    assert clips[0]["offsetX"] == 0.5
    assert clips[0]["scale"] == 1.5
    
    print("6. Adding Text...")
    view = await editor_apply({"command": {
        "op": "addTextClip",
        "trackId": "T2",
        "start": 2.0
    }})
    clips = view["project"]["timelines"][0]["clips"]
    assert len(clips) == 2
    assert clips[1]["kind"] == "text"
    assert clips[1]["name"] == "New Text"
    
    print("7. Extract filmstrip...")
    fs = await extract_filmstrip({"path": "dummy.mp4", "count": 10, "height": 50})
    assert fs.media_type == "image/png"
    
    print("✅ ALL TESTS PASSED!")

asyncio.run(run_test())
