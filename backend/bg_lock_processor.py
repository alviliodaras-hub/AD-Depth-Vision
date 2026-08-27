import cv2
import torch
import numpy as np
from PIL import Image
from transformers import pipeline
from faststart import faststart_mp4
import os
import time

class BackgroundLockProcessor:
    def __init__(self, model_name="depth-anything/Depth-Anything-V2-Small-hf"):
        self.device = 0 if torch.cuda.is_available() else (-1 if not torch.backends.mps.is_available() else 'mps')
        print(f"Loading Depth Anything V2 model ({model_name}) on device {self.device}...")
        self.pipe = pipeline(
            task="depth-estimation",
            model=model_name,
            device=self.device
        )
        print("Depth Anything V2 loaded successfully.")

    @torch.inference_mode()
    def process_video(self, input_path: str, output_path: str, progress_callback=None, 
                      depth_threshold: float = 0.4, motion_threshold: float = 2.0, location_sheet_path: str = None):
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise ValueError(f"Error opening video file {input_path}")

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Output resolution capped at 720p
        max_dim = 720
        scale = 1.0
        if max(width, height) > max_dim:
            scale = max_dim / max(width, height)
            out_width = int(width * scale)
            out_height = int(height * scale)
        else:
            out_width = width
            out_height = height

        out_width = out_width - (out_width % 16)
        out_height = out_height - (out_height % 16)

        model_dim = 518
        model_scale = model_dim / max(width, height)
        model_width = int(width * model_scale)
        model_height = int(height * model_scale)
        model_width = model_width - (model_width % 14)
        model_height = model_height - (model_height % 14)
        if model_width < 14: model_width = 14
        if model_height < 14: model_height = 14

        # Use VP9 codec for WebM to ensure browser playback without faststart/moov issues
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        out = cv2.VideoWriter(output_path, fourcc, fps, (out_width, out_height), isColor=True)
        if not out.isOpened():
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (out_width, out_height), isColor=True)

        # Phase 2 (Memory): Use location sheet if provided
        base_bg = None
        if location_sheet_path and os.path.exists(location_sheet_path):
            img = cv2.imread(location_sheet_path)
            if img is not None:
                base_bg = cv2.resize(img, (out_width, out_height))
        
        batch_size = 4
        frame_count = 0
        start_time = time.monotonic()
        
        prev_gray = None

        with torch.no_grad():
            while cap.isOpened():
                batch_frames = []
                batch_pil = []
                for _ in range(batch_size):
                    ret, frame = cap.read()
                    if not ret:
                        break
                    frame_out_sized = cv2.resize(frame, (out_width, out_height))
                    batch_frames.append(frame_out_sized)
                    
                    frame_resized = cv2.resize(frame, (model_width, model_height))
                    image_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(image_rgb)
                    batch_pil.append(pil_image)

                if not batch_frames:
                    break

                if base_bg is None:
                    # Memory: first frame fallback
                    base_bg = batch_frames[0].copy()

                results = self.pipe(batch_pil, batch_size=batch_size)

                for idx, result in enumerate(results):
                    curr_frame = batch_frames[idx]
                    curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)
                    
                    if prev_gray is None:
                        prev_gray = curr_gray
                        
                    # Phase 1: Depth map
                    depth_map = result["depth"]
                    depth_array = np.array(depth_map, dtype=np.float32)
                    d_min, d_max = float(depth_array.min()), float(depth_array.max())
                    if d_max - d_min > 0:
                        depth_norm = (depth_array - d_min) / (d_max - d_min)
                    else:
                        depth_norm = np.zeros_like(depth_array)
                    
                    depth_norm = cv2.resize(depth_norm, (out_width, out_height), interpolation=cv2.INTER_LINEAR)
                    
                    # Phase 1: Dense Optical Flow
                    flow = cv2.calcOpticalFlowFarneback(prev_gray, curr_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
                    mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                    
                    # Masking: Foreground Mask = (Depth < depth_threshold) AND (Motion Magnitude > motion_threshold)
                    mask = ((depth_norm < depth_threshold) & (mag > motion_threshold)).astype(np.uint8) * 255
                    
                    # Clean mask with morphology and Gaussian Blur
                    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
                    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
                    mask = cv2.GaussianBlur(mask, (5, 5), 0)
                    
                    # Phase 3: Composite
                    mask_float = mask.astype(np.float32) / 255.0
                    alpha = mask_float[..., np.newaxis]
                    
                    composite = (curr_frame * alpha + base_bg * (1.0 - alpha)).astype(np.uint8)
                    
                    out.write(composite)
                    
                    prev_gray = curr_gray
                    frame_count += 1
                
                elapsed = time.monotonic() - start_time
                if frame_count > 0:
                    eta = elapsed * (total_frames - frame_count) / frame_count
                else:
                    eta = 0.0

                if progress_callback:
                    progress_callback(frame_count, total_frames, elapsed_seconds=elapsed, eta_seconds=eta)

        if progress_callback:
            elapsed = time.monotonic() - start_time
            progress_callback(total_frames, total_frames, elapsed_seconds=elapsed, eta_seconds=0.0)

        cap.release()
        out.release()

        # Move moov atom to beginning for browser streaming
        faststart_mp4(output_path)
        
        panorama_path = output_path.replace('.mp4', '_panorama.jpg')
        if base_bg is not None:
            cv2.imwrite(panorama_path, base_bg)
        
        if self.device == 'mps':
            torch.mps.empty_cache()
            
        return output_path, panorama_path
