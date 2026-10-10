path = "scratch/WolfCut/desktop/src/components/MediaBin.tsx"
with open(path) as f:
    text = f.read()

# Add a quick '+' button right next to the slot and close button on hover, and make click / double click very clear
add_btn_code = """                <button
                  type="button"
                  title="Add to timeline"
                  onClick={(event) => {
                    event.stopPropagation();
                    onAddToTimeline(item.id);
                  }}
                  className="invisible absolute left-1 bottom-1 cursor-pointer rounded bg-accent/80 p-1
                             text-white transition-colors hover:bg-accent group-hover:visible"
                >
                  <Icon name="plus" size={10} />
                </button>
"""

if 'title="Add to timeline"' not in text:
    text = text.replace('{/* The slot state stays visible;', add_btn_code + '\n                {/* The slot state stays visible;')

with open(path, "w") as f:
    f.write(text)

print("✅ Added quick Add-to-timeline button to Media cards")
