document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const uploadSection = document.getElementById('upload-section');
    const processingSection = document.getElementById('processing-section');
    const resultsSection = document.getElementById('results-section');
    const colormapSection = document.getElementById('colormap-section');
    const resultTitle = document.getElementById('result-title');
    
    const originalVideo = document.getElementById('original-video');
    const depthVideo = document.getElementById('depth-video');
    const downloadBtn = document.getElementById('download-btn');
    const resetBtn = document.getElementById('reset-btn');
    const statusText = document.getElementById('status-text');
    const progressDetail = document.getElementById('progress-detail');

    const API_URL = window.location.origin;
    let currentVideoId = null;
    let pollInterval = null;
    let selectedMode = 'depth';
    let selectedColormap = 'grayscale';

    // --- Mode Selection ---
    const modeCards = document.querySelectorAll('.mode-card');
    modeCards.forEach(card => {
        card.addEventListener('click', () => {
            modeCards.forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');
            card.querySelector('input').checked = true;
            selectedMode = card.dataset.mode;

            // Show colormap section only for depth map mode
            if (selectedMode === 'depth') {
                colormapSection.classList.remove('hidden');
            } else {
                colormapSection.classList.add('hidden');
            }
        });
    });

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
        if (mode === 'pose') return 'Character Motion Pivot';
        if (mode === '3d_white') return '3D White Character';
        if (mode === 'playground') return '3D Playground Extraction';
        return 'Depth Map';
    }

    function handleFile(file) {
        if (!file.type.startsWith('video/')) { alert('Please select a valid video file.'); return; }
        const fileURL = URL.createObjectURL(file);
        originalVideo.src = fileURL;
        uploadSection.classList.add('hidden');
        processingSection.classList.remove('hidden');

        const modeLabel = getModeLabel(selectedMode);
        statusText.innerText = `Uploading Video...`;
        progressDetail.innerText = `Preparing AI model for ${modeLabel}...`;
        uploadVideo(file);
    }

    async function uploadVideo(file) {
        const formData = new FormData();
        formData.append('mode', selectedMode);
        formData.append('colormap', selectedColormap);
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
                showResults();
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

    function showResults() {
        if (selectedMode === 'playground') {
            window.location.href = `playground.html?id=${currentVideoId}`;
            return;
        }

        processingSection.classList.add('hidden');
        resultsSection.classList.remove('hidden');

        resultTitle.innerText = getModeLabel(selectedMode);

        const depthVideoUrl = `${API_URL}/download/${currentVideoId}`;
        depthVideo.src = depthVideoUrl;
        originalVideo.addEventListener('play', () => depthVideo.play());
        originalVideo.addEventListener('pause', () => depthVideo.pause());
        originalVideo.addEventListener('seeked', () => depthVideo.currentTime = originalVideo.currentTime);
        originalVideo.play();
    }

    downloadBtn.addEventListener('click', () => {
        if (!currentVideoId) return;
        const link = document.createElement('a');
        link.href = `${API_URL}/download/${currentVideoId}`;
        link.download = `${selectedMode}_${currentVideoId}.mp4`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    });

    resetBtn.addEventListener('click', resetApp);

    function resetApp() {
        clearInterval(pollInterval);
        currentVideoId = null;
        fileInput.value = '';
        originalVideo.src = '';
        depthVideo.src = '';
        statusText.innerText = '';
        progressDetail.innerText = '';
        resultsSection.classList.add('hidden');
        processingSection.classList.add('hidden');
        uploadSection.classList.remove('hidden');
    }
});
