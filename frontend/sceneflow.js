// SceneFlow Studio — Real-Time Screenplay-to-Video Synchronization & Cue Alignment
(function() {
    'use strict';

    const CUE_COLORS = {
        dialogue: { color: "#eab308", badge: "🟡 Dialogue", bg: "rgba(234, 179, 8, 0.15)", border: "#eab308" },
        action: { color: "#3b82f6", badge: "🔵 Action", bg: "rgba(59, 130, 246, 0.15)", border: "#3b82f6" },
        camera: { color: "#22c55e", badge: "🟢 Camera", bg: "rgba(34, 197, 94, 0.15)", border: "#22c55e" },
        shot: { color: "#a855f7", badge: "🟣 Shot", bg: "rgba(168, 85, 247, 0.15)", border: "#a855f7" },
        audio: { color: "#f97316", badge: "🟠 Audio", bg: "rgba(249, 115, 22, 0.15)", border: "#f97316" },
        vfx: { color: "#06b6d4", badge: "🔷 VFX", bg: "rgba(6, 182, 212, 0.15)", border: "#06b6d4" },
        transition: { color: "#ec4899", badge: "🩷 Transition", bg: "rgba(236, 72, 153, 0.15)", border: "#ec4899" },
        environment: { color: "#94a3b8", badge: "⚪ Environment", bg: "rgba(148, 163, 184, 0.15)", border: "#94a3b8" }
    };

    const DEMO_SCRIPTS = {
        scifi: `INT. NEURAL LAB - NIGHT
[CAMERA: SLOW PAN LEFT ACROSS GLOWING TERMINALS]
DR. ARIS: "The neural sync sequence is finally stable."
SARAH (tense): "Are you certain? We cannot afford another power surge."
[VFX: HOLOGRAPHIC DATA RIPPLES IN CYAN PARTICLES]
Dr. Aris reaches forward and flips the primary breaker switch.
[SFX: HEAVY POWER GENERATOR HUMMING]
DR. ARIS: "Look at the telemetry. Signal coherence is at ninety-eight percent."
CUT TO:
EXT. CITY ROOFTOP - DAWN
WIDE SHOT of neon metropolis awakening under morning rain.`,
        chase: `EXT. CYBERPUNK ALLEYWAY - NIGHT
[CAMERA: TRACKING SHOT FOLLOWING RUNNING FOOTSTEPS]
KAI (panting): "They've locked down the north perimeter!"
Rain slashes across neon signs reflecting in puddles.
[SFX: SIRENS WAILING IN THE DISTANCE]
[VFX: DRONE SEARCHLIGHT BEAMS CUTTING THROUGH STEAM]
Kai vaults over a rusted dumpster and dives into a shadowy doorway.
KAI: "Ten seconds to breach the firewall... stay with me."
[CAMERA: RAPID TILT UP TO ROOFTOP DRONES]
FADE OUT.`
    };

    let currentProject = null;
    let autoScrollEnabled = true;
    let activeFilter = 'all';

    document.addEventListener('DOMContentLoaded', () => {
        initSceneFlow();
    });

    function initSceneFlow() {
        const videoFileInput = document.getElementById('sceneflow-video-file');
        const scriptInput = document.getElementById('sceneflow-script-input');
        const alignBtn = document.getElementById('sceneflow-align-btn');
        const demoSelect = document.getElementById('sceneflow-demo-select');
        const loadDemoBtn = document.getElementById('sceneflow-load-demo-btn');
        const dropzone = document.getElementById('sceneflow-video-dropzone');
        const dropzoneText = document.getElementById('sceneflow-dropzone-text');

        const studioContainer = document.getElementById('sceneflow-studio-container');
        const player = document.getElementById('sceneflow-player');
        const scriptViewer = document.getElementById('sceneflow-script-viewer');
        const timecodeDisplay = document.getElementById('sceneflow-live-timecode');
        const cueTimeline = document.getElementById('sceneflow-timeline-bar');
        const autoScrollToggle = document.getElementById('sceneflow-autoscroll-toggle');

        const filterChips = document.querySelectorAll('.sceneflow-filter-chip');
        const exportJsonBtn = document.getElementById('sceneflow-export-btn');
        const importJsonBtn = document.getElementById('sceneflow-import-btn');
        const importFileInput = document.getElementById('sceneflow-import-file');
        const toggleEditorBtn = document.getElementById('sceneflow-toggle-editor-btn');
        const editorContainer = document.getElementById('sceneflow-editor-container');
        const editorTableBody = document.getElementById('sceneflow-editor-tbody');
        const applyEditorBtn = document.getElementById('sceneflow-apply-editor-btn');
        const addCueBtn = document.getElementById('sceneflow-add-cue-btn');

        // Dropzone file handling
        if (dropzone && videoFileInput) {
            dropzone.addEventListener('click', () => videoFileInput.click());
            dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
            dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
            dropzone.addEventListener('drop', (e) => {
                e.preventDefault();
                dropzone.classList.remove('dragover');
                if (e.dataTransfer.files.length) {
                    videoFileInput.files = e.dataTransfer.files;
                    if (dropzoneText) dropzoneText.innerText = '✅ ' + e.dataTransfer.files[0].name;
                }
            });
            videoFileInput.addEventListener('change', () => {
                if (videoFileInput.files.length && dropzoneText) {
                    dropzoneText.innerText = '✅ ' + videoFileInput.files[0].name;
                }
            });
        }

        // Script Document (PDF/TXT/Fountain) Upload
        const uploadDocBtn = document.getElementById('sceneflow-upload-doc-btn');
        const docFileInput = document.getElementById('sceneflow-doc-file');
        if (uploadDocBtn && docFileInput && scriptInput) {
            uploadDocBtn.addEventListener('click', () => docFileInput.click());
            docFileInput.addEventListener('change', async (e) => {
                if (e.target.files.length) {
                    const docFile = e.target.files[0];
                    const originalBtnText = uploadDocBtn.innerText;
                    uploadDocBtn.disabled = true;
                    uploadDocBtn.innerText = '⏳ Extracting...';

                    try {
                        const formData = new FormData();
                        formData.append('file', docFile);

                        const resp = await fetch(`${window.location.origin}/sceneflow/extract_document`, {
                            method: 'POST',
                            body: formData
                        });

                        const resData = await resp.json();
                        if (!resp.ok || resData.status === 'error') {
                            throw new Error(resData.message || 'Failed to extract text from document.');
                        }

                        scriptInput.value = resData.text;
                        alert(`✅ Successfully loaded script from "${docFile.name}"!`);
                    } catch (err) {
                        alert('Document Extraction Error: ' + err.message);
                    } finally {
                        uploadDocBtn.disabled = false;
                        uploadDocBtn.innerText = originalBtnText;
                        docFileInput.value = '';
                    }
                }
            });
        }

        // Load Demo Scripts
        if (loadDemoBtn && demoSelect && scriptInput) {
            loadDemoBtn.addEventListener('click', () => {
                const key = demoSelect.value;
                if (DEMO_SCRIPTS[key]) {
                    scriptInput.value = DEMO_SCRIPTS[key];
                }
            });
        }

        // Align Button Click
        if (alignBtn) {
            alignBtn.addEventListener('click', async () => {
                const file = videoFileInput && videoFileInput.files.length ? videoFileInput.files[0] : null;
                const scriptText = scriptInput ? scriptInput.value.trim() : '';

                if (!file) {
                    alert('Please select or drop a video file first.');
                    return;
                }
                if (!scriptText) {
                    alert('Please enter or paste your screenplay script text.');
                    return;
                }

                alignBtn.disabled = true;
                alignBtn.innerText = '⏳ Analyzing Audio & Aligning Script...';

                try {
                    const formData = new FormData();
                    formData.append('video', file);
                    formData.append('script_text', scriptText);

                    const resp = await fetch(`${window.location.origin}/sceneflow/align_video_script`, {
                        method: 'POST',
                        body: formData
                    });

                    const data = await resp.json();
                    if (!resp.ok || data.status === 'error') {
                        throw new Error(data.message || 'Failed to align video and script.');
                    }

                    currentProject = data;
                    renderSceneFlowStudio(data);

                    if (studioContainer) {
                        studioContainer.classList.remove('hidden');
                        studioContainer.scrollIntoView({ behavior: 'smooth' });
                    }
                } catch (err) {
                    console.error('SceneFlow Error:', err);
                    alert('SceneFlow Alignment Error: ' + err.message);
                } finally {
                    alignBtn.disabled = false;
                    alignBtn.innerText = '✨ Generate & Auto-Align Script';
                }
            });
        }

        // Video Player Time Update Sync
        if (player) {
            player.addEventListener('timeupdate', () => {
                const cur = player.currentTime;
                if (timecodeDisplay) {
                    timecodeDisplay.innerText = formatTimecode(cur);
                }
                syncScriptPlayback(cur);
                updateTimelineProgress(cur);
            });
        }

        // Auto-Scroll Toggle
        if (autoScrollToggle) {
            autoScrollToggle.addEventListener('change', () => {
                autoScrollEnabled = autoScrollToggle.checked;
            });
        }

        // Filter Chips
        filterChips.forEach(chip => {
            chip.addEventListener('click', () => {
                filterChips.forEach(c => c.classList.remove('active'));
                chip.classList.add('active');
                activeFilter = chip.dataset.type || 'all';
                applyCueFilter();
            });
        });

        // Toggle Timecode Editor
        if (toggleEditorBtn && editorContainer) {
            toggleEditorBtn.addEventListener('click', () => {
                editorContainer.classList.toggle('hidden');
                toggleEditorBtn.innerText = editorContainer.classList.contains('hidden') 
                    ? '✏️ Edit Timecodes' 
                    : '👁️ Hide Timecode Editor';
            });
        }

        // Apply Manual Timecode Edits
        if (applyEditorBtn) {
            applyEditorBtn.addEventListener('click', () => {
                if (!currentProject || !currentProject.cues) return;
                const rows = editorTableBody.querySelectorAll('tr');
                const updatedCues = [];

                rows.forEach((row, i) => {
                    const typeSel = row.querySelector('.cue-edit-type');
                    const startInp = row.querySelector('.cue-edit-start');
                    const endInp = row.querySelector('.cue-edit-end');
                    const textInp = row.querySelector('.cue-edit-text');

                    const startSec = parseFloat(startInp ? startInp.value : 0) || 0;
                    const endSec = parseFloat(endInp ? endInp.value : 0) || (startSec + 1);
                    const cueType = typeSel ? typeSel.value : 'action';
                    const text = textInp ? textInp.value.trim() : '';

                    updatedCues.push({
                        cue_id: `cue_${String(i + 1).padStart(3, '0')}`,
                        type: cueType,
                        speaker: cueType === 'dialogue' && text.includes(':') ? text.split(':')[0].trim() : null,
                        text: text,
                        start_sec: startSec,
                        end_sec: endSec,
                        timecode_start: formatTimecode(startSec),
                        timecode_end: formatTimecode(endSec),
                        color_info: CUE_COLORS[cueType] || CUE_COLORS['action']
                    });
                });

                currentProject.cues = updatedCues;
                renderSceneFlowScript(currentProject.cues);
                renderTimelineBar(currentProject);
                alert('✅ Timecodes & script sync updated successfully!');
            });
        }

        // Add Cue in Editor
        if (addCueBtn && editorTableBody) {
            addCueBtn.addEventListener('click', () => {
                const count = editorTableBody.querySelectorAll('tr').length;
                const lastRow = editorTableBody.querySelector('tr:last-child');
                let startVal = 0;
                if (lastRow) {
                    const prevEnd = parseFloat(lastRow.querySelector('.cue-edit-end').value) || 0;
                    startVal = prevEnd;
                }
                const newTr = createEditorRow({
                    cue_id: `cue_${String(count + 1).padStart(3, '0')}`,
                    type: 'action',
                    text: 'New action cue',
                    start_sec: startVal,
                    end_sec: startVal + 2.0
                }, count);
                editorTableBody.appendChild(newTr);
            });
        }

        // Export Project JSON
        if (exportJsonBtn) {
            exportJsonBtn.addEventListener('click', () => {
                if (!currentProject) return;
                const jsonStr = JSON.stringify(currentProject, null, 2);
                const blob = new Blob([jsonStr], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = `sceneflow_project_${Date.now()}.json`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(url);
            });
        }

        // Import Project JSON
        if (importJsonBtn && importFileInput) {
            importJsonBtn.addEventListener('click', () => importFileInput.click());
            importFileInput.addEventListener('change', (e) => {
                if (e.target.files.length) {
                    const reader = new FileReader();
                    reader.onload = (event) => {
                        try {
                            const data = JSON.parse(event.target.result);
                            if (data && data.cues) {
                                currentProject = data;
                                renderSceneFlowStudio(data);
                                if (studioContainer) {
                                    studioContainer.classList.remove('hidden');
                                    studioContainer.scrollIntoView({ behavior: 'smooth' });
                                }
                                alert('✅ Project loaded successfully!');
                            } else {
                                throw new Error('Invalid SceneFlow project JSON format.');
                            }
                        } catch (err) {
                            alert('Import Error: ' + err.message);
                        }
                    };
                    reader.readAsText(e.target.files[0]);
                }
            });
        }
    }

    function renderSceneFlowStudio(data) {
        const resultsSection = document.getElementById('results-section');
        const processingSection = document.getElementById('processing-section');
        const videoCompareSection = document.getElementById('video-compare-section');
        const autocutContainer = document.getElementById('autocut-container');
        const autocutSelectionContainer = document.getElementById('autocut-selection-container');
        const downloadBtn = document.getElementById('download-btn');
        const downloadJsonBtn = document.getElementById('download-json-btn');
        const studioContainer = document.getElementById('sceneflow-studio-container');

        if (processingSection) processingSection.classList.add('hidden');
        if (videoCompareSection) videoCompareSection.classList.add('hidden');
        if (autocutContainer) autocutContainer.classList.add('hidden');
        if (autocutSelectionContainer) autocutSelectionContainer.classList.add('hidden');
        if (downloadBtn) downloadBtn.classList.add('hidden');
        if (downloadJsonBtn) downloadJsonBtn.classList.add('hidden');

        if (resultsSection) resultsSection.classList.remove('hidden');
        if (studioContainer) {
            studioContainer.classList.remove('hidden');
            setTimeout(() => {
                studioContainer.scrollIntoView({ behavior: 'smooth' });
            }, 100);
        }

        const player = document.getElementById('sceneflow-player');
        const titleEl = document.getElementById('sceneflow-studio-title');
        const metaShots = document.getElementById('sceneflow-meta-cues');
        const metaDuration = document.getElementById('sceneflow-meta-duration');
        const metaAudioSync = document.getElementById('sceneflow-meta-audiosync');

        if (player && data.video_url) {
            player.src = `${window.location.origin}${data.video_url}?t=${Date.now()}`;
            player.load();
        }

        if (titleEl) titleEl.innerText = `🎬 SceneFlow Studio (${data.total_cues || 0} Synchronized Cues)`;
        if (metaShots) metaShots.innerText = data.total_cues || 0;
        if (metaDuration) metaDuration.innerText = (data.video_duration_sec || 0) + 's';
        if (metaAudioSync) {
            metaAudioSync.innerHTML = data.has_audio_sync 
                ? '<span style="color: #10b981;">✅ Audio Speech Aligned</span>' 
                : '<span style="color: #f59e0b;">⏱️ Pacing Alignment</span>';
        }

        renderSceneFlowScript(data.cues || []);
        renderTimelineBar(data);
        renderEditorTable(data.cues || []);
    }

    function renderSceneFlowScript(cues) {
        const scriptViewer = document.getElementById('sceneflow-script-viewer');
        if (!scriptViewer) return;
        scriptViewer.innerHTML = '';

        cues.forEach((cue, idx) => {
            const card = document.createElement('div');
            card.className = `sceneflow-cue-card cue-type-${cue.type}`;
            card.dataset.cueId = cue.cue_id;
            card.dataset.start = cue.start_sec;
            card.dataset.end = cue.end_sec;
            card.dataset.type = cue.type;

            const colorDef = CUE_COLORS[cue.type] || CUE_COLORS['action'];
            const badgeHtml = `<span class="sceneflow-badge" style="background: ${colorDef.bg}; color: ${colorDef.color}; border: 1px solid ${colorDef.color};">${colorDef.badge}</span>`;
            const timingHtml = `<span class="sceneflow-cue-time">⏱️ ${cue.timecode_start} → ${cue.timecode_end}</span>`;
            const speakerHtml = cue.speaker ? `<span class="sceneflow-speaker-name">${escapeHtml(cue.speaker)}</span>` : '';

            card.innerHTML = `
                <div class="sceneflow-cue-header">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        ${badgeHtml}
                        ${speakerHtml}
                    </div>
                    ${timingHtml}
                </div>
                <div class="sceneflow-cue-text">${escapeHtml(cue.text)}</div>
            `;

            // Click-to-seek
            card.addEventListener('click', () => {
                const player = document.getElementById('sceneflow-player');
                if (player) {
                    player.currentTime = parseFloat(cue.start_sec) || 0;
                    player.play().catch(()=>{});
                }
            });

            scriptViewer.appendChild(card);
        });

        applyCueFilter();
    }

    function syncScriptPlayback(currentTime) {
        const cards = document.querySelectorAll('.sceneflow-cue-card');
        const scriptViewer = document.getElementById('sceneflow-script-viewer');
        let firstActiveCard = null;

        cards.forEach(card => {
            const start = parseFloat(card.dataset.start) || 0;
            const end = parseFloat(card.dataset.end) || 0;

            if (currentTime >= start && currentTime <= end) {
                if (!card.classList.contains('active')) {
                    card.classList.add('active');
                }
                if (!firstActiveCard) firstActiveCard = card;
            } else {
                card.classList.remove('active');
            }
        });

        // Smooth Auto-scroll to active cue
        if (autoScrollEnabled && firstActiveCard && scriptViewer) {
            const cardTop = firstActiveCard.offsetTop;
            const viewerHalf = scriptViewer.clientHeight / 2;
            scriptViewer.scrollTo({
                top: Math.max(0, cardTop - viewerHalf + 40),
                behavior: 'smooth'
            });
        }
    }

    function renderTimelineBar(data) {
        const bar = document.getElementById('sceneflow-timeline-bar');
        if (!bar || !data.video_duration_sec) return;
        bar.innerHTML = '';

        const totalDur = data.video_duration_sec || 1;
        const cues = data.cues || [];

        cues.forEach(cue => {
            const leftPct = (cue.start_sec / totalDur) * 100;
            const widthPct = Math.max(1, ((cue.end_sec - cue.start_sec) / totalDur) * 100);
            const colorDef = CUE_COLORS[cue.type] || CUE_COLORS['action'];

            const segment = document.createElement('div');
            segment.className = 'sceneflow-timeline-tick';
            segment.style.left = `${leftPct}%`;
            segment.style.width = `${widthPct}%`;
            segment.style.backgroundColor = colorDef.color;
            segment.title = `[${colorDef.badge}] ${cue.timecode_start} - ${cue.text}`;

            segment.addEventListener('click', (e) => {
                e.stopPropagation();
                const player = document.getElementById('sceneflow-player');
                if (player) {
                    player.currentTime = cue.start_sec;
                    player.play().catch(()=>{});
                }
            });

            bar.appendChild(segment);
        });
    }

    function updateTimelineProgress(currentTime) {
        const progressEl = document.getElementById('sceneflow-timeline-progress');
        const player = document.getElementById('sceneflow-player');
        if (progressEl && player && player.duration) {
            const pct = (currentTime / player.duration) * 100;
            progressEl.style.width = `${pct}%`;
        }
    }

    function applyCueFilter() {
        const cards = document.querySelectorAll('.sceneflow-cue-card');
        cards.forEach(card => {
            if (activeFilter === 'all' || card.dataset.type === activeFilter) {
                card.style.display = 'block';
            } else {
                card.style.display = 'none';
            }
        });
    }

    function renderEditorTable(cues) {
        const tbody = document.getElementById('sceneflow-editor-tbody');
        if (!tbody) return;
        tbody.innerHTML = '';

        cues.forEach((cue, idx) => {
            const tr = createEditorRow(cue, idx);
            tbody.appendChild(tr);
        });
    }

    function createEditorRow(cue, idx) {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="font-weight: bold; color: var(--text-secondary); text-align: center;">${idx + 1}</td>
            <td>
                <select class="cue-edit-type custom-select" style="padding: 0.35rem 0.5rem; font-size: 0.85rem;">
                    <option value="dialogue" ${cue.type === 'dialogue' ? 'selected' : ''}>🟡 Dialogue</option>
                    <option value="action" ${cue.type === 'action' ? 'selected' : ''}>🔵 Action</option>
                    <option value="camera" ${cue.type === 'camera' ? 'selected' : ''}>🟢 Camera</option>
                    <option value="shot" ${cue.type === 'shot' ? 'selected' : ''}>🟣 Shot</option>
                    <option value="audio" ${cue.type === 'audio' ? 'selected' : ''}>🟠 Audio</option>
                    <option value="vfx" ${cue.type === 'vfx' ? 'selected' : ''}>🔷 VFX</option>
                    <option value="transition" ${cue.type === 'transition' ? 'selected' : ''}>🩷 Transition</option>
                    <option value="environment" ${cue.type === 'environment' ? 'selected' : ''}>⚪ Environment</option>
                </select>
            </td>
            <td><input type="number" step="0.01" class="cue-edit-start" value="${cue.start_sec}" style="width: 75px; padding: 0.35rem; font-size: 0.85rem;"></td>
            <td><input type="number" step="0.01" class="cue-edit-end" value="${cue.end_sec}" style="width: 75px; padding: 0.35rem; font-size: 0.85rem;"></td>
            <td><input type="text" class="cue-edit-text" value="${escapeAttr(cue.text)}" style="width: 100%; padding: 0.35rem; font-size: 0.85rem;"></td>
            <td><button class="btn btn-secondary cue-delete-btn" style="padding: 0.25rem 0.5rem; font-size: 0.8rem; color: #ef4444;">🗑️</button></td>
        `;

        const delBtn = tr.querySelector('.cue-delete-btn');
        if (delBtn) {
            delBtn.addEventListener('click', () => tr.remove());
        }

        return tr;
    }

    function formatTimecode(seconds) {
        if (!seconds || seconds < 0) seconds = 0;
        const hrs = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        const millis = Math.round((seconds - Math.floor(seconds)) * 1000);
        return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}.${String(millis).padStart(3, '0')}`;
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function escapeAttr(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

})();
