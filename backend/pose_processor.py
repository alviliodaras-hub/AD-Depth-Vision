import cv2
import numpy as np
from ultralytics import YOLO
import time

# Skeleton connections (COCO format: 17 keypoints)
SKELETON = [
    (0, 1), (0, 2),      # nose → left_eye, nose → right_eye
    (1, 3), (2, 4),      # eyes → ears
    (5, 6),              # left_shoulder → right_shoulder
    (5, 7), (7, 9),      # left_shoulder → left_elbow → left_wrist
    (6, 8), (8, 10),     # right_shoulder → right_elbow → right_wrist
    (5, 11), (6, 12),    # shoulders → hips
    (11, 12),            # left_hip → right_hip
    (11, 13), (13, 15),  # left_hip → left_knee → left_ankle
    (12, 14), (14, 16),  # right_hip → right_knee → right_ankle
]

# Colors for different detected persons (BGR)
PERSON_COLORS = [
    (0, 255, 128),   # Green
    (255, 128, 0),   # Blue-orange
    (0, 128, 255),   # Orange
    (255, 0, 128),   # Pink
    (128, 255, 0),   # Lime
    (0, 255, 255),   # Yellow
    (255, 0, 255),   # Magenta
    (128, 0, 255),   # Purple
    (255, 255, 0),   # Cyan
    (0, 165, 255),   # Orange-2
]

KEYPOINT_NAMES = [
    "Nose", "L-Eye", "R-Eye", "L-Ear", "R-Ear",
    "L-Shoulder", "R-Shoulder", "L-Elbow", "R-Elbow",
    "L-Wrist", "R-Wrist", "L-Hip", "R-Hip",
    "L-Knee", "R-Knee", "L-Ankle", "R-Ankle"
]


class PoseVideoProcessor:
    def __init__(self, model_name="yolov8m-pose.pt"):
        print(f"Loading pose estimation model {model_name}...")
        self.model = YOLO(model_name)
        print("Pose model loaded successfully.")

    def process_video(self, input_path: str, output_path: str, progress_callback=None):
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise ValueError(f"Error opening video file {input_path}")

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Output resolution capped at 720p
        max_dim = 720
        if max(width, height) > max_dim:
            scale = max_dim / max(width, height)
            out_width = int(width * scale)
            out_height = int(height * scale)
        else:
            out_width = width
            out_height = height

        # Ensure dimensions divisible by 2
        out_width = out_width - (out_width % 2)
        out_height = out_height - (out_height % 2)

        # Video writer
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        out = cv2.VideoWriter(output_path, fourcc, fps, (out_width, out_height), isColor=True)
        if not out.isOpened():
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (out_width, out_height), isColor=True)

        print(f"Processing {total_frames} frames at {out_width}x{out_height}...")
        if progress_callback:
            progress_callback(0, total_frames, elapsed_seconds=0.0, eta_seconds=0.0)

        frame_count = 0
        start_time = time.monotonic()

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # Resize frame
            if out_width != width or out_height != height:
                frame = cv2.resize(frame, (out_width, out_height))

            # Run pose detection
            results = self.model(frame, verbose=False, conf=0.3)

            # Create dark overlay for the output (skeleton on dark bg)
            overlay = np.zeros_like(frame, dtype=np.uint8)
            # Slightly visible original frame (20% opacity)
            overlay = cv2.addWeighted(frame, 0.2, overlay, 0.8, 0)

            if results and len(results) > 0:
                result = results[0]
                if result.keypoints is not None and result.keypoints.data.shape[0] > 0:
                    keypoints_data = result.keypoints.data.cpu().numpy()  # (N, 17, 3)
                    boxes = result.boxes

                    for person_idx, kpts in enumerate(keypoints_data):
                        color = PERSON_COLORS[person_idx % len(PERSON_COLORS)]

                        # Draw bounding box with person label
                        if boxes is not None and person_idx < len(boxes):
                            box = boxes[person_idx]
                            x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                            conf = float(box.conf[0].cpu().numpy())
                            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
                            label = f"Person {person_idx + 1} ({conf:.0%})"
                            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                            cv2.rectangle(overlay, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
                            cv2.putText(overlay, label, (x1 + 2, y1 - 4),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

                        # Draw skeleton connections
                        for (i, j) in SKELETON:
                            x1_k, y1_k, c1 = kpts[i]
                            x2_k, y2_k, c2 = kpts[j]
                            if c1 > 0.3 and c2 > 0.3:
                                pt1 = (int(x1_k), int(y1_k))
                                pt2 = (int(x2_k), int(y2_k))
                                cv2.line(overlay, pt1, pt2, color, 2, cv2.LINE_AA)

                        # Draw keypoints
                        for kpt_idx, (x, y, conf) in enumerate(kpts):
                            if conf > 0.3:
                                cx, cy = int(x), int(y)
                                # Outer circle
                                cv2.circle(overlay, (cx, cy), 5, color, -1, cv2.LINE_AA)
                                # Inner bright dot
                                cv2.circle(overlay, (cx, cy), 2, (255, 255, 255), -1, cv2.LINE_AA)

            # Person count overlay (top left)
            if results and len(results) > 0 and results[0].keypoints is not None:
                n_persons = results[0].keypoints.data.shape[0]
            else:
                n_persons = 0
            count_text = f"Detected: {n_persons} person{'s' if n_persons != 1 else ''}"
            cv2.rectangle(overlay, (8, 8), (220, 36), (0, 0, 0), -1)
            cv2.putText(overlay, count_text, (12, 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 128), 2, cv2.LINE_AA)

            out.write(overlay)
            frame_count += 1

            elapsed = time.monotonic() - start_time
            if frame_count > 0:
                eta = elapsed * (total_frames - frame_count) / frame_count
            else:
                eta = 0.0

            if progress_callback:
                progress_callback(frame_count, total_frames, elapsed_seconds=elapsed, eta_seconds=eta)
            elif frame_count % 10 == 0:
                print(f"Processed {frame_count}/{total_frames} frames...")

        if progress_callback:
            elapsed = time.monotonic() - start_time
            progress_callback(total_frames, total_frames, elapsed_seconds=elapsed, eta_seconds=0.0)

        cap.release()
        out.release()

        elapsed_total = time.monotonic() - start_time
        print(f"Finished pose processing in {elapsed_total:.1f}s. Saved to {output_path}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        processor = PoseVideoProcessor()
        processor.process_video(sys.argv[1], sys.argv[2])
