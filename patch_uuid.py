path = "backend/wolfcut_api.py"
with open(path) as f:
    text = f.read()

# Replace import uuid inside addTrack with just standard usage since uuid is at top of file
text = text.replace("    elif op == \"addTrack\":\n        import uuid\n", "    elif op == \"addTrack\":\n")

with open(path, "w") as f:
    f.write(text)
print("✅ Removed shadowed local import uuid")
