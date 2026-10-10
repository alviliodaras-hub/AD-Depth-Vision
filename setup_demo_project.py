import os
import json
import uuid
import time
import shutil

PROJECTS_DIR = os.path.join("processed", "wolfcut_projects")
MEDIA_DIR = os.path.join("uploads", "wolfcut_media")
os.makedirs(PROJECTS_DIR, exist_ok=True)
os.makedirs(MEDIA_DIR, exist_ok=True)

# 1. Check if there are sample videos/images in uploads or processed
sample_media = []
for root, dirs, files in os.walk("."):
    if "scratch" in root or ".git" in root or "node_modules" in root:
        continue
    for f in files:
        if f.lower().endswith((".mp4", ".mov", ".png", ".jpg")):
            full_path = os.path.abspath(os.path.join(root, f))
            # copy to wolfcut_media
            target = os.path.join(MEDIA_DIR, f)
            shutil.copyfile(full_path, target)
            kind = "image" if f.lower().endswith((".png", ".jpg")) else "video"
            sample_media.append({
                "id": "demo_" + str(uuid.uuid4())[:8],
                "path": target,
                "name": f,
                "duration": 5.0 if kind == "image" else 8.0,
                "kind": kind,
                "width": 1920,
                "height": 1080,
                "frameRate": 30,
                "frameRateFraction": "30/1",
                "videoCodec": "h264",
                "audioCodec": "aac",
                "hasAudio": kind != "image"
            })
            if len(sample_media) >= 3:
                break
    if len(sample_media) >= 3:
        break

# Create Demo Project (CapCut Style Sample)
demo_pid = "demo_capcut_style"
pdir = os.path.join(PROJECTS_DIR, demo_pid)
os.makedirs(pdir, exist_ok=True)

info = {
    "path": os.path.abspath(pdir),
    "name": "✨ CapCut Style Demo Project",
    "width": 1920,
    "height": 1080,
    "rateNum": 30,
    "rateDen": 1,
    "openedAt": int(time.time() * 1000)
}
with open(os.path.join(pdir, "meta.json"), "w") as f:
    json.dump(info, f, indent=2)

# Build Tracks and Clips
tracks = [
    {"id": "T1", "name": "Text & Titles", "visible": True, "muted": False},
    {"id": "T2", "name": "Overlays & Effects", "visible": True, "muted": False},
    {"id": "T3", "name": "Main Video", "visible": True, "muted": False},
    {"id": "T4", "name": "Background Music", "visible": True, "muted": False}
]

clips = []
start_pos = 0.0

for i, m in enumerate(sample_media):
    cid = f"clip_{i+1}"
    dur = m["duration"]
    clips.append({
        "id": cid,
        "kind": m["kind"],
        "mediaId": m["id"],
        "trackId": "T3",
        "name": m["name"],
        "start": start_pos,
        "duration": dur,
        "sourceStart": 0.0,
        "volume": 1.0,
        "fadeIn": 0.5 if i == 0 else 0.0,
        "fadeOut": 0.5 if i == len(sample_media) - 1 else 0.0,
        "speed": 1.0,
        "preservePitch": True,
        "scale": 1.0,
        "offsetX": 0.0,
        "offsetY": 0.0,
        "rotation": 0.0,
        "opacity": 1.0,
        "muted": False,
        "filters": [],
        "videoEffects": []
    })
    start_pos += dur

# Add text title sample
clips.append({
    "id": "text_title_demo",
    "kind": "text",
    "mediaId": "",
    "trackId": "T1",
    "name": "CAPCUT AI PREVIEW",
    "start": 0.5,
    "duration": 4.0,
    "sourceStart": 0.0,
    "volume": 1.0,
    "fadeIn": 0.0,
    "fadeOut": 0.0,
    "speed": 1.0,
    "preservePitch": True,
    "scale": 1.2,
    "offsetX": 0.0,
    "offsetY": -0.3,
    "rotation": 0.0,
    "opacity": 1.0,
    "muted": False,
    "filters": [],
    "videoEffects": [],
    "text": {
        "text": "CAPCUT AI PREVIEW",
        "family": "Cabinet Grotesk",
        "weight": 800,
        "italic": False,
        "color": "#00f0ff"
    }
})

doc = {
    "settings": {
        "name": "✨ CapCut Style Demo Project",
        "width": 1920,
        "height": 1080,
        "rateNum": 30,
        "rateDen": 1
    },
    "project": {
        "media": sample_media,
        "fonts": [],
        "activeTimelineId": "TL1",
        "timelines": [{
            "id": "TL1",
            "name": "Main Timeline",
            "tracks": tracks,
            "clips": clips
        }]
    },
    "canUndo": True,
    "canRedo": False,
    "createdId": None
}

with open(os.path.join(pdir, "document.json"), "w") as f:
    json.dump(doc, f, indent=2)

print("✅ Demo CapCut-style project successfully created!")
