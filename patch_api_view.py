import re
path = "/Users/daras/Documents/Codex/Depth Video/backend/wolfcut_api.py"
with open(path) as f:
    t = f.read()

# Add missing fields to EditorView
replacement = """        view = {
            "settings": {"name": req["name"], "width": req["width"], "height": req["height"], "rateNum": req["rateNum"], "rateDen": req["rateDen"]},
            "project": create_empty_project(req["name"], req["width"], req["height"]),
            "canUndo": False,
            "canRedo": False,
            "createdId": None
        }"""
t = re.sub(r'        view = \{\n\s+"settings".*?"createdId": None\n\s+\}', replacement, t, flags=re.DOTALL)
with open(path, "w") as f:
    f.write(t)
print("✅ EditorView patched")
