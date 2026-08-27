import cv2
import torch
import numpy as np
from PIL import Image
from transformers import pipeline
import os
import time
from faststart import faststart_mp4

COLORMAP_OPTIONS = {
    "grayscale": None,
    "turbo": cv2.COLORMAP_TURBO,
    "magma": cv2.COLORMAP_MAGMA,
    "inferno": cv2.COLORMAP_INFERNO,
    "plasma": cv2.COLORMAP_PLASMA,
    "viridis": cv2.COLORMAP_VIRIDIS,
}

class DepthVideoProcessor:
    def __init__(self, model_name="depth-anything/Depth-Anything-V2-Small-hf"):
        # Determine device
        self.device = 0 if torch.cuda.is_available() else (-1 if not torch.backends.mps.is_available() else 'mps')

        # Load the pipeline
        print(f"Loading Depth Anything V2 model ({model_name}) on device {self.device}...")
        self.pipe = pipeline(
            task="depth-estimation",
            model=model_name,
            device=self.device
        )
        print("Depth Anything V2 loaded successfully.")

    @torch.inference_mode()
    def process_video(self, input_path: str, output_path: str, progress_callback=None, colormap="grayscale", denoise=True, safe_mode="none"):
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

        # Ensure dimensions are divisible by 16
        out_width = out_width - (out_width % 16)
        out_height = out_height - (out_height % 16)

        # Model input resolution: 518px (Depth Anything V2 native)
        model_dim = 518
        model_scale = model_dim / max(width, height)
        model_width = int(width * model_scale)
        model_height = int(height * model_scale)
        model_width = model_width - (model_width % 14)
        model_height = model_height - (model_height % 14)
        if model_width < 14:
            model_width = 14
        if model_height < 14:
            model_height = 14

        # Determine colormap
        cv_colormap = COLORMAP_OPTIONS.get(colormap, None)
        is_color = cv_colormap is not None

        vid_out_width = out_width
        vid_out_height = out_height
        if safe_mode == "side_by_side":
            vid_out_width = out_width * 2
        elif safe_mode == "border":
            vid_out_height = out_height + 80
            
        # Ensure dimensions are even for H.264 codec
        vid_out_width = vid_out_width - (vid_out_width % 2)
        vid_out_height = vid_out_height - (vid_out_height % 2)

        # Use VP9 codec for WebM to ensure browser playback without faststart/moov issues
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        out = cv2.VideoWriter(output_path, fourcc, fps, (vid_out_width, vid_out_height), isColor=True)
        if not out.isOpened():
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (vid_out_width, vid_out_height), isColor=True)

        print(f"Processing {total_frames} frames | V2 Model input: {model_width}x{model_height} | Output: {out_width}x{out_height} | Colormap: {colormap} | Safe Mode: {safe_mode}")
        if progress_callback:
            progress_callback(0, total_frames, elapsed_seconds=0.0, eta_seconds=0.0)

        batch_size = 4
        frame_count = 0
        start_time = time.monotonic()

        # Temporal smoothing buffer (prevents frame-to-frame flickering)
        prev_depth = None
        temporal_weight = 0.7  # Current frame weight (0.7 current + 0.3 previous)

        with torch.no_grad():
            while cap.isOpened():
                batch_pil = []
                batch_originals = []
                for _ in range(batch_size):
                    ret, frame = cap.read()
                    if not ret:
                        break
                    if safe_mode == "side_by_side":
                        batch_originals.append(frame)
                    frame_resized = cv2.resize(frame, (model_width, model_height))
                    image_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(image_rgb)
                    batch_pil.append(pil_image)

                if not batch_pil:
                    break

                results = self.pipe(batch_pil, batch_size=batch_size)

                for idx, result in enumerate(results):
                    depth_map = result["depth"]
                    depth_array = np.array(depth_map, dtype=np.float32)

                    # Clean min-max normalization matching true relative depth
                    d_min = float(depth_array.min())
                    d_max = float(depth_array.max())
                    if d_max - d_min > 0:
                        depth_norm = (depth_array - d_min) / (d_max - d_min)
                    else:
                        depth_norm = np.zeros_like(depth_array)

                    # ── Temporal Stabilization (anti-flicker) ──
                    # Blend current frame with previous using exponential moving average
                    if prev_depth is not None and prev_depth.shape == depth_norm.shape:
                        depth_norm = temporal_weight * depth_norm + (1.0 - temporal_weight) * prev_depth
                    prev_depth = depth_norm.copy()

                    # Convert to 8-bit unsigned integer (0-255)
                    depth_uint8 = (depth_norm * 255.0).astype("uint8")

                    # Resize to output dimensions smoothly
                    depth_uint8 = cv2.resize(depth_uint8, (out_width, out_height), interpolation=cv2.INTER_CUBIC)

                    # Multi-stage Noise Reduction & Edge Preservation
                    if denoise:
                        # 1. Median filter to eliminate grain/speckle noise
                        depth_uint8 = cv2.medianBlur(depth_uint8, 3)
                        # 2. Bilateral filter for ultra-smooth surface with razor-sharp edges
                        depth_uint8 = cv2.bilateralFilter(depth_uint8, d=9, sigmaColor=50, sigmaSpace=50)

                    # ── Glass Effect: Crystal-clear polished depth ──
                    # 1. CLAHE — adaptive contrast for clearer depth separation
                    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                    depth_uint8 = clahe.apply(depth_uint8)

                    # 2. Second bilateral pass — glass-smooth surface polish
                    depth_uint8 = cv2.bilateralFilter(depth_uint8, d=7, sigmaColor=40, sigmaSpace=40)

                    # 3. Unsharp Mask — razor-sharp edges like cut glass
                    blur = cv2.GaussianBlur(depth_uint8, (0, 0), sigmaX=2.0)
                    depth_uint8 = cv2.addWeighted(depth_uint8, 1.4, blur, -0.4, 0)

                    if is_color:
                        depth_out = cv2.applyColorMap(depth_uint8, cv_colormap)
                    else:
                        depth_out = cv2.cvtColor(depth_uint8, cv2.COLOR_GRAY2BGR)

                    if safe_mode == "side_by_side":
                        original = batch_originals[idx]
                        original_resized = cv2.resize(original, (out_width, out_height))
                        frame_out = np.hstack([original_resized, depth_out])
                        cv2.line(frame_out, (out_width, 0), (out_width, out_height), (255, 255, 255), 2)
                        cv2.putText(frame_out, "ORIGINAL", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                        cv2.putText(frame_out, "DEPTH MAP", (out_width + 10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                        depth_out = frame_out

                    elif safe_mode == "overlay":
                        grid_overlay = np.zeros_like(depth_out)
                        for x in range(0, out_width, 80):
                            cv2.line(grid_overlay, (x, 0), (x, out_height), (255, 255, 255), 1)
                        for y in range(0, out_height, 80):
                            cv2.line(grid_overlay, (0, y), (out_width, y), (255, 255, 255), 1)
                        depth_out = cv2.addWeighted(depth_out, 0.85, grid_overlay, 0.15, 0)
                        
                        legend_w, legend_h = 150, 15
                        x_offset = out_width - legend_w - 20
                        y_offset = out_height - legend_h - 20
                        gradient = np.linspace(0, 255, legend_w, dtype=np.uint8)
                        gradient = np.tile(gradient, (legend_h, 1))
                        if is_color:
                            gradient_color = cv2.applyColorMap(gradient, cv_colormap)
                        else:
                            gradient_color = cv2.cvtColor(gradient, cv2.COLOR_GRAY2BGR)
                        depth_out[y_offset:y_offset+legend_h, x_offset:x_offset+legend_w] = gradient_color
                        cv2.putText(depth_out, "Near", (x_offset, y_offset - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                        cv2.putText(depth_out, "Far", (x_offset + legend_w - 25, y_offset - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                        
                        cv2.putText(depth_out, "DEPTH MAP", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                        cv2.putText(depth_out, f"F: {frame_count:04d}", (out_width - 80, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

                    elif safe_mode == "border":
                        depth_out = cv2.copyMakeBorder(depth_out, 40, 40, 0, 0, cv2.BORDER_CONSTANT, value=(0,0,0))
                        top_text = f"DEPTH MAP • {out_width}x{out_height} • {fps:.0f}fps • {colormap}"
                        bottom_text = "AI Depth Estimation • Depth Anything V2"
                        top_size, _ = cv2.getTextSize(top_text, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
                        bottom_size, _ = cv2.getTextSize(bottom_text, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
                        cv2.putText(depth_out, top_text, ((out_width - top_size[0]) // 2, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                        cv2.putText(depth_out, bottom_text, ((out_width - bottom_size[0]) // 2, out_height + 40 + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

                    if depth_out.shape[1] != vid_out_width or depth_out.shape[0] != vid_out_height:
                        depth_out = cv2.resize(depth_out, (vid_out_width, vid_out_height))

                    # Add running timer / timestamp (Record indicator)
                    time_sec = frame_count / fps
                    mins = int(time_sec // 60)
                    secs = int(time_sec % 60)
                    msecs = int((time_sec % 1) * 1000)
                    timer_str = f"REC {mins:02d}:{secs:02d}.{msecs:03d}"
                    
                    cv2.circle(depth_out, (30, vid_out_height - 30), 6, (0, 0, 255), -1)
                    cv2.putText(depth_out, timer_str, (45, vid_out_height - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3, cv2.LINE_AA)
                    cv2.putText(depth_out, timer_str, (45, vid_out_height - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)

                    out.write(depth_out)
                    frame_count += 1

                elapsed = time.monotonic() - start_time
                if frame_count > 0:
                    eta = elapsed * (total_frames - frame_count) / frame_count
                else:
                    eta = 0.0

                if progress_callback:
                    progress_callback(frame_count, total_frames, elapsed_seconds=elapsed, eta_seconds=eta)
                elif frame_count % 10 == 0:
                    print(f"Processed {frame_count}/{total_frames} frames... "
                          f"[elapsed={elapsed:.1f}s, eta={eta:.1f}s]")

        if progress_callback:
            elapsed = time.monotonic() - start_time
            progress_callback(total_frames, total_frames, elapsed_seconds=elapsed, eta_seconds=0.0)

        cap.release()
        out.release()

        # Move moov atom to beginning for browser streaming
        faststart_mp4(output_path)

        # Free MPS memory if applicable
        if self.device == 'mps':
            torch.mps.empty_cache()

        elapsed_total = time.monotonic() - start_time
        print(f"Finished processing video in {elapsed_total:.1f}s. Saved to {output_path}")

if __name__ == "__main__":
    import sys
    colormap_arg = sys.argv[3] if len(sys.argv) > 3 else "grayscale"
    if len(sys.argv) > 2:
        processor = DepthVideoProcessor()
        processor.process_video(sys.argv[1], sys.argv[2], colormap=colormap_arg)
