import re

path = "/Users/daras/Documents/Codex/Depth Video/backend/wolfcut_api.py"
with open(path) as f:
    t = f.read()

# Replace the export logic to zip the CapCut project and return the zip path
replacement = """    export_dir = os.path.join(pdir, "CapCut_Export")
    os.makedirs(export_dir, exist_ok=True)
    with open(os.path.join(export_dir, "draft_content.json"), "w") as f:
        json.dump(capcut, f, indent=2)
        
    meta_info = {
        "draft_materials": [],
        "draft_name": req.get("request", {}).get("output", "WolfCut_Export").split("/")[-1],
        "draft_root_path": "",
        "draft_timeline_materials_size": 0
    }
    with open(os.path.join(export_dir, "draft_meta_info.json"), "w") as f:
        json.dump(meta_info, f, indent=2)

    zip_path = os.path.join(pdir, "CapCut_Project.zip")
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.write(os.path.join(export_dir, "draft_content.json"), arcname="draft_content.json")
        zf.write(os.path.join(export_dir, "draft_meta_info.json"), arcname="draft_meta_info.json")
        
    return zip_path"""

t = re.sub(r'    export_dir = os\.path\.join\(pdir, "CapCut_Export"\)\n.*?\n    return export_dir', replacement, t, flags=re.DOTALL)

with open(path, "w") as f:
    f.write(t)
print("✅ CapCut zip export patched")
