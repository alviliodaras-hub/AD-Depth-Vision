import re
path = "/Users/daras/Documents/Codex/Depth Video/backend/wolfcut_api.py"
with open(path) as f:
    t = f.read()

extra_ops = """    elif op == "setClipSpeed":
        clip = next((c for c in tl["clips"] if c["id"] == cmd["clipId"]), None)
        if clip:
            clip["speed"] = cmd["speed"]
    elif op == "setTrackFlag":
        track = next((t for t in tl["tracks"] if t["id"] == cmd["trackId"]), None)
        if track:
            track[cmd["flag"]] = cmd["value"]
    elif op == "addTrack":
        import uuid
        tl["tracks"].insert(0, {"id": str(uuid.uuid4()), "name": "New Track", "visible": True, "muted": False})
    elif op == "removeTrack":
        tl["tracks"] = [t for t in tl["tracks"] if t["id"] != cmd["trackId"]]
    elif op == "renameTrack":
        track = next((t for t in tl["tracks"] if t["id"] == cmd["trackId"]), None)
        if track:
            track["name"] = cmd["name"]
    elif op == "removeMedia":
        proj["media"] = [m for m in proj["media"] if m["id"] != cmd["mediaId"]]
"""

if 'elif op == "setClipSpeed":' not in t:
    t = t.replace('    elif op == "updateClip":', extra_ops + '    elif op == "updateClip":')

with open(path, "w") as f:
    f.write(t)
print("✅ Extra ops patched")
