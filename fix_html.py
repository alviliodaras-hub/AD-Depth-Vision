with open("/Users/daras/Documents/Codex/Depth Video/frontend/index.html", "r") as f:
    text = f.read()

# I messed up by leaving </div></div> in the middle of the mode-options cards.
# First, I will remove the stray </div></div>
bad_part = """                    </label>
                </div>
            </div>
                    <label class="mode-card" data-mode="autocut">"""

good_part = """                    </label>
                    <label class="mode-card" data-mode="autocut">"""

text = text.replace(bad_part, good_part)

with open("/Users/daras/Documents/Codex/Depth Video/frontend/index.html", "w") as f:
    f.write(text)

print("✅ index.html structure fixed")
