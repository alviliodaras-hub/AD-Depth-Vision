// blocking.js - Handles Top-Down Blocking Editor Logic

const blockingState = {
    projectBgTag: "",
    entities: {}, // { id: { type, label, assetTag, elem, defaultFov } }
    keyframes: {
        director: {} // { timeStr: { activeCamera, activeShot, shotBgTag } }
    },
    duration: 5.0,
    currentTime: 0.0,
    draggingEntity: null,
    rotatingEntity: null,
    fovScalingEntity: null,
    canvasScale: 1.0,
    canvasPanX: 0.0,
    canvasPanY: 0.0
};

// Elements
const blockingStage = document.getElementById('blocking-stage');
const timeLabel = document.getElementById('blocking-time-label');
const timelineSlider = document.getElementById('blocking-timeline-slider');
const timelinePlayhead = document.getElementById('timeline-playhead');
const timelineRuler = document.getElementById('timeline-ruler');
const keyframesDisplay = document.getElementById('blocking-keyframes-display');
const timelineZoomSlider = document.getElementById('blocking-zoom-slider');
const timelineZoomContent = document.getElementById('timeline-zoom-content');
const timelineScrollContainer = document.getElementById('timeline-scroll-container');
const durationSlider = document.getElementById('blocking-duration');
const durationLabel = document.getElementById('blocking-duration-label');
const saveKeyframeBtn = document.getElementById('add-keyframe-btn');
const clearKeyframesBtn = document.getElementById('clear-keyframes-btn');
const prevKfBtn = document.getElementById('blocking-prev-kf-btn');
const prevFrameBtn = document.getElementById('blocking-prev-frame-btn');
const nextFrameBtn = document.getElementById('blocking-next-frame-btn');
const nextKfBtn = document.getElementById('blocking-next-kf-btn');
const playBtn = document.getElementById('blocking-play-btn');
const undoBtn = document.getElementById('blocking-undo-btn');
const redoBtn = document.getElementById('blocking-redo-btn');
const resetBtn = document.getElementById('blocking-reset-btn');
const exportBtn = document.getElementById('blocking-export-btn');
const importBtn = document.getElementById('blocking-import-btn');
const importFile = document.getElementById('blocking-import-file');
const recordBtn = document.getElementById('blocking-record-btn');
const stopBtn = document.getElementById('blocking-stop-btn');

let isRecordingMode = false;

// Add Entity UI
const addEntityType = document.getElementById('add-entity-type');
const addEntityName = document.getElementById('add-entity-name');
const addEntityTag = document.getElementById('add-entity-tag');
const addEntityColor = document.getElementById('add-entity-color');
const addEntityColorWrapper = document.getElementById('add-entity-color-wrapper');
const submitAddEntityBtn = document.getElementById('submit-add-entity-btn');
const activeShotBgTagInput = document.getElementById('active-shot-bg-tag');
const generatePromptBtn = document.getElementById('blocking-generate-prompt-btn');

function initBlocking() {
    durationSlider.addEventListener('input', (e) => {
        blockingState.duration = parseFloat(e.target.value);
        durationLabel.innerText = blockingState.duration;
        timelineSlider.max = blockingState.duration;
        updateKeyframeMarkers();
    });

    // Canvas Zoom & Pan logic
    const editorWrapper = document.querySelector('.blocking-editor');
    if (editorWrapper) {
        let isPanning = false;
        
        // Disable context menu to allow right-click pan if needed, or use middle-click
        editorWrapper.addEventListener('contextmenu', e => e.preventDefault());

        const canvasZoomSlider = document.getElementById('canvas-zoom-slider');
        const canvasResetBtn = document.getElementById('canvas-reset-pan-btn');

        if (canvasZoomSlider) {
            canvasZoomSlider.addEventListener('input', (e) => {
                blockingState.canvasScale = parseFloat(e.target.value);
                updateCanvasTransform();
            });
        }

        if (canvasResetBtn) {
            canvasResetBtn.addEventListener('click', () => {
                blockingState.canvasScale = 1.0;
                blockingState.canvasPanX = 0;
                blockingState.canvasPanY = 0;
                if (canvasZoomSlider) canvasZoomSlider.value = 1.0;
                updateCanvasTransform();
            });
        }

        editorWrapper.addEventListener('mousedown', (e) => {
            // Middle mouse (button 1) or holding Spacebar + Left click
            if (e.button === 1 || (e.button === 0 && e.shiftKey)) { // Using Shift+Click as alternative to spacebar since spacebar might scroll page
                e.preventDefault();
                isPanning = true;
                editorWrapper.style.cursor = 'grabbing';
            }
        });

        window.addEventListener('mousemove', (e) => {
            if (isPanning) {
                blockingState.canvasPanX += e.movementX;
                blockingState.canvasPanY += e.movementY;
                updateCanvasTransform();
            }
        });

        window.addEventListener('mouseup', () => {
            if (isPanning) {
                isPanning = false;
                editorWrapper.style.cursor = 'default';
            }
        });
    }

    function updateCanvasTransform() {
        if (blockingStage) {
            blockingStage.style.transform = `translate(${blockingState.canvasPanX}px, ${blockingState.canvasPanY}px) scale(${blockingState.canvasScale})`;
        }
    }

    timelineSlider.addEventListener('input', (e) => {
        blockingState.currentTime = parseFloat(e.target.value);
        if (timeLabel) timeLabel.innerText = blockingState.currentTime.toFixed(1) + 's';
        
        // If we are currently "holding" a keyframe (to move it), move it along the timeline
        if (selectedKeyframeTrack && selectedKeyframeTime !== null) {
            const oldT = selectedKeyframeTime;
            const newT = blockingState.currentTime;
            
            if (oldT !== newT) {
                // Check if target is empty
                if (!blockingState.keyframes[selectedKeyframeTrack][newT]) {
                    // Move it
                    blockingState.keyframes[selectedKeyframeTrack][newT] = blockingState.keyframes[selectedKeyframeTrack][oldT];
                    delete blockingState.keyframes[selectedKeyframeTrack][oldT];
                    selectedKeyframeTime = newT;
                }
            }
            saveBlockingToLocalStorage();
            updateKeyframeMarkers();
        }
        
        updatePlayhead();
        interpolateAndRender(blockingState.currentTime);
    });

    if (timelineZoomSlider && timelineZoomContent) {
        timelineZoomSlider.addEventListener('input', (e) => {
            const zoom = parseFloat(e.target.value);
            timelineZoomContent.style.minWidth = `${zoom * 100}%`;
        });
    }

    function updatePlayhead() {
        if (timelineSlider && timelinePlayhead) {
            timelineSlider.value = blockingState.currentTime;
            const percent = blockingState.currentTime / blockingState.duration;
            timelinePlayhead.style.left = `calc(${percent * 100}%)`;
        }
    }

    addEntityType.addEventListener('change', (e) => {
        addEntityColorWrapper.style.display = 'flex';
        if (e.target.value === 'camera') {
            addEntityName.placeholder = 'Name (e.g. Cam 1)';
        } else {
            addEntityName.placeholder = 'Name (e.g. Actor 1)';
        }
    });

    submitAddEntityBtn.addEventListener('click', (e) => {
        e.preventDefault();
        const type = addEntityType.value;
        const name = addEntityName.value.trim() || (type === 'camera' ? 'Cam 1' : 'Actor 1');
        const color = addEntityColor.value;
        const tag = addEntityTag.value.trim();
        
        addEntity(type, name, color, tag);
        
        // Reset form
        addEntityName.value = '';
        addEntityTag.value = '';
    });

    if (undoBtn) undoBtn.addEventListener('click', performUndo);
    if (redoBtn) redoBtn.addEventListener('click', performRedo);
    if (resetBtn) resetBtn.addEventListener('click', resetBlockingProject);
    
    if (exportBtn) {
        exportBtn.addEventListener('click', () => {
            const json = localStorage.getItem('ad_blocking_project');
            if (!json) return alert("No project data to save.");
            const blob = new Blob([json], {type: "application/json"});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `blocking_project_${new Date().getTime()}.json`;
            a.click();
            URL.revokeObjectURL(url);
        });
    }

    if (importBtn && importFile) {
        importBtn.addEventListener('click', () => importFile.click());
        importFile.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = (ev) => {
                const json = ev.target.result;
                try {
                    JSON.parse(json);
                    localStorage.setItem('ad_blocking_project', json);
                    undoStack = [];
                    redoStack = [];
                    loadBlockingFromLocalStorage();
                    alert("Project loaded successfully!");
                } catch (err) {
                    alert("Invalid project file.");
                }
            };
            reader.readAsText(file);
            importFile.value = '';
        });
    }
    
    const renderBtn = document.getElementById('blocking-render-btn');
    if (renderBtn) {
        renderBtn.addEventListener('click', () => {
            const submitBtn = document.querySelector('#upload-form button[type="submit"]');
            if (submitBtn) {
                // Scroll to top to see progress and click submit
                window.scrollTo({top: 0, behavior: 'smooth'});
                submitBtn.click();
            }
        });
    }
    
    // Global keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === 'z') {
            const tag = e.target.tagName;
            if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
            if (e.shiftKey) {
                performRedo();
            } else {
                performUndo();
            }
            e.preventDefault();
        }
    });

    saveKeyframeBtn.addEventListener('click', saveKeyframeAtCurrentTime);
    clearKeyframesBtn.addEventListener('click', clearKeyframeAtCurrentTime);
    
    // Background Manager Logic
    const topViewUpload = document.getElementById('top-view-upload');
    const topViewInput = document.getElementById('top-view-input');
    const bgSlots = document.querySelectorAll('.bg-upload-slot');
    const secondaryBgInput = document.getElementById('secondary-bg-input');
    let currentSlotIndex = null;
    
    if (topViewUpload && topViewInput) {
        topViewUpload.addEventListener('click', () => topViewInput.click());
        topViewInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = (ev) => {
                const base64Img = ev.target.result;
                document.getElementById('blocking-stage').style.backgroundImage = `url(${base64Img})`;
                document.getElementById('blocking-placeholder').style.display = 'none';
                topViewUpload.style.backgroundImage = `url(${base64Img})`;
                topViewUpload.style.backgroundSize = 'cover';
                topViewUpload.style.backgroundPosition = 'center';
                const span = topViewUpload.querySelector('.upload-label');
                if (span) {
                    span.style.background = 'rgba(0,0,0,0.5)';
                    span.style.padding = '2px 4px';
                    span.style.borderRadius = '4px';
                }
                
                // Allow generating output now
                document.getElementById('generate-actions').style.display = 'block';
                window.selectedVideoFile = file;
                window.updateBackgroundDropdown();
                saveBlockingToLocalStorage();
            };
            reader.readAsDataURL(file);
        });
    }
    window.updateBackgroundDropdown = function() {
        const bgSelect = document.getElementById('active-shot-bg-tag');
        if (!bgSelect) return;
        const currentVal = bgSelect.value;
        bgSelect.innerHTML = '<option value="">-- None --</option>';
        
        const tags = [];
        document.querySelectorAll('.bg-tag-input').forEach(input => {
            const val = input.value.trim();
            if (val) tags.push({ val, elem: input.closest('.bg-upload-slot') });
        });
        
        tags.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.val;
            opt.innerText = t.val;
            bgSelect.appendChild(opt);
        });
        
        if (tags.some(t => t.val === currentVal)) {
            bgSelect.value = currentVal;
        }
        
        // Update borders
        document.querySelectorAll('.bg-upload-slot').forEach(slot => {
            slot.style.border = '2px dashed rgba(52, 152, 219, 0.3)';
        });
        
        const selectedVal = bgSelect.value;
        if (selectedVal) {
            const match = tags.find(t => t.val === selectedVal);
            if (match) {
                match.elem.style.border = '2px solid #2ecc71';
            }
        }
    };
    window.updateBackgroundDropdown();
    
    document.querySelectorAll('.bg-tag-input').forEach(input => {
        input.addEventListener('input', () => {
            window.updateBackgroundDropdown();
            saveBlockingToLocalStorage();
        });
    });
    
    const shotBgSelect = document.getElementById('active-shot-bg-tag');
    if (shotBgSelect) {
        shotBgSelect.addEventListener('change', () => {
            window.updateBackgroundDropdown();
        });
    }

    if (secondaryBgInput) {
        bgSlots.forEach(slot => {
            slot.addEventListener('click', () => {
                currentSlotIndex = slot.dataset.index;
                secondaryBgInput.click();
            });
        });
        
        secondaryBgInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (!file || !currentSlotIndex) return;
            const reader = new FileReader();
            reader.onload = (ev) => {
                const base64Img = ev.target.result;
                const slot = document.querySelector(`.bg-upload-slot[data-index="${currentSlotIndex}"]`);
                if (slot) {
                    slot.style.backgroundImage = `url(${base64Img})`;
                    slot.style.backgroundSize = 'cover';
                    slot.style.backgroundPosition = 'center';
                    const span = slot.querySelector('.upload-label');
                    if (span) {
                        span.style.background = 'rgba(0,0,0,0.5)';
                        span.style.padding = '2px 4px';
                        span.style.borderRadius = '4px';
                    }
                    slot.dataset.base64 = base64Img;
                    window.updateBackgroundDropdown();
                    saveBlockingToLocalStorage();
                }
            };
            reader.readAsDataURL(file);
        });
    }
    function setupHoldButton(btn, stepFn) {
        if (!btn) return;
        let holdTimer = null;
        let holdInterval = null;
        
        const startAction = () => {
            stepFn();
            holdTimer = setTimeout(() => {
                holdInterval = setInterval(stepFn, 50); // fast scrub
            }, 300);
        };
        
        const stopAction = () => {
            clearTimeout(holdTimer);
            clearInterval(holdInterval);
        };
        
        btn.addEventListener('mousedown', startAction);
        btn.addEventListener('mouseup', stopAction);
        btn.addEventListener('mouseleave', stopAction);
        btn.addEventListener('touchstart', (e) => { e.preventDefault(); startAction(); }, {passive: false});
        btn.addEventListener('touchend', stopAction);
    }
    
    setupHoldButton(prevFrameBtn, () => {
        let newVal = parseFloat(timelineSlider.value) - 0.1;
        if (newVal < 0) newVal = 0;
        timelineSlider.value = newVal;
        timelineSlider.dispatchEvent(new Event('input'));
    });
    
    setupHoldButton(nextFrameBtn, () => {
        let newVal = parseFloat(timelineSlider.value) + 0.1;
        if (newVal > blockingState.duration) newVal = blockingState.duration;
        timelineSlider.value = newVal;
        timelineSlider.dispatchEvent(new Event('input'));
    });
    
    function getAllKeyframeTimes() {
        const times = new Set();
        Object.keys(blockingState.keyframes).forEach(trackId => {
            Object.keys(blockingState.keyframes[trackId]).forEach(tStr => {
                times.add(parseFloat(tStr));
            });
        });
        return Array.from(times).sort((a,b)=>a-b);
    }

    if (prevKfBtn) {
        prevKfBtn.addEventListener('click', () => {
            const times = getAllKeyframeTimes();
            const curr = parseFloat(timelineSlider.value);
            let target = 0;
            for (let i = times.length - 1; i >= 0; i--) {
                if (times[i] < curr - 0.05) {
                    target = times[i];
                    break;
                }
            }
            timelineSlider.value = target;
            timelineSlider.dispatchEvent(new Event('input'));
        });
    }

    if (nextKfBtn) {
        nextKfBtn.addEventListener('click', () => {
            const times = getAllKeyframeTimes();
            const curr = parseFloat(timelineSlider.value);
            let target = blockingState.duration;
            for (let i = 0; i < times.length; i++) {
                if (times[i] > curr + 0.05) {
                    target = times[i];
                    break;
                }
            }
            timelineSlider.value = target;
            timelineSlider.dispatchEvent(new Event('input'));
        });
    }
    
    if (generatePromptBtn) {
        generatePromptBtn.addEventListener('click', () => {
            generatePrompt();
        });
    }

    // Setup stage dragging events
    blockingStage.addEventListener('mousemove', handleMouseMove);
    blockingStage.addEventListener('mouseup', handleMouseUp);
    blockingStage.addEventListener('mouseleave', handleMouseUp);
    
    document.getElementById('active-camera-select').addEventListener('change', (e) => {
        updateCameraOpacities();
        if (selectedKeyframeTime && blockingState.keyframes[selectedKeyframeTime]) {
            blockingState.keyframes[selectedKeyframeTime]._activeCamera = e.target.value;
            saveBlockingToLocalStorage();
        }
    });
    
    const activeShotSelect = document.getElementById('active-shot-select');
    if (activeShotSelect) {
        activeShotSelect.addEventListener('change', (e) => {
            if (selectedKeyframeTime && blockingState.keyframes[selectedKeyframeTime]) {
                blockingState.keyframes[selectedKeyframeTime]._activeShot = e.target.value;
                saveBlockingToLocalStorage();
            }
        });
    }
    
    if (playBtn) {
        playBtn.addEventListener('click', togglePlayback);
    }
    
    if (recordBtn) {
        recordBtn.addEventListener('click', () => {
            isRecordingMode = !isRecordingMode;
            if (isRecordingMode) {
                recordBtn.style.background = 'rgba(231, 76, 60, 0.4)';
                recordBtn.style.boxShadow = '0 0 10px red';
            } else {
                recordBtn.style.background = 'rgba(231, 76, 60, 0.1)';
                recordBtn.style.boxShadow = 'none';
            }
        });
    }

    if (stopBtn) {
        stopBtn.addEventListener('click', () => {
            if (isPlaying) togglePlayback();
            blockingState.currentTime = 0;
            timelineSlider.value = 0;
            timelineSlider.dispatchEvent(new Event('input'));
            
            if (isRecordingMode) {
                isRecordingMode = false;
                if (recordBtn) {
                    recordBtn.style.background = 'rgba(231, 76, 60, 0.1)';
                    recordBtn.style.boxShadow = 'none';
                }
            }
        });
    }
    
    loadBlockingFromLocalStorage();
    setInterval(saveBlockingToLocalStorage, 2000);
}

let isPlaying = false;
let lastFrameTime = 0;
let animationFrameId = null;
let selectedKeyframeTime = null;

function togglePlayback() {
    isPlaying = !isPlaying;
    if (isPlaying) {
        playBtn.innerText = '⏸️';
        if (blockingState.currentTime >= blockingState.duration) {
            blockingState.currentTime = 0; // restart if at end
        }
        lastFrameTime = performance.now();
        animationFrameId = requestAnimationFrame(playLoop);
    } else {
        playBtn.innerText = '▶️';
        if (animationFrameId) cancelAnimationFrame(animationFrameId);
    }
}

function playLoop(timestamp) {
    if (!isPlaying) return;
    
    const deltaMs = timestamp - lastFrameTime;
    lastFrameTime = timestamp;
    
    blockingState.currentTime += (deltaMs / 1000);
    
    if (blockingState.currentTime >= blockingState.duration) {
        blockingState.currentTime = blockingState.duration;
        timelineSlider.value = blockingState.duration;
        timeLabel.innerText = blockingState.duration.toFixed(1) + 's';
        updatePlayhead();
        interpolateAndRender(blockingState.duration);
        togglePlayback(); // auto pause at end
        return;
    }
    
    timelineSlider.value = blockingState.currentTime;
    timeLabel.innerText = blockingState.currentTime.toFixed(1) + 's';
    updatePlayhead();
    interpolateAndRender(blockingState.currentTime);
    
    animationFrameId = requestAnimationFrame(playLoop);
}

let undoStack = [];
let redoStack = [];
let isRestoringHistory = false;

window.saveBlockingToLocalStorage = saveBlockingToLocalStorage;

function saveBlockingToLocalStorage() {
    const data = {
        duration: blockingState.duration,
        currentTime: blockingState.currentTime,
        entities: {},
        keyframes: blockingState.keyframes,
        bgs: {}
    };
    
    Object.keys(blockingState.entities).forEach(id => {
        const ent = blockingState.entities[id];
        data.entities[id] = { 
            type: ent.type, 
            label: ent.label, 
            color: ent.elem.dataset.color, 
            x: ent.elem.dataset.x, 
            y: ent.elem.dataset.y, 
            rot: ent.elem.dataset.rot, 
            fov: ent.elem.dataset.fov,
            assetTag: ent.assetTag || "",
            locked: ent.elem.dataset.locked === "true"
        };
    });
    
    const bg = document.getElementById('blocking-stage').style.backgroundImage;
    if (bg && bg !== 'none') {
        data.bg = bg;
    }
    
    const topViewTag = document.getElementById('top-view-tag');
    if (topViewTag) data.topViewTag = topViewTag.value;
    
    document.querySelectorAll('.bg-upload-slot').forEach(slot => {
        const idx = slot.dataset.index;
        const tagInput = slot.querySelector('.bg-tag-input');
        if (slot.dataset.base64) {
            data.bgs[idx] = {
                base64: slot.dataset.base64,
                tag: tagInput ? tagInput.value : ""
            };
        }
    });
    
    try {
        const dataStr = JSON.stringify(data);
        localStorage.setItem('ad_blocking_project', dataStr);
        
        if (!isRestoringHistory) {
            if (undoStack.length === 0 || undoStack[undoStack.length - 1] !== dataStr) {
                undoStack.push(dataStr);
                redoStack = [];
                if (undoStack.length > 30) undoStack.shift();
            }
        }
        updateHistoryButtons();
        
        const timeLabel = document.getElementById('autosave-time-label');
        if (timeLabel) {
            timeLabel.innerText = "Updated " + new Date().toLocaleTimeString();
        }
    } catch (e) {
        console.warn("Could not save blocking project (quota exceeded?)", e);
    }
}

function restoreStateFromJSON(json) {
    isRestoringHistory = true;
    try {
        const data = JSON.parse(json);
        
        // Clear current stage
        blockingStage.querySelectorAll('.blocking-entity').forEach(e => e.remove());
        blockingState.entities = {};
        blockingState.keyframes = {};
        
        blockingState.duration = data.duration || 5.0;
        if (durationSlider) durationSlider.value = blockingState.duration;
        if (durationLabel) durationLabel.innerText = blockingState.duration;
        if (timelineSlider) timelineSlider.max = blockingState.duration;
        
        if (data.bg) {
            document.getElementById('blocking-stage').style.backgroundImage = data.bg;
            const ph = document.getElementById('blocking-placeholder');
            if (ph) ph.style.display = 'none';
            const tv = document.getElementById('top-view-upload');
            if (tv) {
                tv.style.backgroundImage = data.bg;
                tv.style.backgroundSize = 'cover';
                tv.style.backgroundPosition = 'center';
            }
        } else {
            document.getElementById('blocking-stage').style.backgroundImage = 'none';
            const ph = document.getElementById('blocking-placeholder');
            if (ph) ph.style.display = 'block';
            const tv = document.getElementById('top-view-upload');
            if (tv) tv.style.backgroundImage = 'none';
        }
        
        const topViewTag = document.getElementById('top-view-tag');
        if (topViewTag) topViewTag.value = data.topViewTag || "";
        
        // Clear slots first
        document.querySelectorAll('.bg-upload-slot').forEach(slot => {
            slot.style.backgroundImage = 'none';
            delete slot.dataset.base64;
            const span = slot.querySelector('.upload-label');
            if (span) { span.style.background = 'none'; }
        });
        
        if (data.bgs) {
            Object.keys(data.bgs).forEach(idx => {
                const slot = document.querySelector(`.bg-upload-slot[data-index="${idx}"]`);
                if (slot) {
                    slot.style.backgroundImage = `url(${data.bgs[idx].base64})`;
                    slot.style.backgroundSize = 'cover';
                    slot.style.backgroundPosition = 'center';
                    slot.dataset.base64 = data.bgs[idx].base64;
                    const span = slot.querySelector('.upload-label');
                    if (span) { span.style.background = 'rgba(0,0,0,0.5)'; span.style.padding = '2px 4px'; span.style.borderRadius = '4px'; }
                    const tagInput = slot.querySelector('.bg-tag-input');
                    if (tagInput) tagInput.value = data.bgs[idx].tag || "";
                }
            });
        }
        
        if (window.updateBackgroundDropdown) window.updateBackgroundDropdown();
        
        // Restore entities
        Object.keys(data.entities).forEach(id => {
            const ent = data.entities[id];
            addEntity(ent.type, ent.label, ent.color, ent.assetTag || "", id, ent.x, ent.y, ent.rot, ent.fov, ent.locked);
        });
        
        // Restore keyframes
        blockingState.keyframes = data.keyframes || {};
        updateKeyframeMarkers();
        interpolateAndRender(blockingState.currentTime);
        renderEntityList();
        
        localStorage.setItem('ad_blocking_project', json);
        updateHistoryButtons();
    } catch (e) {
        console.error("Error restoring state", e);
    }
    isRestoringHistory = false;
}

function updateHistoryButtons() {
    if (undoBtn) undoBtn.disabled = undoStack.length <= 1;
    if (redoBtn) redoBtn.disabled = redoStack.length === 0;
}

function performUndo() {
    if (undoStack.length <= 1) return;
    const currentState = undoStack.pop();
    redoStack.push(currentState);
    const prevState = undoStack[undoStack.length - 1];
    restoreStateFromJSON(prevState);
}

function performRedo() {
    if (redoStack.length === 0) return;
    const nextState = redoStack.pop();
    undoStack.push(nextState);
    restoreStateFromJSON(nextState);
}

function resetBlockingProject() {
    if (!confirm("Are you sure you want to reset the entire blocking project? This will remove all entities and keyframes.")) return;
    
    blockingStage.querySelectorAll('.blocking-entity').forEach(e => e.remove());
    blockingState.entities = {};
    blockingState.keyframes = {};
    blockingStage.style.backgroundImage = 'none';
    document.getElementById('blocking-placeholder').style.display = 'block';
    
    saveBlockingToLocalStorage();
    renderEntityList();
    updateKeyframeMarkers();
}

function loadBlockingFromLocalStorage() {
    const json = localStorage.getItem('ad_blocking_project');
    if (!json) {
        saveBlockingToLocalStorage();
        return;
    }
    if (undoStack.length === 0) {
        undoStack.push(json);
    }
    restoreStateFromJSON(json);
}

function generateId() {
    return Math.random().toString(36).substr(2, 9);
}

function addEntity(type, label, color = null, assetTag = "", forceId = null, startX=50, startY=50, startRot=0, startFov=100, isLocked=false) {
    const id = forceId || generateId();
    const elem = document.createElement('div');
    elem.className = 'blocking-entity';
    elem.dataset.id = id;
    elem.dataset.locked = isLocked ? "true" : "false";
    if (color) {
        elem.dataset.color = color;
    }
    
    // Initial position center
    let x = 50, y = 50, rot = 0, fov = 100;
    
    if (type === 'character') {
        const bg = color || "var(--primary-color)";
        elem.innerHTML = `
            <div class="blocking-eyeline"></div>
            <div class="blocking-char-circle" style="background-color: ${bg};">${label.charAt(0)}</div>
            <div class="blocking-label">${label}</div>
        `;
        // Add rotation handle
        const rotHandle = document.createElement('div');
        rotHandle.className = 'char-rot-handle';
        rotHandle.style.cssText = 'position: absolute; top: -15px; left: 50%; transform: translateX(-50%); width: 8px; height: 8px; background: yellow; border-radius: 50%; cursor: grab; z-index: 10;';
        rotHandle.addEventListener('mousedown', (e) => {
            e.stopPropagation();
            blockingState.rotatingEntity = id;
        });
        elem.appendChild(rotHandle);
        
        // Add scale handle
        const scaleHandle = document.createElement('div');
        scaleHandle.className = 'char-scale-handle';
        scaleHandle.style.cssText = 'position: absolute; bottom: -5px; right: -5px; width: 8px; height: 8px; background: #e67e22; border-radius: 50%; cursor: nwse-resize; z-index: 10;';
        scaleHandle.addEventListener('mousedown', (e) => {
            e.stopPropagation();
            blockingState.fovScalingEntity = id;
        });
        elem.appendChild(scaleHandle);
    } else if (type === 'camera') {
        let rgbaColor = 'rgba(255, 255, 255, 0.2)';
        if (color) {
            const hex = color.replace('#', '');
            if (hex.length === 6) {
                const r = parseInt(hex.substring(0, 2), 16);
                const g = parseInt(hex.substring(2, 4), 16);
                const b = parseInt(hex.substring(4, 6), 16);
                rgbaColor = `rgba(${r}, ${g}, ${b}, 0.25)`;
            }
        }
        elem.innerHTML = `
            <div class="blocking-camera-fov" id="fov-${id}" style="--fov-color: ${rgbaColor};"></div>
            <div class="blocking-camera-icon" style="cursor: pointer;">🎥</div>
            <div class="blocking-active-dot" id="active-dot-${id}" style="display: none; position: absolute; top: -5px; right: -5px; width: 12px; height: 12px; background: red; border-radius: 50%; box-shadow: 0 0 5px red; pointer-events: none;"></div>
            <div class="blocking-lock-btn" id="lock-btn-${id}" style="position: absolute; bottom: 10px; right: -15px; cursor: pointer; font-size: 14px; opacity: ${isLocked ? '1' : '0.5'}; background: rgba(0,0,0,0.7); border-radius: 4px; padding: 2px;">${isLocked ? '🔒' : '🔓'}</div>
            <div class="blocking-label" style="margin-top: 15px;">${label}</div>
        `;
        
        // Active Toggle
        const iconElem = elem.querySelector('.blocking-camera-icon');
        iconElem.addEventListener('mousedown', (e) => { e.stopPropagation(); }); // prevent drag conflict
        iconElem.addEventListener('click', (e) => {
            e.stopPropagation();
            const camSelect = document.getElementById('active-camera-select');
            if (camSelect) {
                if (camSelect.value === id) {
                    camSelect.value = "none";
                } else {
                    camSelect.value = id;
                }
                camSelect.dispatchEvent(new Event('change'));
                
                if (isRecordingMode) {
                    // Keyframe Director track at current time
                    const t = blockingState.currentTime.toFixed(1);
                    if (!blockingState.keyframes.director) blockingState.keyframes.director = {};
                    
                    const shotSelect = document.getElementById('active-shot-select');
                    const shotBg = document.getElementById('active-shot-bg-tag');
                    
                    blockingState.keyframes.director[t] = {
                        activeCamera: camSelect.value,
                        activeShot: shotSelect ? shotSelect.value : "",
                        shotBgTag: shotBg ? shotBg.value : ""
                    };
                    saveBlockingToLocalStorage();
                    updateKeyframeMarkers();
                }
                interpolateAndRender(blockingState.currentTime);
            }
        });
        
        // Lock Toggle
        const lockBtn = elem.querySelector('.blocking-lock-btn');
        lockBtn.addEventListener('mousedown', (e) => { e.stopPropagation(); });
        lockBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (elem.dataset.locked === "true") {
                elem.dataset.locked = "false";
                lockBtn.innerText = "🔓";
                lockBtn.style.opacity = "0.5";
            } else {
                elem.dataset.locked = "true";
                lockBtn.innerText = "🔒";
                lockBtn.style.opacity = "1";
            }
        });

        // Add rotation handle
        const rotHandle = document.createElement('div');
        rotHandle.style.cssText = 'position: absolute; top: -20px; left: 50%; transform: translateX(-50%); width: 10px; height: 10px; background: yellow; border-radius: 50%; cursor: grab; z-index: 10;';
        rotHandle.addEventListener('mousedown', (e) => {
            e.stopPropagation();
            if (elem.dataset.locked === "true") return;
            blockingState.rotatingEntity = id;
        });
        elem.appendChild(rotHandle);
        
        // Add FOV scale handle
        const fovHandle = document.createElement('div');
        fovHandle.style.cssText = 'position: absolute; top: -100px; left: 50%; transform: translateX(-50%); width: 10px; height: 10px; background: cyan; border-radius: 50%; cursor: ns-resize; z-index: 10;';
        fovHandle.id = `fov-handle-${id}`;
        fovHandle.addEventListener('mousedown', (e) => {
            e.stopPropagation();
            if (elem.dataset.locked === "true") return;
            blockingState.fovScalingEntity = id;
        });
        elem.appendChild(fovHandle);
    } else if (type.startsWith('shape-')) {
        const isRect = type === 'shape-rect';
        const isCircle = type === 'shape-circle';
        const isLine = type === 'shape-line';
        
        elem.classList.add(type);
        elem.style.width = '100px';
        elem.style.height = isLine ? '4px' : '100px';
        
        // Add rotation handle
        const rotHandle = document.createElement('div');
        rotHandle.style.cssText = 'position: absolute; top: -15px; left: 50%; transform: translateX(-50%); width: 10px; height: 10px; background: yellow; border-radius: 50%; cursor: grab; z-index: 10;';
        rotHandle.addEventListener('mousedown', (e) => {
            e.stopPropagation();
            if (elem.dataset.locked === "true") return;
            blockingState.rotatingEntity = id;
        });
        elem.appendChild(rotHandle);
        
        // Add scale handle (which we'll use fovScalingEntity for scaling the shape!)
        const scaleHandle = document.createElement('div');
        scaleHandle.style.cssText = 'position: absolute; bottom: -5px; right: -5px; width: 10px; height: 10px; background: #e67e22; border-radius: 50%; cursor: nwse-resize; z-index: 10;';
        scaleHandle.addEventListener('mousedown', (e) => {
            e.stopPropagation();
            if (elem.dataset.locked === "true") return;
            blockingState.fovScalingEntity = id;
        });
        elem.appendChild(scaleHandle);
        
        // Label
        const labelDiv = document.createElement('div');
        labelDiv.className = 'blocking-label';
        labelDiv.style.marginTop = isLine ? '10px' : '110px';
        labelDiv.innerText = label;
        elem.appendChild(labelDiv);
        
        // Lock button
        const lockBtn = document.createElement('div');
        lockBtn.className = 'blocking-lock-btn';
        lockBtn.style.cssText = `position: absolute; bottom: 10px; right: -15px; cursor: pointer; font-size: 14px; opacity: ${isLocked ? '1' : '0.5'}; background: rgba(0,0,0,0.7); border-radius: 4px; padding: 2px;`;
        lockBtn.innerText = isLocked ? '🔒' : '🔓';
        lockBtn.addEventListener('mousedown', (e) => { e.stopPropagation(); });
        lockBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (elem.dataset.locked === "true") {
                elem.dataset.locked = "false";
                lockBtn.innerText = "🔓";
                lockBtn.style.opacity = "0.5";
            } else {
                elem.dataset.locked = "true";
                lockBtn.innerText = "🔒";
                lockBtn.style.opacity = "1";
            }
        });
        elem.appendChild(lockBtn);
    }

    // Drag handle
    elem.addEventListener('mousedown', (e) => {
        if (elem.dataset.locked === "true") return;
        if (blockingState.rotatingEntity || blockingState.fovScalingEntity) return;
        blockingState.draggingEntity = id;
    });

    blockingStage.appendChild(elem);

    blockingState.entities[id] = { type, label, color, assetTag, elem };
    if (!blockingState.keyframes[id]) blockingState.keyframes[id] = {};
    updateEntityTransform(id, startX, startY, startRot, startFov);
    
    // Automatically save a keyframe at time 0.0 if it's the first entity and no forced ID
    if (!forceId) {
        const t0 = (0.0).toFixed(1);
        blockingState.keyframes[id][t0] = { x: startX, y: startY, rot: startRot, fov: startFov };
        saveBlockingToLocalStorage();
        updateKeyframeMarkers();
    }
    renderEntityList();
}

function renderEntityList() {
    const list = document.getElementById('entity-list');
    const camSelect = document.getElementById('active-camera-select');
    if (!list || !camSelect) return;
    
    list.innerHTML = '';
    
    const currentActiveCam = camSelect.value;
    camSelect.innerHTML = '<option value="none">-- None (Top Down) --</option>';
    
    const ids = Object.keys(blockingState.entities);
    if (ids.length === 0) {
        list.innerHTML = '<p style="color: rgba(255,255,255,0.3); font-size: 0.9rem;">No entities yet.</p>';
        return;
    }
    
    ids.forEach(id => {
        const ent = blockingState.entities[id];
        
        if (ent.type === 'camera') {
            const opt = document.createElement('option');
            opt.value = id;
            opt.innerText = ent.label;
            if (id === currentActiveCam) opt.selected = true;
            camSelect.appendChild(opt);
        }
        
        const item = document.createElement('div');
        item.className = 'entity-list-item';
        
        const infoDiv = document.createElement('div');
        infoDiv.className = 'entity-info';
        
        let icon = '👤';
        if (ent.type === 'camera') icon = '🎥';
        else if (ent.type === 'shape-rect') icon = '⬛';
        else if (ent.type === 'shape-circle') icon = '⭕';
        else if (ent.type === 'shape-line') icon = '📏';
        
        const typeIcon = document.createElement('span');
        typeIcon.innerText = icon;
        typeIcon.title = ent.type;
        infoDiv.appendChild(typeIcon);
        
        if (ent.type === 'character') {
            const colorBox = document.createElement('input');
            colorBox.type = 'color';
            colorBox.className = 'entity-color-box';
            colorBox.value = ent.elem.dataset.color || '#3498db';
            colorBox.style.padding = '0';
            colorBox.style.border = 'none';
            colorBox.style.background = 'none';
            colorBox.style.cursor = 'pointer';
            colorBox.style.width = '18px';
            colorBox.style.height = '18px';
            colorBox.title = "Click to change color";
            colorBox.addEventListener('input', (e) => {
                const newColor = e.target.value;
                ent.elem.dataset.color = newColor;
                ent.elem.querySelector('.blocking-char-circle').style.backgroundColor = newColor;
                saveBlockingToLocalStorage();
            });
            infoDiv.appendChild(colorBox);
            
            // Add scale number input
            const scaleInput = document.createElement('input');
            scaleInput.type = 'number';
            scaleInput.className = 'entity-scale-input';
            scaleInput.value = Math.round(ent.elem.dataset.fov || 100);
            scaleInput.min = 20;
            scaleInput.max = 300;
            scaleInput.title = 'Scale %';
            scaleInput.style.width = '50px';
            scaleInput.style.background = 'rgba(0,0,0,0.5)';
            scaleInput.style.color = 'white';
            scaleInput.style.border = '1px solid #555';
            scaleInput.style.borderRadius = '4px';
            scaleInput.style.fontSize = '0.8rem';
            scaleInput.style.marginLeft = '5px';
            
            scaleInput.addEventListener('change', (e) => {
                const newScale = Math.max(20, Math.min(300, parseInt(e.target.value) || 100));
                e.target.value = newScale;
                
                // Get current transform to keep everything else intact
                const x = parseFloat(ent.elem.dataset.x || 50);
                const y = parseFloat(ent.elem.dataset.y || 50);
                const rot = parseFloat(ent.elem.dataset.rot || 0);
                
                updateEntityTransform(id, x, y, rot, newScale);
                
                // Auto-keyframe if recording
                if (isRecordingMode) {
                    const t = blockingState.currentTime.toFixed(1);
                    if (!blockingState.keyframes[id]) blockingState.keyframes[id] = {};
                    blockingState.keyframes[id][t] = getEntityCurrentTransform(id);
                }
                saveBlockingToLocalStorage();
                updateKeyframeMarkers();
            });
            infoDiv.appendChild(scaleInput);
        }
        
        const label = document.createElement('input');
        label.type = 'text';
        label.className = 'entity-label';
        label.value = ent.label;
        label.style.background = 'none';
        label.style.border = 'none';
        label.style.color = 'white';
        label.style.width = '100px';
        label.addEventListener('change', (e) => {
            const newLabel = e.target.value.trim();
            if (newLabel) {
                ent.label = newLabel;
                ent.elem.querySelector('.blocking-label').innerText = newLabel;
                if (ent.type === 'camera') renderEntityList();
                saveBlockingToLocalStorage();
            }
        });
        infoDiv.appendChild(label);
        
        const delBtn = document.createElement('button');
        delBtn.className = 'entity-delete-btn';
        delBtn.innerText = '🗑️';
        delBtn.addEventListener('click', () => {
            if (confirm(`Delete ${ent.label}?`)) {
                ent.elem.remove();
                delete blockingState.entities[id];
                // Remove from all keyframes
                Object.values(blockingState.keyframes).forEach(kfObj => {
                    delete kfObj[id];
                });
                renderEntityList();
            }
        });
        
        item.appendChild(infoDiv);
        item.appendChild(delBtn);
        list.appendChild(item);
    });
}

function handleMouseMove(e) {
    const rect = blockingStage.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    
    const pctX = Math.max(0, Math.min(100, (mouseX / rect.width) * 100));
    const pctY = Math.max(0, Math.min(100, (mouseY / rect.height) * 100));

    if (blockingState.draggingEntity) {
        const id = blockingState.draggingEntity;
        const state = getEntityCurrentTransform(id);
        updateEntityTransform(id, pctX, pctY, state.rot, state.fov);
    } else if (blockingState.rotatingEntity) {
        const id = blockingState.rotatingEntity;
        const state = getEntityCurrentTransform(id);
        
        // Calculate angle between entity center and mouse
        const elem = blockingState.entities[id].elem;
        const elemRect = elem.getBoundingClientRect();
        const centerX = elemRect.left + elemRect.width / 2 - rect.left;
        const centerY = elemRect.top + elemRect.height / 2 - rect.top;
        
        let angle = Math.atan2(mouseY - centerY, mouseX - centerX) * (180 / Math.PI) + 90;
        updateEntityTransform(id, state.x, state.y, angle, state.fov);
    } else if (blockingState.fovScalingEntity) {
        const id = blockingState.fovScalingEntity;
        const state = getEntityCurrentTransform(id);
        
        const elem = blockingState.entities[id].elem;
        const elemRect = elem.getBoundingClientRect();
        const centerX = elemRect.left + elemRect.width / 2 - rect.left;
        const centerY = elemRect.top + elemRect.height / 2 - rect.top;
        
        const dist = Math.sqrt(Math.pow(mouseX - centerX, 2) + Math.pow(mouseY - centerY, 2)) / (blockingState.canvasScale || 1.0);
        updateEntityTransform(id, state.x, state.y, state.rot, dist);
    }
}

function handleMouseUp() {
    if (blockingState.draggingEntity || blockingState.rotatingEntity || blockingState.fovScalingEntity) {
        const id = blockingState.draggingEntity || blockingState.rotatingEntity || blockingState.fovScalingEntity;
        
        if (isRecordingMode) {
            // Auto-Keyframe this entity
            const t = blockingState.currentTime.toFixed(1);
            if (!blockingState.keyframes[id]) blockingState.keyframes[id] = {};
            blockingState.keyframes[id][t] = getEntityCurrentTransform(id);
            
            saveBlockingToLocalStorage();
            updateKeyframeMarkers();
        }
    }

    blockingState.draggingEntity = null;
    blockingState.rotatingEntity = null;
    blockingState.fovScalingEntity = null;
}

function updateEntityTransform(id, x, y, rot, fov) {
    const elem = blockingState.entities[id].elem;
    elem.style.left = `${x}%`;
    elem.style.top = `${y}%`;
    elem.style.transform = `translate(-50%, -50%) rotate(${rot}deg)`;
    elem.dataset.x = x;
    elem.dataset.y = y;
    elem.dataset.rot = rot;
    elem.dataset.fov = fov;

    if (blockingState.entities[id].type === 'character') {
        const circle = elem.querySelector('.blocking-char-circle');
        if (circle) {
            const scale = Math.max(10, fov) / 100;
            const size = 30 * scale;
            circle.style.width = `${size}px`;
            circle.style.height = `${size}px`;
            circle.style.fontSize = `${Math.max(8, 14 * scale)}px`;
            
            const rotHandle = elem.querySelector('.char-rot-handle');
            if (rotHandle) rotHandle.style.top = `-${(size/2) + 10}px`;
            
            const scaleHandle = elem.querySelector('.char-scale-handle');
            if (scaleHandle) {
                scaleHandle.style.bottom = `-${(size/2) - 5}px`;
                scaleHandle.style.right = `-${(size/2) - 5}px`;
            }
        }
    } else if (blockingState.entities[id].type === 'camera') {
        const fovElem = document.getElementById(`fov-${id}`);
        const fovHandle = document.getElementById(`fov-handle-${id}`);
        if (fovElem) {
            // Adjust the CSS triangle border lengths based on FOV
            const halfBase = fov / 2;
            const styleId = `style-fov-${id}`;
            let styleTag = document.getElementById(styleId);
            if (!styleTag) {
                styleTag = document.createElement('style');
                styleTag.id = styleId;
                document.head.appendChild(styleTag);
            }
            styleTag.innerHTML = `
                #fov-${id}::before {
                    top: -${fov}px !important;
                    left: -${halfBase}px !important;
                    border-width: ${fov}px ${halfBase}px 0 ${halfBase}px !important;
                    border-color: rgba(255, 255, 255, 0.2) transparent transparent transparent !important;
                    transform: none !important;
                }
            `;
            if (fovHandle) fovHandle.style.top = `-${fov}px`;
        }
    } else if (blockingState.entities[id].type.startsWith('shape-')) {
        elem.style.width = `${fov}px`;
        if (blockingState.entities[id].type !== 'shape-line') {
            elem.style.height = `${fov}px`;
        }
    }
}

function getEntityCurrentTransform(id) {
    const elem = blockingState.entities[id].elem;
    return {
        x: parseFloat(elem.dataset.x || 50),
        y: parseFloat(elem.dataset.y || 50),
        rot: parseFloat(elem.dataset.rot || 0),
        fov: parseFloat(elem.dataset.fov || 100)
    };
}

function saveKeyframeAtCurrentTime() {
    const t = blockingState.currentTime.toFixed(1);
    
    // Save state for all entities
    Object.keys(blockingState.entities).forEach(id => {
        if (!blockingState.keyframes[id]) blockingState.keyframes[id] = {};
        blockingState.keyframes[id][t] = getEntityCurrentTransform(id);
    });
    
    // Save Director state
    const camSelect = document.getElementById('active-camera-select');
    const shotSelect = document.getElementById('active-shot-select');
    const shotBg = document.getElementById('active-shot-bg-tag');
    
    if (!blockingState.keyframes.director) blockingState.keyframes.director = {};
    blockingState.keyframes.director[t] = {
        activeCamera: camSelect ? camSelect.value : "none",
        activeShot: shotSelect ? shotSelect.value : "",
        shotBgTag: shotBg ? shotBg.value : ""
    };
    
    saveBlockingToLocalStorage();
    updateKeyframeMarkers();
    
    // Visual feedback
    blockingStage.style.boxShadow = "inset 0 0 20px #10b981";
    setTimeout(() => { blockingStage.style.boxShadow = "none"; }, 300);
}

function clearKeyframeAtCurrentTime() {
    const t = blockingState.currentTime.toFixed(1);
    
    if (selectedKeyframeTrack && blockingState.keyframes[selectedKeyframeTrack]) {
        // Clear only selected track if one is selected
        delete blockingState.keyframes[selectedKeyframeTrack][t];
    } else {
        // Clear all tracks at this time
        Object.keys(blockingState.keyframes).forEach(track => {
            delete blockingState.keyframes[track][t];
        });
    }
    
    if (selectedKeyframeTime === t) selectedKeyframeTime = null;
    
    saveBlockingToLocalStorage();
    updateKeyframeMarkers();
}

let selectedKeyframeTrack = null;

function updateKeyframeMarkers() {
    // 1. Build Ruler
    timelineRuler.innerHTML = '';
    for (let i = 0; i <= blockingState.duration; i++) {
        const pct = (i / blockingState.duration) * 100;
        timelineRuler.innerHTML += `<div class="ruler-tick" style="left: ${pct}%;"></div>`;
        timelineRuler.innerHTML += `<div class="ruler-label" style="left: ${pct}%;">${i}s</div>`;
    }

    // 2. Build Tracks
    const headersDisplay = document.getElementById('blocking-track-headers');
    if (!headersDisplay) return;
    
    headersDisplay.innerHTML = '';
    keyframesDisplay.innerHTML = '';
    
    // Director Track
    const dirHeader = document.createElement('div');
    dirHeader.className = 'track-header';
    dirHeader.title = 'Director';
    dirHeader.innerHTML = '🎬 Director';
    headersDisplay.appendChild(dirHeader);

    const dirTimelineRow = document.createElement('div');
    dirTimelineRow.className = 'track-timeline';
    dirTimelineRow.dataset.track = 'director';
    keyframesDisplay.appendChild(dirTimelineRow);
    renderTrackDots('director', dirTimelineRow);
    
    // Entity Tracks
    Object.keys(blockingState.entities).forEach(id => {
        const ent = blockingState.entities[id];
        
        const entHeader = document.createElement('div');
        entHeader.className = 'track-header';
        entHeader.title = ent.label;
        const icon = ent.type === 'camera' ? '🎥' : (ent.type === 'light' ? '💡' : '👤');
        entHeader.innerHTML = `${icon} ${ent.label.toUpperCase()}`;
        headersDisplay.appendChild(entHeader);

        const entTimelineRow = document.createElement('div');
        entTimelineRow.className = 'track-timeline';
        entTimelineRow.dataset.track = id;
        keyframesDisplay.appendChild(entTimelineRow);
        
        renderTrackDots(id, entTimelineRow);
    });
}

function renderTrackDots(trackId, container) {
    // 1. Draw Active Camera Spans
    if (blockingState.entities[trackId] && blockingState.entities[trackId].type === 'camera') {
        const dirTrack = blockingState.keyframes.director || {};
        const dirTimes = Object.keys(dirTrack).map(parseFloat).sort((a,b)=>a-b);
        let activeStartTime = null;
        
        for (let i = 0; i < dirTimes.length; i++) {
            const t = dirTimes[i];
            const state = dirTrack[t.toFixed(1)];
            
            if (state.activeCamera === trackId) {
                if (activeStartTime === null) activeStartTime = t;
            } else {
                if (activeStartTime !== null) {
                    drawTrackSpan(container, activeStartTime, t);
                    activeStartTime = null;
                }
            }
        }
        
        if (activeStartTime !== null) {
            drawTrackSpan(container, activeStartTime, blockingState.duration);
        }
    }

    // 2. Draw Keyframe Dots
    if (!blockingState.keyframes[trackId]) return;
    
    Object.keys(blockingState.keyframes[trackId]).forEach(tStr => {
        const t = parseFloat(tStr);
        if (t <= blockingState.duration) {
            const pct = (t / blockingState.duration) * 100;
            const marker = document.createElement('div');
            marker.className = 'keyframe-dot';
            marker.style.left = `${pct}%`;
            
            if (trackId === 'director') {
                marker.style.backgroundColor = 'white';
                marker.style.border = '2px solid black';
            } else if (blockingState.entities[trackId]) {
                const ent = blockingState.entities[trackId];
                if (ent.type === 'character') {
                    marker.style.backgroundColor = ent.elem.dataset.color || 'white';
                    marker.style.border = '1px solid black';
                } else {
                    marker.style.backgroundColor = '#f39c12'; // orange for camera
                    marker.style.border = '1px solid black';
                }
            }
            
            marker.title = `Keyframe at ${t}s`;
            
            if (tStr === selectedKeyframeTime && trackId === selectedKeyframeTrack) {
                marker.classList.add('selected');
            }
            
            let isDragging = false;
            let hasMoved = false;

            marker.addEventListener('mousedown', (e) => {
                e.stopPropagation();
                isDragging = true;
                hasMoved = false;
                const rect = container.getBoundingClientRect();
                
                const onMouseMove = (ev) => {
                    if (!isDragging) return;
                    hasMoved = true;
                    const deltaX = ev.clientX - rect.left;
                    let newPct = (deltaX / rect.width) * 100;
                    newPct = Math.max(0, Math.min(100, newPct));
                    marker.style.left = `${newPct}%`;
                    
                    const newT = (newPct / 100 * blockingState.duration).toFixed(1);
                    marker.title = `Keyframe at ${newT}s`;
                    
                    // Live scrub while dragging
                    timelineSlider.value = newT;
                    timelineSlider.dispatchEvent(new Event('input'));
                };
                
                const onMouseUp = (ev) => {
                    if (!isDragging) return;
                    isDragging = false;
                    window.removeEventListener('mousemove', onMouseMove);
                    window.removeEventListener('mouseup', onMouseUp);
                    
                    if (hasMoved) {
                        const deltaX = ev.clientX - rect.left;
                        let newPct = (deltaX / rect.width) * 100;
                        newPct = Math.max(0, Math.min(100, newPct));
                        const newT = (newPct / 100 * blockingState.duration).toFixed(1);
                        
                        if (newT !== tStr) {
                            // Move keyframe
                            blockingState.keyframes[trackId][newT] = blockingState.keyframes[trackId][tStr];
                            delete blockingState.keyframes[trackId][tStr];
                            saveBlockingToLocalStorage();
                            
                            // If we moved the selected one, keep it selected
                            if (selectedKeyframeTime === tStr && selectedKeyframeTrack === trackId) {
                                selectedKeyframeTime = newT;
                            }
                            updateKeyframeMarkers();
                        }
                    } else {
                        // Just a click
                        selectedKeyframeTime = tStr;
                        selectedKeyframeTrack = trackId;
                        updateKeyframeMarkers();
                        timelineSlider.value = t;
                        timelineSlider.dispatchEvent(new Event('input'));
                    }
                };
                
                window.addEventListener('mousemove', onMouseMove);
                window.addEventListener('mouseup', onMouseUp);
            });
            
            container.appendChild(marker);
        }
    });
}

function drawTrackSpan(container, startT, endT) {
    const startPct = (startT / blockingState.duration) * 100;
    const endPct = (endT / blockingState.duration) * 100;
    const width = endPct - startPct;
    
    if (width <= 0) return;
    
    const span = document.createElement('div');
    span.style.position = 'absolute';
    span.style.top = '6px';
    span.style.bottom = '6px';
    span.style.left = `${startPct}%`;
    span.style.width = `${width}%`;
    span.style.background = 'rgba(231, 76, 60, 0.3)'; // Red-ish
    span.style.borderLeft = '2px solid rgba(231, 76, 60, 0.8)';
    span.style.borderRadius = '0 4px 4px 0';
    span.style.pointerEvents = 'none';
    
    container.appendChild(span);
}

function interpolateAndRender(t) {
    // 1. Director Track Interpolation
    let dirPrev = 0;
    if (blockingState.keyframes.director) {
        const dirTimes = Object.keys(blockingState.keyframes.director).map(parseFloat).sort((a,b)=>a-b);
        for (let i = 0; i < dirTimes.length; i++) {
            if (t >= dirTimes[i]) dirPrev = dirTimes[i];
        }
        
        const dirState = blockingState.keyframes.director[dirPrev.toFixed(1)] || {};
        
        const camSelect = document.getElementById('active-camera-select');
        if (camSelect) camSelect.value = dirState.activeCamera || "none";
        
        const shotSelect = document.getElementById('active-shot-select');
        if (shotSelect) shotSelect.value = dirState.activeShot || "";
        
        const shotBg = document.getElementById('active-shot-bg-tag');
        if (shotBg) {
            shotBg.value = dirState.shotBgTag || "";
            if (window.updateBackgroundDropdown) window.updateBackgroundDropdown();
        }
    }

    // 2. Entity Tracks Interpolation
    Object.keys(blockingState.entities).forEach(id => {
        const track = blockingState.keyframes[id];
        if (!track) return;
        
        const times = Object.keys(track).map(parseFloat).sort((a,b)=>a-b);
        if (times.length === 0) return;
        
        let t0 = times[0];
        let t1 = times[times.length - 1];
        
        if (t <= t0) {
            const state = track[t0.toFixed(1)];
            updateEntityTransform(id, state.x, state.y, state.rot, state.fov);
            return;
        }
        if (t >= t1) {
            const state = track[t1.toFixed(1)];
            updateEntityTransform(id, state.x, state.y, state.rot, state.fov);
            return;
        }
        
        let prev = t0, next = t1;
        for (let i = 0; i < times.length - 1; i++) {
            if (t >= times[i] && t <= times[i+1]) {
                prev = times[i];
                next = times[i+1];
                break;
            }
        }
        
        const prevStr = prev.toFixed(1);
        const nextStr = next.toFixed(1);
        const factor = (t - prev) / (next - prev);
        
        const kfPrev = track[prevStr];
        const kfNext = track[nextStr];
        
        if (kfPrev && kfNext) {
            const x = kfPrev.x + (kfNext.x - kfPrev.x) * factor;
            const y = kfPrev.y + (kfNext.y - kfPrev.y) * factor;
            
            let rotDiff = kfNext.rot - kfPrev.rot;
            while (rotDiff > 180) rotDiff -= 360;
            while (rotDiff < -180) rotDiff += 360;
            const rot = kfPrev.rot + rotDiff * factor;
            
            const fov = kfPrev.fov + (kfNext.fov - kfPrev.fov) * factor;
            
            updateEntityTransform(id, x, y, rot, fov);
        } else if (kfPrev) {
            updateEntityTransform(id, kfPrev.x, kfPrev.y, kfPrev.rot, kfPrev.fov);
        }
    });
    
    updateCameraOpacities();
    updateSpotlightMask();
}

function updateSpotlightMask() {
    const maskHoles = document.getElementById('spotlight-holes');
    const overlay = document.getElementById('spotlight-overlay');
    if (!maskHoles || !overlay) return;
    
    let hasShapes = false;
    let svgContent = '';
    
    Object.keys(blockingState.entities).forEach(id => {
        const ent = blockingState.entities[id];
        if (ent.type.startsWith('shape-')) {
            hasShapes = true;
            const x = parseFloat(ent.elem.dataset.x || 50);
            const y = parseFloat(ent.elem.dataset.y || 50);
            const rot = parseFloat(ent.elem.dataset.rot || 0);
            const fov = parseFloat(ent.elem.dataset.fov || 100);
            
            if (ent.type === 'shape-rect') {
                svgContent += `<svg x="\${x}%" y="\${y}%" overflow="visible"><g transform="rotate(\${rot})"><rect x="-\${fov/2}" y="-\${fov/2}" width="\${fov}" height="\${fov}" fill="black" /></g></svg>`;
            } else if (ent.type === 'shape-circle') {
                svgContent += `<svg x="\${x}%" y="\${y}%" overflow="visible"><circle cx="0" cy="0" r="\${fov/2}" fill="black" /></svg>`;
            } else if (ent.type === 'shape-line') {
                svgContent += `<svg x="\${x}%" y="\${y}%" overflow="visible"><g transform="rotate(\${rot})"><rect x="-\${fov/2}" y="-2" width="\${fov}" height="4" fill="black" /></g></svg>`;
            }
        }
    });
    
    maskHoles.innerHTML = svgContent;
    overlay.style.display = hasShapes ? 'block' : 'none';
}

function updateCameraOpacities() {
    const camSelect = document.getElementById('active-camera-select');
    const activeCam = camSelect ? camSelect.value : 'none';
    
    Object.keys(blockingState.entities).forEach(id => {
        const ent = blockingState.entities[id];
        if (ent.type === 'camera') {
            const dot = document.getElementById(`active-dot-${id}`);
            if (activeCam === id) {
                ent.elem.style.opacity = '1';
                ent.elem.style.filter = 'none';
                if (dot) dot.style.display = 'block';
            } else if (activeCam === 'none') {
                ent.elem.style.opacity = '1';
                ent.elem.style.filter = 'none';
                if (dot) dot.style.display = 'none';
            } else {
                ent.elem.style.opacity = '0.3';
                ent.elem.style.filter = 'grayscale(100%)';
                if (dot) dot.style.display = 'none';
            }
        }
    });
}

window.getBlockingExportData = function() {
    // Format data for backend
    const tracks = {};
    const metadata = {
        projectBgTag: "",
        directorTrack: []
    };
    
    // Process Director Track
    if (blockingState.keyframes.director) {
        Object.keys(blockingState.keyframes.director).forEach(tStr => {
            const dirState = blockingState.keyframes.director[tStr];
            metadata.directorTrack.push({
                time: parseFloat(tStr),
                activeCamera: dirState.activeCamera,
                activeShot: dirState.activeShot,
                shotBgTag: dirState.shotBgTag
            });
        });
        metadata.directorTrack.sort((a, b) => a.time - b.time);
    }
    
    // Process Entities
    Object.keys(blockingState.entities).forEach(id => {
        const ent = blockingState.entities[id];
        tracks[id] = [];
        
        if (blockingState.keyframes[id]) {
            Object.keys(blockingState.keyframes[id]).forEach(tStr => {
                const kf = blockingState.keyframes[id][tStr];
                const t = parseFloat(tStr);
                
                // Determine if this camera is active at this time
                let isActiveCamera = false;
                let displayLabel = ent.label;
                
                // Find active camera at this exact time from director track
                if (ent.type === 'camera' && blockingState.keyframes.director) {
                    const dirKeys = Object.keys(blockingState.keyframes.director).map(parseFloat).sort((a,b)=>a-b);
                    let activeAtTime = "none";
                    let shotAtTime = "";
                    for (let i = 0; i < dirKeys.length; i++) {
                        if (t >= dirKeys[i]) {
                            const dState = blockingState.keyframes.director[dirKeys[i].toFixed(1)];
                            activeAtTime = dState.activeCamera;
                            shotAtTime = dState.activeShot;
                        }
                    }
                    if (activeAtTime === id) {
                        isActiveCamera = true;
                        if (shotAtTime) displayLabel = `[${shotAtTime}] ${ent.label}`;
                    }
                }
                
                tracks[id].push({
                    time: t,
                    x: kf.x / 100.0, // Normalize to 0-1 for backend
                    y: kf.y / 100.0,
                    rot: kf.rot,
                    fov: kf.fov,
                    type: ent.type,
                    label: displayLabel,
                    assetTag: ent.assetTag || "",
                    color: ent.elem.dataset.color || null,
                    isActiveCamera: isActiveCamera
                });
            });
            tracks[id].sort((a, b) => a.time - b.time);
        }
    });
    
    return {
        tracks: JSON.stringify(tracks),
        metadata: JSON.stringify(metadata),
        duration: blockingState.duration
    };
};

// --- Project Manager ---

function getSavedProjects() {
    try {
        const listStr = localStorage.getItem('ad_projects_list');
        return listStr ? JSON.parse(listStr) : [];
    } catch(e) { return []; }
}

function saveProjectsList(list) {
    localStorage.setItem('ad_projects_list', JSON.stringify(list));
}

function getTrashProjects() {
    try {
        const listStr = localStorage.getItem('ad_trash_projects_list');
        return listStr ? JSON.parse(listStr) : [];
    } catch(e) { return []; }
}

function saveTrashProjectsList(list) {
    localStorage.setItem('ad_trash_projects_list', JSON.stringify(list));
}

window.saveCurrentAsNewProject = function() {
    const name = prompt("Enter new project name:");
    if (!name) return;
    
    const currentData = localStorage.getItem('ad_blocking_project');
    if (!currentData) {
        alert("Current workspace is empty!");
        return;
    }
    
    const id = 'proj_' + Date.now();
    localStorage.setItem('ad_blocking_project_' + id, currentData);
    
    const list = getSavedProjects();
    list.unshift({ id, name, lastSaved: new Date().toLocaleString() });
    saveProjectsList(list);
    
    renderProjectList();
};

window.loadSavedProject = function(id) {
    const data = localStorage.getItem('ad_blocking_project_' + id);
    if (data) {
        if (confirm("Load this project? Current unsaved changes in Auto-Save will be overwritten by this loaded project.")) {
            restoreStateFromJSON(data);
            document.querySelectorAll('.project-item').forEach(el => el.classList.remove('active'));
            const el = document.getElementById('proj-item-' + id);
            if (el) el.classList.add('active');
        }
    } else {
        alert("Project data not found!");
    }
};

window.deleteSavedProject = function(event, id) {
    if (event) event.stopPropagation();
    if (confirm("Move this project to Recycle Bin?")) {
        let list = getSavedProjects();
        const p = list.find(x => x.id === id);
        if (p) {
            let trash = getTrashProjects();
            trash.unshift(p);
            saveTrashProjectsList(trash);
        }
        
        list = list.filter(x => x.id !== id);
        saveProjectsList(list);
        
        renderProjectList();
        renderTrashList();
    }
};

window.restoreFromTrash = function(event, id) {
    if (event) event.stopPropagation();
    let trash = getTrashProjects();
    const p = trash.find(x => x.id === id);
    if (p) {
        let list = getSavedProjects();
        list.unshift(p);
        saveProjectsList(list);
    }
    trash = trash.filter(x => x.id !== id);
    saveTrashProjectsList(trash);
    
    renderProjectList();
    renderTrashList();
};

window.deletePermanently = function(event, id) {
    if (event) event.stopPropagation();
    if (confirm("Delete this project permanently?")) {
        localStorage.removeItem('ad_blocking_project_' + id);
        let trash = getTrashProjects();
        trash = trash.filter(x => x.id !== id);
        saveTrashProjectsList(trash);
        renderTrashList();
    }
};

window.emptyTrash = function() {
    if (confirm("Empty recycle bin? All deleted projects will be lost forever.")) {
        let trash = getTrashProjects();
        trash.forEach(p => localStorage.removeItem('ad_blocking_project_' + p.id));
        saveTrashProjectsList([]);
        renderTrashList();
    }
};

function renderProjectList() {
    const list = getSavedProjects();
    const container = document.getElementById('project-list-saved');
    if (!container) return;
    
    container.innerHTML = '';
    
    if (list.length === 0) {
        container.innerHTML = '<div style="font-size: 0.8rem; color: rgba(255,255,255,0.3);">No saved projects yet.</div>';
        return;
    }
    
    list.forEach(p => {
        const item = document.createElement('div');
        item.className = 'project-item';
        item.id = 'proj-item-' + p.id;
        item.style.cssText = 'background: rgba(0,0,0,0.5); border: 1px solid var(--border-color); padding: 0.5rem; border-radius: 6px; cursor: pointer; display: flex; justify-content: space-between; align-items: center;';
        
        item.innerHTML = `
            <div style="flex: 1; overflow: hidden;" onclick="loadSavedProject('${p.id}')">
                <div style="font-weight: bold; font-size: 0.85rem; color: white; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${p.name}</div>
                <div style="font-size: 0.65rem; color: rgba(255,255,255,0.5);">${p.lastSaved}</div>
            </div>
            <button class="btn btn-secondary" style="padding: 2px 5px; font-size: 0.7rem;" onclick="deleteSavedProject(event, '${p.id}')">🗑️</button>
        `;
        container.appendChild(item);
    });
}

const newProjBtn = document.getElementById('blocking-new-project-btn');
if (newProjBtn) {
    newProjBtn.addEventListener('click', saveCurrentAsNewProject);
}

const autoSaveBtn = document.getElementById('load-autosave-btn');
if (autoSaveBtn) {
    autoSaveBtn.addEventListener('click', () => {
        if (confirm("Reload from Auto-Save?")) {
            loadBlockingFromLocalStorage();
            document.querySelectorAll('.project-item').forEach(el => el.classList.remove('active'));
            autoSaveBtn.classList.add('active');
        }
    });
}

const clearAutoSaveBtn = document.getElementById('clear-autosave-btn');
if (clearAutoSaveBtn) {
    clearAutoSaveBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (confirm("Clear current workspace? It will be moved to the Recycle Bin as a backup.")) {
            // Backup to recycle bin
            const currentData = localStorage.getItem('ad_blocking_project');
            if (currentData) {
                const id = 'proj_auto_' + Date.now();
                localStorage.setItem('ad_blocking_project_' + id, currentData);
                let trash = getTrashProjects();
                trash.unshift({ id, name: "Auto-Saved Backup", lastSaved: new Date().toLocaleString() });
                saveTrashProjectsList(trash);
                renderTrashList();
            }
            
            // Clear without triggering another confirm
            blockingState.entities = {};
            blockingState.keyframes = { director: {} };
            blockingState.currentTime = 0;
            saveBlockingToLocalStorage();
            loadBlockingFromLocalStorage();
        }
    });
}

const emptyTrashBtn = document.getElementById('empty-trash-btn');
if (emptyTrashBtn) {
    emptyTrashBtn.addEventListener('click', window.emptyTrash);
}

function renderTrashList() {
    const list = getTrashProjects();
    const container = document.getElementById('project-list-trash');
    const emptyBtn = document.getElementById('empty-trash-btn');
    if (!container) return;
    
    container.innerHTML = '';
    
    if (list.length === 0) {
        if (emptyBtn) emptyBtn.style.display = 'none';
        return;
    }
    
    if (emptyBtn) emptyBtn.style.display = 'block';
    
    list.forEach(p => {
        const item = document.createElement('div');
        item.className = 'project-item trash-item';
        item.style.cssText = 'background: rgba(231, 76, 60, 0.1); border: 1px dashed rgba(231, 76, 60, 0.5); padding: 0.5rem; border-radius: 6px; display: flex; justify-content: space-between; align-items: center;';
        
        item.innerHTML = `
            <div style="flex: 1; overflow: hidden; opacity: 0.7;">
                <div style="font-weight: bold; font-size: 0.85rem; color: #e74c3c; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${p.name}</div>
                <div style="font-size: 0.65rem; color: rgba(255,255,255,0.5);">Deleted</div>
            </div>
            <div style="display: flex; gap: 5px;">
                <button class="btn btn-secondary" style="padding: 2px 5px; font-size: 0.7rem; background: rgba(46, 204, 113, 0.2); border: none;" onclick="restoreFromTrash(event, '${p.id}')" title="Restore">🔄</button>
                <button class="btn btn-secondary" style="padding: 2px 5px; font-size: 0.7rem; background: rgba(231, 76, 60, 0.2); border: none;" onclick="deletePermanently(event, '${p.id}')" title="Delete Permanently">❌</button>
            </div>
        `;
        container.appendChild(item);
    });
}

const style = document.createElement('style');
style.innerHTML = `
    .project-item:hover { background: rgba(255,255,255,0.1) !important; }
    .project-item.active { border-color: #3498db !important; box-shadow: 0 0 5px rgba(52, 152, 219, 0.5); }
    .trash-item:hover { background: rgba(231, 76, 60, 0.2) !important; }
`;
document.head.appendChild(style);

renderProjectList();
renderTrashList();

function generatePrompt() {
    let prompt = "";
    let pBgTag = "";
    const activeShotBg = document.getElementById('active-shot-bg-tag');
    if (activeShotBg && activeShotBg.value) {
        pBgTag = activeShotBg.value;
    }
    pBgTag = pBgTag || "N/A";
    
    // [REFERENCE]
    prompt += "[REFERENCE]\n";
    prompt += `{background: "${pBgTag}", tag: "[M-LOC_INT_MODERN_OFFICE]"}\n\n`;
    
    // Get current time state
    const tStr = blockingState.currentTime.toFixed(1);
    
    // [STAGE MAP — LOCKED]
    prompt += "[STAGE MAP — LOCKED]\n";
    Object.keys(blockingState.entities).forEach(id => {
        const ent = blockingState.entities[id];
        if (ent.type === 'character') {
            const state = getEntityCurrentTransform(id);
            // Translate X, Y (0-100) to logical coordinates (-1 to 1 roughly)
            const x = ((state.x - 50) / 50).toFixed(2);
            const z = ((state.y - 50) / 50).toFixed(2); // In top down, Y is depth (Z)
            const tag = ent.assetTag || `@${ent.label.toUpperCase().replace(/\s+/g, '_')}`;
            prompt += `{character: "${tag}", x: ${x}, y: 0.0, z: ${z}, direction: "facing rot ${state.rot.toFixed(0)}"}\n`;
        }
    });
    prompt += "\n";
    
    // [EYELINE LOCK]
    prompt += "[EYELINE LOCK]\n";
    prompt += "// Auto-generated eyelines would go here\n\n";
    
    // [CAMERA PATH]
    prompt += "[CAMERA PATH]\n";
    Object.keys(blockingState.entities).forEach(id => {
        const ent = blockingState.entities[id];
        if (ent.type === 'camera') {
            const state = getEntityCurrentTransform(id);
            const x = ((state.x - 50) / 50).toFixed(2);
            const z = ((state.y - 50) / 50).toFixed(2);
            const tag = ent.assetTag || ent.label.toUpperCase().replace(/\s+/g, '_');
            
            // Check if active
            const camSelect = document.getElementById('active-camera-select');
            const isActive = camSelect && camSelect.value === id;
            const prefix = isActive ? "*ACTIVE* " : "";
            
            prompt += `{camera: "${prefix}${tag}", type: "static", x: ${x}, y: 1.5, z: ${z}, fov: ${state.fov.toFixed(0)}, pan: ${state.rot.toFixed(0)}, tilt: 0}\n`;
        }
    });
    prompt += "\n";
    
    // [ACTION SEQUENCE]
    prompt += "[ACTION SEQUENCE]\n";
    prompt += "- Enter action details here based on the timeline.\n";
    
    // Show in modal
    const modal = document.getElementById('modal-container');
    const output = document.getElementById('prompt-output');
    if (modal && output) {
        output.value = prompt;
        modal.style.display = 'flex';
        
        document.getElementById('close-modal-btn').onclick = () => {
            modal.style.display = 'none';
        };
        
        document.getElementById('copy-prompt-btn').onclick = () => {
            output.select();
            document.execCommand('copy');
            alert("Prompt copied to clipboard!");
        };
    } else {
        console.log(prompt);
        alert("Prompt generated! Check console.");
    }
}

function importPromptToBlocking(text) {
    if (!text || text.trim() === '') return;

    let inStageMap = false;
    let inCameraPath = false;
    
    const lines = text.split('\n');
    let activeCameraId = null;
    
    // Auto-Save before import just in case
    saveBlockingToLocalStorage();
    
    for (const line of lines) {
        const t = line.trim();
        
        // Parse Background Tag
        if (t.startsWith('{background:')) {
            const bgMatch = t.match(/background:\s*"([^"]+)"/);
            if (bgMatch && bgMatch[1] !== "N/A") {
                const activeShotBg = document.getElementById('active-shot-bg-tag');
                if (activeShotBg) activeShotBg.value = bgMatch[1];
            }
        }
        
        if (t === '[STAGE MAP — LOCKED]') {
            inStageMap = true;
            inCameraPath = false;
            continue;
        }
        if (t === '[CAMERA PATH]') {
            inStageMap = false;
            inCameraPath = true;
            continue;
        }
        if (t.startsWith('[')) {
            inStageMap = false;
            inCameraPath = false;
            continue;
        }
        
        if (inStageMap && t.startsWith('{character:')) {
            const charMatch = t.match(/character:\s*"([^"]+)"/);
            const xMatch = t.match(/x:\s*([-\d.]+)/);
            const zMatch = t.match(/z:\s*([-\d.]+)/);
            const dirMatch = t.match(/rot\s*([-\d.]+)/);
            
            if (charMatch && xMatch && zMatch) {
                const tag = charMatch[1]; // e.g. @ACTOR_1
                const label = tag.replace(/^@/, '').replace(/_/g, ' ');
                const xVal = parseFloat(xMatch[1]);
                const zVal = parseFloat(zMatch[1]);
                let rot = 0;
                if (dirMatch) rot = parseFloat(dirMatch[1]);
                
                const px = (xVal * 50) + 50;
                const pz = (zVal * 50) + 50;
                
                let entId = Object.keys(blockingState.entities).find(id => blockingState.entities[id].type === 'character' && blockingState.entities[id].label === label);
                if (!entId) {
                    entId = 'char_' + Date.now() + Math.floor(Math.random() * 1000);
                    addEntity('character', label, '#3498db', tag, entId, px, pz, rot, 100);
                } else {
                    updateEntityTransform(entId, px, pz, rot, 100);
                }
            }
        }
        
        if (inCameraPath && t.startsWith('{camera:')) {
            const camMatch = t.match(/camera:\s*"([^"]+)"/);
            const xMatch = t.match(/x:\s*([-\d.]+)/);
            const zMatch = t.match(/z:\s*([-\d.]+)/);
            const panMatch = t.match(/pan:\s*([-\d.]+)/);
            const fovMatch = t.match(/fov:\s*([-\d.]+)/);
            
            if (camMatch && xMatch && zMatch) {
                let label = camMatch[1];
                let isActive = false;
                if (label.includes("*ACTIVE*")) {
                    isActive = true;
                    label = label.replace("*ACTIVE*", "").trim();
                }
                
                const tag = label;
                const cleanLabel = label.replace(/_/g, ' ');
                
                const xVal = parseFloat(xMatch[1]);
                const zVal = parseFloat(zMatch[1]);
                let pan = 0;
                if (panMatch) pan = parseFloat(panMatch[1]);
                let fov = 100;
                if (fovMatch) fov = parseFloat(fovMatch[1]);
                
                const px = (xVal * 50) + 50;
                const pz = (zVal * 50) + 50;
                
                let entId = Object.keys(blockingState.entities).find(id => blockingState.entities[id].type === 'camera' && blockingState.entities[id].label === cleanLabel);
                if (!entId) {
                    entId = 'cam_' + Date.now() + Math.floor(Math.random() * 1000);
                    addEntity('camera', cleanLabel, null, tag, entId, px, pz, pan, fov);
                } else {
                    updateEntityTransform(entId, px, pz, pan, fov);
                }
                
                if (isActive) {
                    activeCameraId = entId;
                }
            }
        }
    }
    
    if (activeCameraId) {
        const camSelect = document.getElementById('active-camera-select');
        if (camSelect) {
            camSelect.value = activeCameraId;
            camSelect.dispatchEvent(new Event('change'));
            
            const tStr = blockingState.currentTime.toFixed(1);
            if (!blockingState.keyframes.director) blockingState.keyframes.director = {};
            blockingState.keyframes.director[tStr] = { activeCamera: activeCameraId };
        }
    }
    
    saveToKeyframes();
    interpolateAndRender(blockingState.currentTime);
}

const importPromptBtn = document.getElementById('blocking-import-prompt-btn');
const importModal = document.getElementById('import-prompt-modal');
const closeImportBtn = document.getElementById('close-import-modal-btn');
const applyImportBtn = document.getElementById('apply-import-btn');
const importInput = document.getElementById('import-prompt-input');

if (importPromptBtn && importModal) {
    importPromptBtn.addEventListener('click', () => {
        importInput.value = '';
        importModal.style.display = 'flex';
    });
    closeImportBtn.addEventListener('click', () => {
        importModal.style.display = 'none';
    });
    applyImportBtn.addEventListener('click', () => {
        importPromptToBlocking(importInput.value);
        importModal.style.display = 'none';
    });
}

initBlocking();
