import cv2
import numpy as np
import os
import time
import json
from scenedetect import detect, ContentDetector

def format_timecode(frame_num: int, fps: float) -> str:
    if fps <= 0:
        fps = 30.0
    total_seconds = frame_num / fps
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    millis = int(round((total_seconds - int(total_seconds)) * 1000))
    if millis >= 1000:
        millis = 999
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"

def draw_overlay_text(img: np.ndarray, shot_text: str, timecode_text: str):
    h, w = img.shape[:2]
    # Scale font proportionally to image width
    font_scale = max(0.6, (w / 800.0) * 0.85)
    thickness = max(1, int(round(font_scale * 2.2)))
    font = cv2.FONT_HERSHEY_DUPLEX
    
    # 1. Top-Left Shot Number (e.g. "001")
    shot_pad_x = int(w * 0.02)
    shot_pad_y = int(h * 0.08)
    
    # Draw dark stroke / drop shadow then crisp white text
    cv2.putText(img, shot_text, (shot_pad_x, shot_pad_y), font, font_scale, (0, 0, 0), thickness + 2, cv2.LINE_AA)
    cv2.putText(img, shot_text, (shot_pad_x, shot_pad_y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
    
    # 2. Bottom-Right Timecode (e.g. "00:00:01.167")
    tc_font_scale = font_scale * 0.85
    tc_thickness = max(1, int(round(tc_font_scale * 2.0)))
    tc_size = cv2.getTextSize(timecode_text, font, tc_font_scale, tc_thickness)[0]
    tc_pad_x = w - tc_size[0] - int(w * 0.02)
    tc_pad_y = h - int(h * 0.03)
    
    cv2.putText(img, timecode_text, (tc_pad_x, tc_pad_y), font, tc_font_scale, (0, 0, 0), tc_thickness + 2, cv2.LINE_AA)
    cv2.putText(img, timecode_text, (tc_pad_x, tc_pad_y), font, tc_font_scale, (255, 255, 255), tc_thickness, cv2.LINE_AA)

class AutocutProcessor:
    def __init__(self):
        pass

    def process_video(self, input_path: str, output_path: str, progress_callback=None, **kwargs):
        start_time = time.monotonic()
        
        # Step 1: Detect scenes
        if progress_callback:
            progress_callback(1, 100, elapsed_seconds=0, eta_seconds=10)
            
        scene_list = detect(input_path, ContentDetector())
        
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise ValueError(f"Error opening video file {input_path}")
            
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        if fps <= 0 or np.isnan(fps):
            fps = 30.0
        
        extracted_shots = []
        autocut_capture = kwargs.get('autocut_capture', 'mid_frame')
        
        if len(scene_list) > 0:
            for i, scene in enumerate(scene_list):
                start_frame_tc, end_frame_tc = scene
                start_f = start_frame_tc.get_frames()
                end_f = end_frame_tc.get_frames()
                
                if progress_callback:
                    progress_callback(20 + int(i / len(scene_list) * 50), 100, elapsed_seconds=time.monotonic() - start_time, eta_seconds=5)
                
                if autocut_capture == 'first_frame':
                    target_frame = start_f
                elif autocut_capture == 'end_frame':
                    target_frame = max(start_f, end_f - 1)
                else: # mid_frame (default)
                    target_frame = (start_f + end_f) // 2
                
                target_frame = max(0, min(total_frames - 1, target_frame))
                
                cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                ret, frame = cap.read()
                if ret:
                    timecode_str = format_timecode(target_frame, fps)
                    extracted_shots.append({
                        "shot_index": i + 1,
                        "frame_idx": target_frame,
                        "timecode": timecode_str,
                        "frame": frame
                    })
        else:
            # If no scene cuts found, determine target frame
            if autocut_capture == 'first_frame':
                target_frame = 0
            elif autocut_capture == 'end_frame':
                target_frame = max(0, total_frames - 2)
            else: # mid_frame
                target_frame = total_frames // 2
                
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            ret, frame = cap.read()
            if ret:
                timecode_str = format_timecode(target_frame, fps)
                extracted_shots.append({
                    "shot_index": 1,
                    "frame_idx": target_frame,
                    "timecode": timecode_str,
                    "frame": frame
                })
                
        cap.release()
        
        if not extracted_shots:
            raise ValueError("Could not extract any frames from the video.")
            
        if progress_callback:
            progress_callback(80, 100, elapsed_seconds=time.monotonic() - start_time, eta_seconds=2)
            
        # Step 2: Save individual frames with overlay
        dir_name = output_path.replace('.mp4', '_frames')
        os.makedirs(dir_name, exist_ok=True)
        
        saved_frames = []
        shot_metadata = []
        
        for item in extracted_shots:
            shot_idx = item["shot_index"]
            shot_text = f"{shot_idx:03d}"
            timecode_str = item["timecode"]
            raw_frame = item["frame"].copy()
            
            # Apply shot number (top-left) and timecode (bottom-right)
            draw_overlay_text(raw_frame, shot_text, timecode_str)
            
            frame_filename = f"shot_{shot_idx:03d}.jpg"
            frame_path = os.path.join(dir_name, frame_filename)
            cv2.imwrite(frame_path, raw_frame)
            saved_frames.append(frame_path)
            
            shot_metadata.append({
                "shot_index": shot_idx,
                "shot_label": shot_text,
                "timecode": timecode_str,
                "frame_path": frame_path
            })
            
        # Save metadata JSON
        meta_json_path = os.path.join(dir_name, "shots_metadata.json")
        with open(meta_json_path, "w") as f:
            json.dump(shot_metadata, f, indent=2)
            
        if progress_callback:
            progress_callback(100, 100, elapsed_seconds=time.monotonic() - start_time, eta_seconds=0)
            
        return saved_frames
