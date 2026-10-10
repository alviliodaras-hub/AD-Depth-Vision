import re

path = "/Users/daras/Documents/Codex/Depth Video/frontend/index.html"
with open(path) as f:
    t = f.read()

# Fix the playground card that was mangled
t = t.replace("""<p>Interactive 3D WebGL Visualization</p>
                        </div>
                    </label>
                    
                    <!-- NEW: Video Editor mode card -->
                    <label class="mode-card" id="launch-editor-card" style="cursor: pointer;">
                        <div class="mode-icon">✂️</div>
                        <div class="mode-info">
                            <strong>Video Editor</strong>
                            <p>Multi-track Timeline Editor</p>
                        </div>
                    </label>
                </div>
            </div>
                            <p>Interactive 3D Blocking & Previz Scene</p>
                        </div>
                    </label>""", """<p>Interactive 3D Blocking & Previz Scene</p>
                        </div>
                    </label>
                    
                    <!-- NEW: Video Editor mode card -->
                    <label class="mode-card" id="launch-editor-card" style="cursor: pointer;" onclick="window.open('/editor/', '_blank')">
                        <div class="mode-icon">✂️</div>
                        <div class="mode-info">
                            <strong>Video Editor</strong>
                            <p>Multi-track Timeline Editor</p>
                        </div>
                    </label>
                </div>
            </div>""")

with open(path, "w") as f:
    f.write(t)
print("✅ index.html mangled part fixed")
