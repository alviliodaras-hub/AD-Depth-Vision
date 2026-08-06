import cv2
import torch
import numpy as np
from PIL import Image
from transformers import pipeline
import os
import time

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
    def process_video(self, input_path: str, output_path: str, progress_callback=None, colormap="grayscale", denoise=True):
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

        # Use H.264 codec for browser compatibility, fallback to mp4v
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        out = cv2.VideoWriter(output_path, fourcc, fps, (out_width, out_height), isColor=True)
        if not out.isOpened():
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (out_width, out_height), isColor=True)

        print(f"Processing {total_frames} frames | V2 Model input: {model_width}x{model_height} | Output: {out_width}x{out_height} | Colormap: {colormap}")
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
                for _ in range(batch_size):
                    ret, frame = cap.read()
                    if not ret:
                        break
                    frame_resized = cv2.resize(frame, (model_width, model_height))
                    image_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(image_rgb)
                    batch_pil.append(pil_image)

                if not batch_pil:
                    break

                results = self.pipe(batch_pil, batch_size=batch_size)

                for result in results:
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
