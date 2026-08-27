import os
import re
import cv2
import numpy as np
import av
import json
import time

CUE_COLORS = {
    "dialogue": {"color": "#eab308", "badge": "🟡 Dialogue", "bg": "rgba(234, 179, 8, 0.15)"},
    "action": {"color": "#3b82f6", "badge": "🔵 Action", "bg": "rgba(59, 130, 246, 0.15)"},
    "camera": {"color": "#22c55e", "badge": "🟢 Camera", "bg": "rgba(34, 197, 94, 0.15)"},
    "shot": {"color": "#a855f7", "badge": "🟣 Shot", "bg": "rgba(168, 85, 247, 0.15)"},
    "audio": {"color": "#f97316", "badge": "🟠 Audio", "bg": "rgba(249, 115, 22, 0.15)"},
    "vfx": {"color": "#06b6d4", "badge": "🔷 VFX", "bg": "rgba(6, 182, 212, 0.15)"},
    "transition": {"color": "#ec4899", "badge": "🩷 Transition", "bg": "rgba(236, 72, 153, 0.15)"},
    "environment": {"color": "#94a3b8", "badge": "⚪ Environment", "bg": "rgba(148, 163, 184, 0.15)"}
}

def format_timecode(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        millis = 999
    return f"{hrs:02d}:{mins:02d}:{secs:02d}.{millis:03d}"

class SceneFlowAligner:
    def __init__(self):
        pass

    def extract_audio_energy(self, video_path: str, fps_sample=20):
        """
        Extracts RMS audio energy envelope across time windows (e.g. 50ms) using PyAV.
        Returns array of (timestamp_sec, rms_energy, is_active).
        """
        speech_intervals = []
        duration = 0.0

        try:
            container = av.open(video_path)
            # Get video duration
            if container.duration:
                duration = float(container.duration / av.time_base)

            audio_streams = [s for s in container.streams if s.type == 'audio']
            if not audio_streams:
                container.close()
                return duration, []

            stream = audio_streams[0]
            sample_rate = stream.sample_rate or 44100
            
            all_samples = []
            for frame in container.decode(stream):
                # Convert frame to mono float numpy array
                arr = frame.to_ndarray()
                if arr.ndim > 1:
                    arr = np.mean(arr, axis=0) # convert stereo/multi-channel to mono
                all_samples.append(arr.astype(np.float32))

            container.close()

            if not all_samples:
                return duration, []

            full_audio = np.concatenate(all_samples)
            total_samples = len(full_audio)
            actual_duration = total_samples / sample_rate
            if duration <= 0:
                duration = actual_duration

            # Calculate RMS energy per window (e.g., 50ms window = 0.05s)
            window_size = int(sample_rate / fps_sample)
            num_windows = total_samples // window_size

            energies = []
            for w_idx in range(num_windows):
                chunk = full_audio[w_idx * window_size : (w_idx + 1) * window_size]
                rms = float(np.sqrt(np.mean(chunk**2))) if len(chunk) > 0 else 0.0
                energies.append(rms)

            if not energies:
                return duration, []

            # Determine adaptive activity threshold
            med_energy = float(np.median(energies))
            max_energy = float(np.max(energies))
            threshold = med_energy + 0.15 * (max_energy - med_energy + 1e-6)

            # Detect continuous active audio intervals (speech bursts)
            min_speech_len = int(fps_sample * 0.3) # minimum 300ms
            min_pause_len = int(fps_sample * 0.25) # 250ms pause splits speech

            is_speaking = False
            start_w = 0
            pause_count = 0

            for i, e in enumerate(energies):
                if e > threshold:
                    if not is_speaking:
                        is_speaking = True
                        start_w = max(0, i - 1)
                    pause_count = 0
                else:
                    if is_speaking:
                        pause_count += 1
                        if pause_count >= min_pause_len:
                            end_w = i - pause_count
                            if end_w - start_w >= min_speech_len:
                                start_sec = start_w / fps_sample
                                end_sec = end_w / fps_sample
                                speech_intervals.append({"start": start_sec, "end": end_sec})
                            is_speaking = False
                            pause_count = 0

            if is_speaking:
                start_sec = start_w / fps_sample
                end_sec = len(energies) / fps_sample
                if end_sec - start_sec >= 0.2:
                    speech_intervals.append({"start": start_sec, "end": end_sec})

        except Exception as err:
            print(f"Audio extraction notice: {err}")

        # Fallback video duration check with OpenCV if needed
        if duration <= 0:
            try:
                cap = cv2.VideoCapture(video_path)
                if cap.isOpened():
                    f_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                    duration = f_count / fps
                    cap.release()
            except Exception:
                duration = 10.0

        return duration, speech_intervals

    def parse_script_lines(self, script_text: str):
        """
        Parses screenplay/script plain text into raw cue units with preliminary classification.
        """
        lines = [l.strip() for l in script_text.strip().split('\n') if l.strip()]
        if not lines:
            return []

        cues = []
        current_speaker = None

        for line in lines:
            # 1. Environment / Scene Slugline
            if re.match(r'^(INT\.|EXT\.|INT/EXT\.|EST\.|SCENE\s+\d+)', line, re.IGNORECASE):
                cues.append({
                    "type": "environment",
                    "speaker": None,
                    "text": line,
                    "estimated_weight": 1.2
                })
                current_speaker = None
                continue

            # 2. Camera Direction
            if re.match(r'^(CAMERA|CAM|ANGLE|PAN|TILT|DOLLY|ZOOM|TRACKING|CRANE|POV|OVER THE SHOULDER|OTS|DUTCH ANGLE|ESTABLISHING SHOT)', line, re.IGNORECASE) or re.search(r'\[(CAMERA|CAM|ANGLE):.*?\]', line, re.IGNORECASE):
                clean_text = re.sub(r'^CAMERA:\s*', '', line, flags=re.IGNORECASE).strip()
                cues.append({
                    "type": "camera",
                    "speaker": None,
                    "text": clean_text,
                    "estimated_weight": 1.0
                })
                continue

            # 3. Transition
            if re.match(r'^(CUT TO\b|FADE IN\b|FADE OUT\b|DISSOLVE TO\b|MATCH CUT\b|SMASH CUT\b|JUMP CUT\b|TRANSITION\b)', line, re.IGNORECASE) or re.search(r'\[(TRANSITION|CUT TO):.*?\]', line, re.IGNORECASE):
                cues.append({
                    "type": "transition",
                    "speaker": None,
                    "text": line,
                    "estimated_weight": 0.6
                })
                current_speaker = None
                continue

            # 4. Shot Framing
            if re.match(r'^(SHOT\b|WIDE SHOT\b|CLOSE UP\b|MEDIUM SHOT\b|EXTREME CLOSE UP\b|\bCU\b|\bMCU\b|\bWS\b|\bECU\b|\bLONG SHOT\b|\bFULL SHOT\b)', line, re.IGNORECASE) or re.search(r'\[SHOT:.*?\]', line, re.IGNORECASE):
                cues.append({
                    "type": "shot",
                    "speaker": None,
                    "text": line,
                    "estimated_weight": 1.0
                })
                current_speaker = None
                continue

            # 5. Sound / Audio Cue
            if re.match(r'^(SFX|AUDIO|SOUND|MUSIC|TRACK|SCORE):', line, re.IGNORECASE) or re.search(r'\[(SFX|SOUND|AUDIO):.*?\]', line, re.IGNORECASE):
                clean_text = re.sub(r'^(SFX|AUDIO|SOUND|MUSIC|TRACK|SCORE):\s*', '', line, flags=re.IGNORECASE).strip()
                cues.append({
                    "type": "audio",
                    "speaker": None,
                    "text": clean_text,
                    "estimated_weight": 0.8
                })
                current_speaker = None
                continue

            # 6. VFX Cue
            if re.match(r'^(VFX|CGI|EFFECT|FX):', line, re.IGNORECASE) or re.search(r'\[(VFX|CGI|EFFECT):.*?\]', line, re.IGNORECASE):
                clean_text = re.sub(r'^(VFX|CGI|EFFECT|FX):\s*', '', line, flags=re.IGNORECASE).strip()
                cues.append({
                    "type": "vfx",
                    "speaker": None,
                    "text": clean_text,
                    "estimated_weight": 1.0
                })
                current_speaker = None
                continue

            # 7. Dialogue format: "CHARACTER: text" or "CHARACTER (parenthetical): text"
            diag_match = re.match(r'^([A-Z0-9_\s\.\'\-]+?)(\s*\([^\)]+\))?\s*:\s*(.+)$', line)
            if diag_match:
                speaker_name = diag_match.group(1).strip()
                spoken_text = diag_match.group(3).strip()
                cues.append({
                    "type": "dialogue",
                    "speaker": speaker_name,
                    "text": spoken_text,
                    "estimated_weight": max(1.0, len(spoken_text.split()) * 0.35)
                })
                current_speaker = None
                continue

            # 8. All-caps Character heading on its own line followed by dialogue
            if line.isupper() and len(line) < 30 and not line.endswith('.'):
                current_speaker = line.strip()
                continue

            if current_speaker:
                # Spoken line under character heading
                cues.append({
                    "type": "dialogue",
                    "speaker": current_speaker,
                    "text": line,
                    "estimated_weight": max(1.0, len(line.split()) * 0.35)
                })
                current_speaker = None
                continue

            # 9. Default: Action Description
            cues.append({
                "type": "action",
                "speaker": None,
                "text": line,
                "estimated_weight": max(1.0, len(line.split()) * 0.25)
            })

        return cues

    def align(self, video_path: str, script_text: str):
        """
        Executes automatic audio speech extraction and script-to-video forced alignment.
        Returns complete SceneFlow project data structure with 8 color-coded cue elements.
        """
        # 1. Extract audio energy and video duration
        video_duration, speech_intervals = self.extract_audio_energy(video_path)
        if video_duration <= 0:
            video_duration = 10.0

        # 2. Parse script into cue elements
        parsed_cues = self.parse_script_lines(script_text)
        if not parsed_cues:
            # Fallback single cue if empty
            parsed_cues = [{
                "type": "action",
                "speaker": None,
                "text": script_text or "Scene progression",
                "estimated_weight": 1.0
            }]

        total_weight = sum(c["estimated_weight"] for c in parsed_cues)
        num_cues = len(parsed_cues)
        dialogue_cues = [c for c in parsed_cues if c["type"] == "dialogue"]

        # Strategy A: Speech-Intervals alignment (if audio voice intervals detected)
        aligned_cues = []
        if speech_intervals and len(speech_intervals) >= len(dialogue_cues) and len(dialogue_cues) > 0:
            speech_idx = 0
            cur_time = 0.0

            for i, cue in enumerate(parsed_cues):
                if cue["type"] == "dialogue" and speech_idx < len(speech_intervals):
                    s_int = speech_intervals[speech_idx]
                    start_s = max(cur_time, s_int["start"])
                    end_s = max(start_s + 0.5, min(video_duration, s_int["end"]))
                    speech_idx += 1
                else:
                    # Non-dialogue cue: place in remaining timeline proportionally
                    weight_fraction = cue["estimated_weight"] / max(0.1, total_weight)
                    dur = max(0.5, weight_fraction * video_duration)
                    start_s = cur_time
                    end_s = min(video_duration, cur_time + dur)

                cur_time = min(video_duration, end_s)
                aligned_cues.append({
                    "cue_id": f"cue_{i+1:03d}",
                    "type": cue["type"],
                    "speaker": cue["speaker"],
                    "text": cue["text"],
                    "start_sec": round(start_s, 3),
                    "end_sec": round(end_s, 3),
                    "timecode_start": format_timecode(start_s),
                    "timecode_end": format_timecode(end_s),
                    "color_info": CUE_COLORS.get(cue["type"], CUE_COLORS["action"])
                })

        else:
            # Strategy B: Proportional Pacing Alignment across video duration
            cur_time = 0.0
            for i, cue in enumerate(parsed_cues):
                weight_fraction = cue["estimated_weight"] / max(0.1, total_weight)
                cue_dur = weight_fraction * video_duration
                # Ensure minimum visible duration of 0.4s
                cue_dur = max(0.4, cue_dur)
                
                start_s = cur_time
                end_s = min(video_duration, start_s + cue_dur)
                cur_time = end_s

                aligned_cues.append({
                    "cue_id": f"cue_{i+1:03d}",
                    "type": cue["type"],
                    "speaker": cue["speaker"],
                    "text": cue["text"],
                    "start_sec": round(start_s, 3),
                    "end_sec": round(end_s, 3),
                    "timecode_start": format_timecode(start_s),
                    "timecode_end": format_timecode(end_s),
                    "color_info": CUE_COLORS.get(cue["type"], CUE_COLORS["action"])
                })

        # Ensure last cue reaches end of video
        if aligned_cues:
            aligned_cues[-1]["end_sec"] = round(video_duration, 3)
            aligned_cues[-1]["timecode_end"] = format_timecode(video_duration)

        # Summary statistics
        cue_counts = {}
        for c in aligned_cues:
            t = c["type"]
            cue_counts[t] = cue_counts.get(t, 0) + 1

        result = {
            "status": "success",
            "video_duration_sec": round(video_duration, 3),
            "video_duration_timecode": format_timecode(video_duration),
            "total_cues": len(aligned_cues),
            "cue_counts": cue_counts,
            "cues": aligned_cues,
            "has_audio_sync": len(speech_intervals) > 0,
            "speech_intervals_detected": len(speech_intervals)
        }

        return result
