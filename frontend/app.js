document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const uploadSection = document.getElementById('upload-section');
    const processingSection = document.getElementById('processing-section');
    const resultsSection = document.getElementById('results-section');
    const colormapSection = document.getElementById('colormap-section');
    const safeModeSection = document.getElementById('safe-mode-section');
    const autocutSection = document.getElementById('autocut-section');
    const blockingSection = document.getElementById('blocking-section');
    const sceneflowSection = document.getElementById('sceneflow-section');
    const sceneflowStudioContainer = document.getElementById('sceneflow-studio-container');
    const resultTitle = document.getElementById('result-title');
    const videoCompareSection = document.getElementById('video-compare-section');

    const originalVideo = document.getElementById('original-video');
    const depthVideo = document.getElementById('depth-video');
    const downloadBtn = document.getElementById('download-btn');
    const downloadJsonBtn = document.getElementById('download-json-btn');
    const resetBtn = document.getElementById('reset-btn');
    const statusText = document.getElementById('status-text');
    const progressDetail = document.getElementById('progress-detail');
    const dropZoneTitle = document.getElementById('drop-zone-title');
    const dropZoneSubtitle = document.getElementById('drop-zone-subtitle');
    const generateActions = document.getElementById('generate-actions');
    const startGenerateBtn = document.getElementById('start-generate-btn');

    const API_URL = window.location.origin;
    let currentVideoId = null;
    let pollInterval = null;
    let selectedMode = 'depth';
    let selectedColormap = 'grayscale';
    let selectedSafeMode = 'none';
    let selectedAutocutCapture = 'mid_frame';

    // Video sync event listener cleanup
    let videoSyncCleanup = null;

    // --- Mode Selection ---
    const modeCards = document.querySelectorAll('.mode-card');
    modeCards.forEach(card => {
        card.addEventListener('click', () => {
            // 3D Playground: direct access without upload
            if (card.dataset.mode === 'playground') {
                window.location.href = 'playground.html';
                return;
            }
            // Storyboard Sketch: direct access to Sketch Studio
            if (card.dataset.mode === 'sketch') {
                window.location.href = 'sketch.html';
                return;
            }
            modeCards.forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');
            card.querySelector('input').checked = true;
            selectedMode = card.dataset.mode;
            updateModeVisibility();
        });
    });

    function updateModeVisibility() {
        // Colormap: only for depth
        if (colormapSection) {
            colormapSection.classList.toggle('hidden', selectedMode !== 'depth');
        }
        // Safe mode: only for depth & 3d_white
        if (safeModeSection) {
            safeModeSection.classList.toggle('hidden', selectedMode !== 'depth' && selectedMode !== '3d_white');
        }
        // Autocut options
        if (autocutSection) {
            autocutSection.classList.toggle('hidden', selectedMode !== 'autocut');
        }
        // Blocking options
        if (blockingSection) {
            blockingSection.classList.toggle('hidden', selectedMode !== 'blocking');
        }
        // SceneFlow options
        if (sceneflowSection) {
            sceneflowSection.classList.toggle('hidden', selectedMode !== 'sceneflow');
        }

        // Drop zone visibility and text
        if (dropZone) {
            dropZone.style.display = (selectedMode === 'sceneflow') ? 'none' : 'block';
        }

        if (selectedMode === 'blocking') {
            if (dropZoneTitle) dropZoneTitle.innerText = "Upload Floor Plan / Top-Down Image";
            if (dropZoneSubtitle) dropZoneSubtitle.innerHTML = 'or <span class="browse-btn">browse files</span><br>Use the Blocking Editor below to add characters.';
        } else {
            if (dropZoneTitle) dropZoneTitle.innerText = "Drag & Drop your video";
            if (dropZoneSubtitle) dropZoneSubtitle.innerHTML = 'or <span class="browse-btn">browse files</span><br>Supports MP4, AVI, MOV (Max 50MB recommended)';
        }

        // Show/hide generate actions for blocking mode
        if (generateActions) {
            generateActions.style.display = (selectedMode === 'blocking' && dropZone.classList.contains('has-file')) ? 'block' : 'none';
        }
    }

    // --- Colormap Selection ---
    const colormapOptions = document.querySelectorAll('.colormap-option');
    colormapOptions.forEach(option => {
        option.addEventListener('click', () => {
            colormapOptions.forEach(o => o.classList.remove('selected'));
            option.classList.add('selected');
            option.querySelector('input').checked = true;
            selectedColormap = option.dataset.value;
        });
    });

    // --- Safe Mode Selection ---
    const safeModeOptions = document.querySelectorAll('.safe-mode-option');
    safeModeOptions.forEach(option => {
        option.addEventListener('click', () => {
            safeModeOptions.forEach(o => o.classList.remove('selected'));
            option.classList.add('selected');
            option.querySelector('input').checked = true;
            selectedSafeMode = option.dataset.value;
        });
    });

    // --- Autocut Capture Selection ---
    const autocutCapture = document.getElementById('autocut-capture');
    if (autocutCapture) {
        autocutCapture.addEventListener('change', () => {
            selectedAutocutCapture = autocutCapture.value;
        });
    }

    // --- Drop Zone ---
    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
    dropZone.addEventListener('dragleave', () => { dropZone.classList.remove('dragover'); });
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener('change', (e) => { if (e.target.files.length) handleFile(e.target.files[0]); });

    function getModeLabel(mode) {
        if (mode === '3d_white') return '3D White Character';
        if (mode === 'playground') return '3D Playground Extraction';
        if (mode === 'autocut') return 'Autocut Midframe';
        if (mode === 'blocking') return 'Top-Down Blocking Animatic';
        if (mode === 'sceneflow') return 'SceneFlow Script-Video Sync';
        return 'Depth Map';
    }

    function handleFile(file) {
        const isImage = file.type.startsWith('image/');
        const isVideo = file.type.startsWith('video/');
        if (!isImage && !isVideo) { alert('Please select a valid video or image file.'); return; }

        window.selectedVideoFile = file;

        if (selectedMode === 'blocking') {
            // For blocking mode, just mark file as loaded and show generate button
            dropZone.classList.add('has-file');
            if (dropZoneTitle) dropZoneTitle.innerText = '✅ ' + file.name;
            if (dropZoneSubtitle) dropZoneSubtitle.innerHTML = '<span class="browse-btn">Change file</span>';
            if (generateActions) generateActions.style.display = 'block';
            return;
        }

        if (selectedMode === 'prompt_ai') {
            dropZone.classList.add('has-file');
            if (dropZoneTitle) dropZoneTitle.innerText = '✅ ' + file.name;
            if (dropZoneSubtitle) dropZoneSubtitle.innerHTML = '<span class="browse-btn">Change file</span>';
            if (generateActions) generateActions.style.display = 'block';
            return;
        }

        // For all other modes, start upload immediately
        const fileURL = URL.createObjectURL(file);
        if (isVideo) {
            originalVideo.src = fileURL;
        }
        uploadSection.classList.add('hidden');
        processingSection.classList.remove('hidden');

        const modeLabel = getModeLabel(selectedMode);
        statusText.innerText = `Uploading Video...`;
        progressDetail.innerText = `Preparing AI model for ${modeLabel}...`;

        const loader = document.querySelector('.processing-section .loader');
        const scanningHud = document.getElementById('scanning-hud');
        if (loader) loader.classList.remove('hidden');
        if (scanningHud) scanningHud.classList.add('hidden');

        uploadVideo(file);
    }

    // --- Start Generate Button (for blocking / prompt_ai) ---
    if (startGenerateBtn) {
        startGenerateBtn.addEventListener('click', () => {
            const file = window.selectedVideoFile;
            if (!file) { alert('Please select a file first.'); return; }

            if (selectedMode === 'prompt_ai') {
                handlePromptAI(file);
                return;
            }

            // For blocking, we use the blocking.js render flow
            // The blocking-render-btn handles that
            // For regular modes with generate button:
            uploadSection.classList.add('hidden');
            processingSection.classList.remove('hidden');
            const modeLabel = getModeLabel(selectedMode);
            statusText.innerText = `Uploading...`;
            progressDetail.innerText = `Preparing AI model for ${modeLabel}...`;
            uploadVideo(file);
        });
    }

    async function handlePromptAI(file) {
        const rawPrompt = document.getElementById('raw-prompt').value.trim();
        const apiKey = document.getElementById('gemini-api-key').value.trim();
        const locationSheetInput = document.getElementById('location-sheet');

        if (!rawPrompt) { alert('Please enter a raw prompt.'); return; }
        if (!apiKey) { alert('Please enter a Gemini API key.'); return; }
        if (!locationSheetInput || !locationSheetInput.files.length) {
            alert('Please upload a Location Sheet image.');
            return;
        }

        uploadSection.classList.add('hidden');
        processingSection.classList.remove('hidden');
        statusText.innerText = 'Analyzing with Gemini AI...';
        progressDetail.innerText = 'Sending video, location sheet and prompt to Gemini...';

        const formData = new FormData();
        formData.append('video', file);
        formData.append('location_sheet', locationSheetInput.files[0]);
        formData.append('raw_prompt', rawPrompt);
        formData.append('api_key', apiKey);

        try {
            const response = await fetch(`${API_URL}/analyze_prompt`, { method: 'POST', body: formData });
            const data = await response.json();

            if (response.ok && data.status === 'success') {
                processingSection.classList.add('hidden');
                resultsSection.classList.remove('hidden');
                if (videoCompareSection) videoCompareSection.classList.add('hidden');

                const promptResult = document.getElementById('prompt-result-container');
                const adjustedPrompt = document.getElementById('adjusted-prompt-result');
                if (promptResult) promptResult.classList.remove('hidden');
                if (adjustedPrompt) adjustedPrompt.value = data.adjusted_prompt;

                // Copy button
                const copyBtn = document.getElementById('copy-prompt-btn');
                if (copyBtn) {
                    copyBtn.addEventListener('click', () => {
                        adjustedPrompt.select();
                        document.execCommand('copy');
                        copyBtn.innerText = '✅ Copied!';
                        setTimeout(() => { copyBtn.innerText = 'Copy to Clipboard'; }, 2000);
                    });
                }
            } else {
                throw new Error(data.message || 'Unknown error');
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Error analyzing prompt: ' + error.message);
            resetApp();
        }
    }

    async function uploadVideo(file) {
        const formData = new FormData();
        formData.append('mode', selectedMode);
        formData.append('colormap', selectedColormap);
        formData.append('safe_mode', selectedSafeMode);
        formData.append('autocut_capture', selectedAutocutCapture);
        formData.append('file', file);

        try {
            const response = await fetch(`${API_URL}/upload`, { method: 'POST', body: formData });
            if (!response.ok) throw new Error('Upload failed');
            const data = await response.json();
            currentVideoId = data.video_id;

            const modeLabel = getModeLabel(selectedMode);
            statusText.innerText = `Rendering ${modeLabel}...`;
            pollInterval = setInterval(checkStatus, 2000);
        } catch (error) {
            console.error('Error:', error);
            alert('Error uploading video.');
            resetApp();
        }
    }

    function formatTime(seconds) {
        if (seconds == null || isNaN(seconds)) return '0:00';
        const totalSeconds = Math.round(seconds);
        const mins = Math.floor(totalSeconds / 60);
        const secs = totalSeconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    async function checkStatus() {
        if (!currentVideoId) return;
        try {
            const response = await fetch(`${API_URL}/status/${currentVideoId}`);
            const data = await response.json();
            const status = data.status;

            if (status === 'completed') {
                clearInterval(pollInterval);
                showResults(data);
            } else if (status === 'error') {
                clearInterval(pollInterval);
                alert('An error occurred while processing the video.');
                resetApp();
            } else if (status === 'processing') {
                const current = data.progress;
                const total = data.total;
                const elapsed = data.elapsed;
                const eta = data.eta;
                if (total > 0) {
                    const percent = Math.round((current / total) * 100);
                    const modeLabel = getModeLabel(selectedMode);
                    statusText.innerText = `Rendering ${modeLabel}... ${percent}%`;
                    progressDetail.innerText = `Frame ${current}/${total} \u2022 Elapsed: ${formatTime(elapsed)} \u2022 ETA: ${formatTime(eta)}`;
                }
            }
        } catch (error) {
            console.error('Status check error:', error);
        }
    }

    function showResults(statusData) {
        if (selectedMode === 'playground') {
            window.location.href = `playground.html?id=${currentVideoId}`;
            return;
        }

        processingSection.classList.add('hidden');
        resultsSection.classList.remove('hidden');
        resultTitle.innerText = getModeLabel(selectedMode);

        // --- Autocut mode ---
        if (selectedMode === 'autocut') {
            if (videoCompareSection) videoCompareSection.classList.add('hidden');
            if (downloadBtn) downloadBtn.classList.add('hidden');

            if (statusData && statusData.frames && statusData.frames.length > 0) {
                const autocutGallery = document.getElementById('autocut-gallery');
                const autocutSelectionContainer = document.getElementById('autocut-selection-container');
                if (autocutSelectionContainer) autocutSelectionContainer.classList.remove('hidden');
                if (autocutGallery) {
                    autocutGallery.innerHTML = '';
                    statusData.frames.forEach((frameUrl, i) => {
                        const shotNumStr = String(i + 1).padStart(3, '0');
                        const div = document.createElement('div');
                        div.className = 'autocut-frame-item';
                        div.innerHTML = `
                            <label style="cursor: pointer; display: block; position: relative;">
                                <input type="checkbox" value="${frameUrl}" checked style="position: absolute; top: 5px; left: 5px; z-index: 1;">
                                <img src="${API_URL}${frameUrl}" style="width: 100%; border-radius: 8px; border: 2px solid rgba(255,255,255,0.1);">
                                <p style="text-align: center; font-size: 0.85rem; font-weight: 600; margin-top: 0.3rem;">Shot ${shotNumStr}</p>
                            </label>
                        `;
                        autocutGallery.appendChild(div);
                    });
                }
            }
            return;
        }

        // --- Non-autocut modes ---
        if (videoCompareSection) videoCompareSection.classList.remove('hidden');

        if (selectedMode === 'blocking') {
            if (downloadJsonBtn) downloadJsonBtn.classList.remove('hidden');
            originalVideo.parentElement.classList.add('hidden');
            resultTitle.innerText = "Blocking Video (Timeline)";
            if (videoCompareSection) videoCompareSection.classList.add('single-video');
        } else if (selectedSafeMode === 'side_by_side') {
            if (downloadJsonBtn) downloadJsonBtn.classList.add('hidden');
            originalVideo.parentElement.classList.add('hidden');
            resultTitle.innerText = getModeLabel(selectedMode) + " (Side-by-Side)";
            if (videoCompareSection) videoCompareSection.classList.add('single-video');
        } else {
            if (downloadJsonBtn) downloadJsonBtn.classList.add('hidden');
            originalVideo.parentElement.classList.remove('hidden');
            resultTitle.innerText = getModeLabel(selectedMode);
            if (videoCompareSection) videoCompareSection.classList.remove('single-video');
        }

        // Use static files for reliable playback (with cache-bust)
        const depthVideoUrl = `${API_URL}/outputs/${currentVideoId}.mp4?t=${Date.now()}`;

        // Clean up previous video sync listeners
        if (videoSyncCleanup) {
            videoSyncCleanup();
            videoSyncCleanup = null;
        }

        // Remove any previous error overlay
        const existingOverlay = depthVideo.parentElement.querySelector('.video-error-overlay');
        if (existingOverlay) existingOverlay.remove();
        depthVideo.style.display = '';

        // Revoke any previous blob URL
        if (depthVideo._blobUrl) {
            URL.revokeObjectURL(depthVideo._blobUrl);
            depthVideo._blobUrl = null;
        }

        // Try loading the video with blob URL fallback
        let loadAttempt = 0;
        const tryLoadVideo = async (url) => {
            loadAttempt++;
            depthVideo.onerror = async () => {
                console.error(`Depth video load attempt ${loadAttempt} failed:`, depthVideo.error);
                if (loadAttempt === 1) {
                    // Fallback: fetch as blob and use object URL
                    try {
                        console.log('Trying blob URL fallback...');
                        const resp = await fetch(url);
                        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                        const blob = await resp.blob();
                        const blobUrl = URL.createObjectURL(blob);
                        depthVideo._blobUrl = blobUrl;
                        tryLoadVideo(blobUrl);
                    } catch (e) {
                        console.error('Blob fallback also failed:', e);
                        showVideoError();
                    }
                } else {
                    showVideoError();
                }
            };
            depthVideo.src = url;
        };

        const showVideoError = () => {
            // Show error overlay WITHOUT destroying the video element
            let overlay = depthVideo.parentElement.querySelector('.video-error-overlay');
            if (!overlay) {
                overlay = document.createElement('div');
                overlay.className = 'video-error-overlay';
                overlay.innerHTML = '<p>⚠️ Video preview unavailable.<br>Use the Download button instead.</p>';
                depthVideo.parentElement.appendChild(overlay);
            }
            depthVideo.style.display = 'none';
        };

        tryLoadVideo(depthVideoUrl);

        // Set up video sync listeners (with cleanup tracking)
        if (selectedMode !== 'blocking') {
            const onPlay = () => depthVideo.play().catch(()=>{});
            const onPause = () => depthVideo.pause();
            const onSeeked = () => { depthVideo.currentTime = originalVideo.currentTime; };
            originalVideo.addEventListener('play', onPlay);
            originalVideo.addEventListener('pause', onPause);
            originalVideo.addEventListener('seeked', onSeeked);
            videoSyncCleanup = () => {
                originalVideo.removeEventListener('play', onPlay);
                originalVideo.removeEventListener('pause', onPause);
                originalVideo.removeEventListener('seeked', onSeeked);
            };
            depthVideo.addEventListener('loadeddata', () => {
                originalVideo.play().catch(()=>{});
            }, { once: true });
            originalVideo.play().catch(()=>{});
        } else {
            depthVideo.addEventListener('loadeddata', () => {
                depthVideo.play().catch(()=>{});
            }, { once: true });
        }
    }

    // --- Download Button ---
    downloadBtn.addEventListener('click', async () => {
        if (!currentVideoId) return;

        let fileUrl = `${API_URL}/download/${currentVideoId}`;
        let fileName = `${selectedMode}_${currentVideoId}.mp4`;

        if (selectedMode === 'autocut') {
            const autocutResult = document.getElementById('autocut-result');
            const imgs = autocutResult ? autocutResult.querySelectorAll('img') : [];
            if (imgs.length > 0) {
                // Download grid images
                for (const img of imgs) {
                    try {
                        const res = await fetch(img.src);
                        const blob = await res.blob();
                        const blobUrl = URL.createObjectURL(blob);
                        const cleanFileName = img.src.split('/').pop().split('?')[0];
                        
                        const link = document.createElement('a');
                        link.href = blobUrl;
                        link.download = cleanFileName;
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                        URL.revokeObjectURL(blobUrl);
                    } catch (err) {
                        console.error('Download error:', err);
                        window.open(img.src, '_blank');
                    }
                }
                return;
            }
        }

        // Fallback for videos: use window.location.href since the server sends Content-Disposition: attachment
        window.location.href = fileUrl;
    });

    // --- Download JSON Log Button ---
    if (downloadJsonBtn) {
        downloadJsonBtn.addEventListener('click', async () => {
            if (!currentVideoId) return;
            window.location.href = `${API_URL}/download_log/${currentVideoId}`;
        });
    }

    // --- Reset Button ---
    resetBtn.addEventListener('click', resetApp);

    function resetApp() {
        clearInterval(pollInterval);
        currentVideoId = null;
        fileInput.value = '';
        originalVideo.src = '';
        depthVideo.src = '';
        depthVideo.onerror = null;
        statusText.innerText = '';
        progressDetail.innerText = '';
        window.selectedVideoFile = null;

        // Clean up video sync listeners
        if (videoSyncCleanup) {
            videoSyncCleanup();
            videoSyncCleanup = null;
        }

        // Revoke any blob URL
        if (depthVideo._blobUrl) {
            URL.revokeObjectURL(depthVideo._blobUrl);
            depthVideo._blobUrl = null;
        }

        // Restore video element if error overlay was shown
        const errorOverlay = depthVideo.parentElement.querySelector('.video-error-overlay');
        if (errorOverlay) errorOverlay.remove();
        depthVideo.style.display = '';

        // Reset safe mode
        safeModeOptions.forEach(o => o.classList.remove('selected'));
        const noneOption = document.querySelector('.safe-mode-option[data-value="none"]');
        if (noneOption) noneOption.classList.add('selected');
        selectedSafeMode = 'none';

        // Reset drop zone
        if (dropZoneTitle) dropZoneTitle.innerText = "Drag & Drop your video";
        if (dropZoneSubtitle) dropZoneSubtitle.innerHTML = 'or <span class="browse-btn">browse files</span><br>Supports MP4, AVI, MOV (Max 50MB recommended)';
        dropZone.classList.remove('has-file');
        if (generateActions) generateActions.style.display = 'none';

        // Hide containers
        const autocutContainer = document.getElementById('autocut-container');
        const autocutSelectionContainer = document.getElementById('autocut-selection-container');
        const panoramaContainer = document.getElementById('panorama-container');
        if (autocutContainer) autocutContainer.classList.add('hidden');
        if (autocutSelectionContainer) autocutSelectionContainer.classList.add('hidden');
        if (panoramaContainer) panoramaContainer.classList.add('hidden');
        if (sceneflowStudioContainer) sceneflowStudioContainer.classList.add('hidden');
        if (videoCompareSection) videoCompareSection.classList.remove('hidden');
        if (videoCompareSection) videoCompareSection.classList.remove('single-video');
        if (downloadBtn) {
            downloadBtn.classList.remove('hidden');
            downloadBtn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg> Download Processed Video`;
        }
        if (downloadJsonBtn) downloadJsonBtn.classList.add('hidden');

        resultsSection.classList.add('hidden');
        processingSection.classList.add('hidden');
        uploadSection.classList.remove('hidden');

        updateModeVisibility();
    }

    // --- Generate Grid Button (Autocut) ---
    const generateGridBtn = document.getElementById('generate-grid-btn');
    const autocutGallery = document.getElementById('autocut-gallery');
    if (generateGridBtn) {
        generateGridBtn.addEventListener('click', async () => {
            const checkboxes = autocutGallery.querySelectorAll('input[type="checkbox"]:checked');
            const selectedFrames = Array.from(checkboxes).map(cb => cb.value);

            if (selectedFrames.length === 0) {
                alert('Please select at least one frame.');
                return;
            }

            const layoutRadio = document.querySelector('input[name="grid_layout"]:checked');
            const layoutMode = layoutRadio ? layoutRadio.value : 'all';

            generateGridBtn.innerText = '⏳ Generating Grid...';
            generateGridBtn.disabled = true;

            try {
                const response = await fetch(`${API_URL}/generate_grid`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        video_id: currentVideoId,
                        frames: selectedFrames,
                        layout_mode: layoutMode,
                        autocut_capture: selectedAutocutCapture
                    })
                });
                const data = await response.json();
                if (response.ok && data.grid_urls) {
                    const autocutContainer = document.getElementById('autocut-container');
                    const autocutResult = document.getElementById('autocut-result');
                    const autocutSelectionContainer = document.getElementById('autocut-selection-container');
                    if (autocutResult) {
                        autocutResult.innerHTML = data.grid_urls.map(url =>
                            `<img src="${API_URL}${url}?t=${Date.now()}" style="width: 100%; border-radius: 8px; margin-bottom: 1rem;">`
                        ).join('');
                    }
                    if (autocutContainer) autocutContainer.classList.remove('hidden');
                    if (autocutSelectionContainer) autocutSelectionContainer.classList.add('hidden');

                    if (downloadBtn) {
                        downloadBtn.classList.remove('hidden');
                        downloadBtn.innerHTML = '⬇️ Download Grid Image';
                    }
                } else {
                    alert('Error generating grid: ' + (data.message || 'Unknown error'));
                }
            } catch (error) {
                console.error(error);
                alert('Error generating grid: ' + error.message);
            } finally {
                generateGridBtn.innerText = '📸 Generate Grid from Selected';
                generateGridBtn.disabled = false;
            }
        });
    }

    // --- Initialize visibility ---
    updateModeVisibility();
});
