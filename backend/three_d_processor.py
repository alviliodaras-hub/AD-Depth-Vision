import cv2
import torch
import numpy as np
from PIL import Image
from transformers import pipeline
import os
import time

class ThreeDWhiteCharacterProcessor:
    def __init__(self, model_name="depth-anything/Depth-Anything-V2-Small-hf"):
        self.device = 0 if torch.cuda.is_available() else (-1 if not torch.backends.mps.is_available() else 'mps')
        print(f"Loading 3D White Character processor with model {model_name} on {self.device}...")
        self.pipe = pipeline(
            task="depth-estimation",
            model=model_name,
            device=self.device
        )
        print("3D White Character processor initialized.")

    @torch.inference_mode()
    def process_video(self, input_path: str, output_path: str, progress_callback=None):
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise ValueError(f"Error opening video file {input_path}")

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

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
        if model_width < 14:
            model_width = 14
        if model_height < 14:
            model_height = 14

        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        out = cv2.VideoWriter(output_path, fourcc, fps, (out_width, out_height), isColor=True)
        if not out.isOpened():
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (out_width, out_height), isColor=True)

        print(f"Processing 3D White Character: {total_frames} frames at {out_width}x{out_height}...")
        if progress_callback:
            progress_callback(0, total_frames, elapsed_seconds=0.0, eta_seconds=0.0)

        batch_size = 4
        frame_count = 0
        start_time = time.monotonic()

        # 3D Lighting directions (normalized)
        L_key = np.array([0.4, -0.6, 0.7], dtype=np.float32)
        L_key /= np.linalg.norm(L_key)

        L_fill = np.array([-0.5, 0.3, 0.6], dtype=np.float32)
        L_fill /= np.linalg.norm(L_fill)

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
                    depth_raw = np.array(depth_map, dtype=np.float32)

                    # Normalize depth 0.0 - 1.0
                    d_min = float(depth_raw.min())
                    d_max = float(depth_raw.max())
                    if d_max - d_min > 0:
                        depth_norm = (depth_raw - d_min) / (d_max - d_min)
                    else:
                        depth_norm = np.zeros_like(depth_raw)

                    # Resize depth to target resolution
                    depth_norm = cv2.resize(depth_norm, (out_width, out_height), interpolation=cv2.INTER_CUBIC)

                    # ── Temporal Stabilization (anti-flicker) ──
                    if prev_depth is not None and prev_depth.shape == depth_norm.shape:
                        depth_norm = temporal_weight * depth_norm + (1.0 - temporal_weight) * prev_depth
                    prev_depth = depth_norm.copy()

                    # Smooth depth to produce clean 3D clay surfaces
                    depth_smooth = cv2.bilateralFilter(depth_norm, d=9, sigmaColor=0.1, sigmaSpace=9.0)

                    # Compute 3D Surface Normals using Sobel gradients
                    dzdx = cv2.Sobel(depth_smooth, cv2.CV_32F, 1, 0, ksize=3)
                    dzdy = cv2.Sobel(depth_smooth, cv2.CV_32F, 0, 1, ksize=3)

                    gradient_scale = 12.0
                    nx = -dzdx * gradient_scale
                    ny = -dzdy * gradient_scale
                    nz = np.ones_like(depth_smooth)

                    norm_len = np.sqrt(nx**2 + ny**2 + nz**2)
                    nx /= norm_len
                    ny /= norm_len
                    nz /= norm_len

                    # 3D Shading calculation (Phong Diffuse + Ambient + Specular)
                    diffuse_key = np.maximum(0.0, nx * L_key[0] + ny * L_key[1] + nz * L_key[2])
                    diffuse_fill = np.maximum(0.0, nx * L_fill[0] + ny * L_fill[1] + nz * L_fill[2]) * 0.35
                    ambient = 0.22

                    # Blinn-Phong Specular Highlight (White Clay Shine)
                    half_z = (nz + 1.0) / np.sqrt((nx)**2 + (ny)**2 + (nz + 1.0)**2)
                    specular = np.power(np.maximum(0.0, half_z), 24) * 0.3

                    # Combined 3D light intensity
                    light_intensity = ambient + diffuse_key + diffuse_fill + specular

                    # White Clay Character Material RGB: (245, 247, 250)
                    clay_r = np.clip(light_intensity * 247, 0, 255).astype(np.float32)
                    clay_g = np.clip(light_intensity * 249, 0, 255).astype(np.float32)
                    clay_b = np.clip(light_intensity * 252, 0, 255).astype(np.float32)

                    # Compute crisp 3D Contour Outline Borders (Sobel depth gradient magnitude)
                    depth_u8 = (depth_smooth * 255.0).astype(np.uint8)
                    grad_x = cv2.Sobel(depth_u8, cv2.CV_32F, 1, 0, ksize=3)
                    grad_y = cv2.Sobel(depth_u8, cv2.CV_32F, 0, 1, ksize=3)
                    edge_mag = np.sqrt(grad_x**2 + grad_y**2)
                    edge_stroke = np.clip(edge_mag * 0.035, 0.0, 1.0)
                    outline_factor = 1.0 - edge_stroke

                    # Apply dark outline borders to 3D white clay character
                    clay_r *= outline_factor
                    clay_g *= outline_factor
                    clay_b *= outline_factor

                    # Combine channels to BGR frame
                    render_3d = cv2.merge([clay_b.astype(np.uint8), clay_g.astype(np.uint8), clay_r.astype(np.uint8)])

                    # Create clean background (mask out background areas where depth is low)
                    bg_mask = (depth_smooth < 0.12)
                    dark_bg = np.array([255, 255, 255], dtype=np.uint8)  # White/clean studio canvas background
                    render_3d[bg_mask] = dark_bg

                    out.write(render_3d)
                    frame_count += 1

                elapsed = time.monotonic() - start_time
                if frame_count > 0:
                    eta = elapsed * (total_frames - frame_count) / frame_count
                else:
                    eta = 0.0

                if progress_callback:
                    progress_callback(frame_count, total_frames, elapsed_seconds=elapsed, eta_seconds=eta)
                elif frame_count % 10 == 0:
                    print(f"Processed 3D White Character {frame_count}/{total_frames} frames...")

        if progress_callback:
            elapsed = time.monotonic() - start_time
            progress_callback(total_frames, total_frames, elapsed_seconds=elapsed, eta_seconds=0.0)

        cap.release()
        out.release()

        if self.device == 'mps':
            torch.mps.empty_cache()

        elapsed_total = time.monotonic() - start_time
        print(f"Finished 3D White Character processing in {elapsed_total:.1f}s. Saved to {output_path}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        processor = ThreeDWhiteCharacterProcessor()
        processor.process_video(sys.argv[1], sys.argv[2])
