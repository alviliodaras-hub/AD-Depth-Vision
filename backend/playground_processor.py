import cv2
import torch
import numpy as np
from PIL import Image
from transformers import pipeline
from ultralytics import YOLO
import os
import json
import time

class PlaygroundProcessor:
    def __init__(self, depth_model="depth-anything/Depth-Anything-V2-Small-hf", pose_model="yolov8m-pose.pt"):
        self.device = 0 if torch.cuda.is_available() else (-1 if not torch.backends.mps.is_available() else 'mps')
        print(f"Loading models for 3D Playground on {self.device}...")
        
        self.depth_pipe = pipeline(
            task="depth-estimation",
            model=depth_model,
            device=self.device
        )
        self.pose_model = YOLO(pose_model)
        
        print("Playground models loaded successfully.")

    @torch.inference_mode()
    def process_image(self, input_path: str, output_path: str, video_id: str, processed_dir: str, progress_callback=None):
        if progress_callback:
            progress_callback(10, 100, elapsed_seconds=0.0, eta_seconds=0.0)
            
        print(f"Processing Playground Image: {input_path}")
        image = cv2.imread(input_path)
        if image is None:
            raise ValueError(f"Could not read image: {input_path}")
            
        # Generate Depth Map
        pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        depth_result = self.depth_pipe(pil_img)
        depth_map = depth_result["depth"]
        depth_np = np.array(depth_map)
        
        # Save base image and depth map to processed dir so frontend can load them
        base_filename = f"{video_id}_base.jpg"
        depth_filename = f"{video_id}_depth.jpg"
        
        base_path = os.path.join(processed_dir, base_filename)
        depth_path = os.path.join(processed_dir, depth_filename)
        
        cv2.imwrite(base_path, image)
        cv2.imwrite(depth_path, depth_np)
        
        # Write JSON for frontend to know it's image mode
        scene_data = {
            "mode": "image",
            "base_url": f"/outputs/{base_filename}",
            "depth_url": f"/outputs/{depth_filename}",
            "scene_width": image.shape[1],
            "scene_height": image.shape[0]
        }
        
        with open(output_path, "w") as f:
            json.dump(scene_data, f)
            
        if progress_callback:
            progress_callback(100, 100, elapsed_seconds=1.0, eta_seconds=0.0)
            
        print(f"Playground Image saved to {output_path}")

    @torch.inference_mode()
    def process_video(self, input_path: str, output_path: str, progress_callback=None):
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise ValueError(f"Error opening video file {input_path}")

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        print(f"Processing 3D Playground Data: {total_frames} frames at {width}x{height}...")
        if progress_callback:
            progress_callback(0, total_frames, elapsed_seconds=0.0, eta_seconds=0.0)

        scene_data = {
            "mode": "video",
            "fps": fps,
            "total_frames": total_frames,
            "scene_width": width,
            "scene_height": height,
            "frames": []
        }

        # Model input resolution: 518px (Depth Anything V2 native)
        model_dim = 518
        model_scale = model_dim / max(width, height)
        model_width = int(width * model_scale)
        model_height = int(height * model_scale)
        model_width = model_width - (model_width % 14)
        model_height = model_height - (model_height % 14)
        if model_width < 14: model_width = 14
        if model_height < 14: model_height = 14

        batch_size = 4
        frame_count = 0
        start_time = time.monotonic()

        while cap.isOpened():
            frames = []
            for _ in range(batch_size):
                ret, frame = cap.read()
                if not ret:
                    break
                frames.append(frame)

            if not frames:
                break

            # Process depth for the batch
            batch_pil = []
            for frame in frames:
                frame_resized = cv2.resize(frame, (model_width, model_height))
                image_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                batch_pil.append(Image.fromarray(image_rgb))

            depth_results = self.depth_pipe(batch_pil, batch_size=batch_size)

            for i, frame in enumerate(frames):
                frame_data = {
                    "frame": frame_count,
                    "characters": []
                }

                # 1. Depth extraction
                depth_map = depth_results[i]["depth"]
                depth_raw = np.array(depth_map, dtype=np.float32)
                
                # Normalize depth 0.0 - 1.0 (relative)
                d_min = float(depth_raw.min())
                d_max = float(depth_raw.max())
                if d_max - d_min > 0:
                    depth_norm = (depth_raw - d_min) / (d_max - d_min)
                else:
                    depth_norm = np.zeros_like(depth_raw)
                
                # Resize depth back to original video dimensions for accurate mapping
                depth_full = cv2.resize(depth_norm, (width, height), interpolation=cv2.INTER_CUBIC)

                # 2. Pose extraction
                pose_results = self.pose_model(frame, verbose=False, conf=0.3)
                
                if pose_results and len(pose_results) > 0:
                    result = pose_results[0]
                    if result.keypoints is not None and result.keypoints.data.shape[0] > 0:
                        keypoints_data = result.keypoints.data.cpu().numpy()  # (N, 17, 3)
                        boxes = result.boxes

                        for person_idx, kpts in enumerate(keypoints_data):
                            # Calculate average depth for this person based on keypoints
                            valid_depths = []
                            for kpt in kpts:
                                x, y, conf = kpt
                                if conf > 0.3:
                                    x_idx = min(max(int(x), 0), width - 1)
                                    y_idx = min(max(int(y), 0), height - 1)
                                    valid_depths.append(depth_full[y_idx, x_idx])
                            
                            if valid_depths:
                                avg_depth = float(np.mean(valid_depths))
                            else:
                                avg_depth = 0.5 # fallback

                            bbox = []
                            if boxes is not None and person_idx < len(boxes):
                                box = boxes[person_idx]
                                bbox = [float(v) for v in box.xyxy[0].cpu().numpy()]
                            
                            char_data = {
                                "id": person_idx,
                                "depth_z": avg_depth,
                                "keypoints": [[float(k[0]), float(k[1]), float(k[2])] for k in kpts],
                                "bbox": bbox
                            }
                            frame_data["characters"].append(char_data)
                
                scene_data["frames"].append(frame_data)
                frame_count += 1

            elapsed = time.monotonic() - start_time
            if frame_count > 0:
                eta = elapsed * (total_frames - frame_count) / frame_count
            else:
                eta = 0.0

            if progress_callback:
                progress_callback(frame_count, total_frames, elapsed_seconds=elapsed, eta_seconds=eta)
            elif frame_count % 10 == 0:
                print(f"Processed Playground Data {frame_count}/{total_frames} frames...")

        if progress_callback:
            elapsed = time.monotonic() - start_time
            progress_callback(total_frames, total_frames, elapsed_seconds=elapsed, eta_seconds=0.0)

        cap.release()

        # Save to JSON file instead of video
        with open(output_path, 'w') as f:
            json.dump(scene_data, f)

        if self.device == 'mps':
            torch.mps.empty_cache()

        elapsed_total = time.monotonic() - start_time
        print(f"Finished Playground processing in {elapsed_total:.1f}s. Saved to {output_path}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        processor = PlaygroundProcessor()
        processor.process_video(sys.argv[1], sys.argv[2])
