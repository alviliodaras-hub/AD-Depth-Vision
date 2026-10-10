path = "scratch/WolfCut/desktop/src/components/MediaBin.tsx"
with open(path) as f:
    text = f.read()

# 1. Update beginMarquee so that it strictly ignores when target is inside a data-media-card
old_marquee = """  const beginMarquee = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    if ((event.target as Element).closest("[data-media-card]")) return;"""

new_marquee = """  const beginMarquee = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    const target = event.target as Element | null;
    if (target?.closest("[data-media-card]") || target?.closest("button") || target?.closest("input")) return;"""

text = text.replace(old_marquee, new_marquee)

# 2. Update beginDrag:
# Make threshold lower (2px) and stopPropagation on pointerdown
old_begin_drag = """  const beginDrag = (event: ReactPointerEvent<HTMLLIElement>, item: MediaItem) => {
    if (event.button !== 0) return;
    const originX = event.clientX;
    const originY = event.clientY;

    const onMove = (moveEvent: PointerEvent) => {
      if (Math.hypot(moveEvent.clientX - originX, moveEvent.clientY - originY) <= 4) return;
      cleanup();
      onBeginDrag(item, moveEvent.clientX, moveEvent.clientY);
    };
    const cleanup = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", cleanup);
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", cleanup);
  };"""

new_begin_drag = """  const beginDrag = (event: ReactPointerEvent<HTMLLIElement>, item: MediaItem) => {
    if (event.button !== 0) return;
    // Don't drag if clicking action buttons
    if ((event.target as Element).closest("button")) return;
    
    event.stopPropagation();
    const originX = event.clientX;
    const originY = event.clientY;

    const onMove = (moveEvent: PointerEvent) => {
      if (Math.hypot(moveEvent.clientX - originX, moveEvent.clientY - originY) <= 2) return;
      cleanup();
      onBeginDrag(item, moveEvent.clientX, moveEvent.clientY);
    };
    const cleanup = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", cleanup);
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", cleanup);
  };"""

text = text.replace(old_begin_drag, new_begin_drag)

with open(path, "w") as f:
    f.write(text)

print("✅ Drag and Marquee handlers patched in MediaBin.tsx")
