import re
path = "/Users/daras/Documents/Codex/Depth Video/backend/wolfcut_api.py"
with open(path) as f:
    t = f.read()

replacement_add_clip = """        tl["clips"].append({
            "id": cid, "kind": media["kind"], "mediaId": cmd["mediaId"], "trackId": cmd["trackId"],
            "name": media.get("name", "Clip"),
            "start": cmd["start"], "duration": duration, "sourceStart": 0.0,
            "volume": 1.0, "fadeIn": 0.0, "fadeOut": 0.0, "speed": 1.0, "preservePitch": True,
            "scale": 1.0, "offsetX": 0.0, "offsetY": 0.0, "rotation": 0.0, "opacity": 1.0,
            "muted": False, "filters": [], "videoEffects": []
        })"""

t = re.sub(r'        tl\["clips"\].append\(\{\n\s+"id": cid, "kind": media\["kind"\].*?"muted": False, "filters": \[\]\n\s+\}\)', replacement_add_clip, t, flags=re.DOTALL)

replacement_text_clip = """        tl["clips"].append({
            "id": cid, "kind": "text", "mediaId": "", "trackId": cmd["trackId"] or tl["tracks"][-1]["id"],
            "name": cmd.get("style", {}).get("text", "Text"),
            "start": cmd["start"], "duration": cmd.get("duration", 3.0), "sourceStart": 0.0,
            "volume": 1.0, "fadeIn": 0.0, "fadeOut": 0.0, "speed": 1.0, "preservePitch": True,
            "scale": 1.0, "offsetX": 0.0, "offsetY": cmd.get("offsetY", 0.0), "rotation": 0.0, "opacity": 1.0,
            "muted": False, "filters": [], "videoEffects": [],
            "text": cmd.get("style", {})
        })"""

t = re.sub(r'        tl\["clips"\].append\(\{\n\s+"id": cid, "kind": "text",.*?"style": cmd.get\("style", \{\}\)\n\s+\}\)', replacement_text_clip, t, flags=re.DOTALL)

with open(path, "w") as f:
    f.write(t)
print("✅ Clip schema patched")
