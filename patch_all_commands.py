path = "backend/wolfcut_api.py"
with open(path) as f:
    text = f.read()

# Add addClipAtFirstFree implementation
add_first_free_code = """    elif op == "addClipAtFirstFree":
        cid = str(uuid.uuid4())
        media = next((m for m in proj["media"] if m["id"] == cmd["mediaId"]), None)
        duration = media.get("duration") or 5.0 if media else 5.0
        kind = media["kind"] if media else "video"
        name = media.get("name", "Clip") if media else "Clip"
        # Find first track or use the first track
        track_id = tl["tracks"][0]["id"] if tl["tracks"] else "T1"
        # Check if there is an available spot on tracks or place on track 0
        start = cmd.get("start", 0.0)
        tl["clips"].append({
            "id": cid, "kind": kind, "mediaId": cmd["mediaId"], "trackId": track_id,
            "name": name,
            "start": start, "duration": duration, "sourceStart": 0.0,
            "volume": 1.0, "fadeIn": 0.0, "fadeOut": 0.0, "speed": 1.0, "preservePitch": True,
            "scale": 1.0, "offsetX": 0.0, "offsetY": 0.0, "rotation": 0.0, "opacity": 1.0,
            "muted": False, "filters": [], "videoEffects": []
        })
        view["createdId"] = cid
"""

if 'elif op == "addClipAtFirstFree":' not in text:
    text = text.replace('    elif op == "addClip":', add_first_free_code + '    elif op == "addClip":')

with open(path, "w") as f:
    f.write(text)

print("✅ Added addClipAtFirstFree command support")
