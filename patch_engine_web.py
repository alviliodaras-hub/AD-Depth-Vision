path = "scratch/WolfCut/desktop/src/lib/engine-web.ts"
with open(path) as f:
    text = f.read()

# Make sure openFilePicker handles both single and multiple correctly and uses correct URL
text = text.replace(
    "const res = await fetch(`${API}/upload_media`, { method: \"POST\", body: fd });",
    "const res = await fetch(`${API}/upload_media`, { method: \"POST\", body: fd });\n        if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`);"
)

with open(path, "w") as f:
    f.write(text)
print("✅ engine-web.ts updated")
