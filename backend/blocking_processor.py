import cv2
import numpy as np
import math
from faststart import faststart_mp4

class BlockingProcessor:
    def process_blocking(self, image_path: str, output_path: str, tracks: dict, duration: float, fps: int = 30, progress_callback=None):
        # 1. Load image
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not read image: {image_path}")
            
        h, w = img.shape[:2]
        
        # Resize if max dimension > 1920
        max_dim = max(h, w)
        if max_dim > 1920:
            scale = 1920 / max_dim
            img = cv2.resize(img, (int(w * scale), int(h * scale)))
            h, w = img.shape[:2]
            
        # Use VP9 codec for WebM to ensure browser playback without faststart/moov issues
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        out = cv2.VideoWriter(output_path, fourcc, fps, (w, h), isColor=True)
        if not out.isOpened():
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (w, h), isColor=True)
        
        total_frames = int(duration * fps)
        
        # Pre-process tracks for interpolation
        processed_tracks = {}
        for entity_id, kfs in tracks.items():
            if not kfs:
                continue
            # Sort by time just in case
            kfs.sort(key=lambda x: x["time"])
            
            times = [kf["time"] for kf in kfs]
            xs = [kf["x"] for kf in kfs]
            ys = [kf["y"] for kf in kfs]
            fovs = [kf.get("fov", 1.0) for kf in kfs]
            rots = self._unwrap_angles([kf.get("rot", 0.0) for kf in kfs])
            active_cams = [kf.get("isActiveCamera", False) for kf in kfs]
            
            # Precompute detailed trajectory for this track
            traj_pts = []
            if len(times) > 1:
                for step in range(0, int(times[-1] * fps) + 1, max(1, fps//5)):
                    tt = step / fps
                    tx = self._interpolate(tt, times, xs) * w
                    ty = self._interpolate(tt, times, ys) * h
                    traj_pts.append((int(tx), int(ty)))
            elif len(times) == 1:
                traj_pts.append((int(xs[0] * w), int(ys[0] * h)))
            
            processed_tracks[entity_id] = {
                "times": times,
                "xs": xs,
                "ys": ys,
                "fovs": fovs,
                "rots": rots,
                "active_cams": active_cams,
                "type": kfs[0].get("type", "character"),
                "label": kfs[0].get("label", entity_id),
                "color": kfs[0].get("color", None),
                "trajectory": traj_pts
            }
        
        # Colors for different entities
        colors = [
            (0, 120, 255),  # Orange
            (255, 0, 120),  # Purple
            (0, 255, 0),    # Green
            (255, 255, 0),  # Cyan
            (128, 0, 128),  # Deep purple
            (0, 165, 255)   # Gold
        ]
        
        entity_colors = {}
        for frame in range(total_frames):
            t = frame / fps
            frame_img = img.copy()
            
            for i, (entity_id, track_data) in enumerate(processed_tracks.items()):
                ent_type = track_data["type"]
                label = track_data["label"]
                color_hex = track_data["color"]
                
                # Default color or Hex to BGR
                if color_hex and color_hex.startswith('#'):
                    color_hex = color_hex.lstrip('#')
                    try:
                        color = tuple(int(color_hex[i:i+2], 16) for i in (4, 2, 0)) # BGR
                    except:
                        color = colors[i % len(colors)]
                else:
                    color = colors[i % len(colors)]
                
                times = track_data["times"]
                
                x_norm = self._interpolate(t, times, track_data["xs"])
                y_norm = self._interpolate(t, times, track_data["ys"])
                rot = self._interpolate(t, times, track_data["rots"])
                fov = self._interpolate(t, times, track_data["fovs"])
                
                px = int(x_norm * w)
                py = int(y_norm * h)
                
                ent_type = track_data["type"]
                label = track_data["label"]
                
                # Draw Trajectory
                traj_pts = track_data["trajectory"]
                if len(traj_pts) > 1:
                    cv2.polylines(frame_img, [np.array(traj_pts)], False, (255, 255, 255), 1, cv2.LINE_AA)
                    
                    # Draw small dots on trajectory
                    for pt in traj_pts[::3]:
                        cv2.circle(frame_img, pt, 2, (255, 255, 255), -1)
                
                # Determine active camera at time t
                active_cam = None
                max_past_time = -1
                for eid, td in processed_tracks.items():
                    for j, tm in enumerate(td["times"]):
                        if tm <= t and td["active_cams"][j]:
                            if tm > max_past_time:
                                active_cam = eid
                                max_past_time = tm
                
                is_active = (entity_id == active_cam)
                
                if ent_type == 'character':
                    # Draw filled colored circle with white border
                    cv2.circle(frame_img, (px, py), 15, (255, 255, 255), -1)
                    cv2.circle(frame_img, (px, py), 13, color, -1)
                    
                    # Draw eyeline
                    rot_rad = math.radians(rot - 90) # -90 because 0 is up in HTML, but CV2 0 is right
                    eye_x = px + int(math.cos(rot_rad) * 35)
                    eye_y = py + int(math.sin(rot_rad) * 35)
                    cv2.line(frame_img, (px, py), (eye_x, eye_y), (255, 255, 255), 2, cv2.LINE_AA)
                    cv2.circle(frame_img, (eye_x, eye_y), 3, (0, 255, 255), -1)
                    
                    # Draw text
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    text_size = cv2.getTextSize(label, font, 0.7, 2)[0]
                    text_x = px + 20
                    text_y = py + 5
                    
                    # Background for text
                    cv2.rectangle(frame_img, (text_x-2, text_y - text_size[1] - 2), (text_x + text_size[0] + 2, text_y + 2), (0, 0, 0), -1)
                    cv2.putText(frame_img, label, (text_x, text_y), font, 0.7, (255, 255, 255), 2)
                    
                elif ent_type == 'camera':
                    # Draw camera icon/polygon
                    pts = np.array([
                        [px - 10, py - 10],
                        [px + 10, py - 10],
                        [px + 10, py + 10],
                        [px - 10, py + 10]
                    ], np.int32)
                    
                    rot_rad = math.radians(rot - 90) # Adjust angle 
                    cos_a, sin_a = math.cos(rot_rad), math.sin(rot_rad)
                    
                    rot_pts = []
                    for pt in pts:
                        dx, dy = pt[0] - px, pt[1] - py
                        rx = px + dx * cos_a - dy * sin_a
                        ry = py + dx * sin_a + dy * cos_a
                        rot_pts.append([int(rx), int(ry)])
                        
                    cv2.fillPoly(frame_img, [np.array(rot_pts)], (200, 200, 200) if not is_active else (100, 255, 100))
                    cv2.polylines(frame_img, [np.array(rot_pts)], True, (255, 255, 255), 2)
                    
                    # Draw FOV cone
                    cone_length = fov * w
                    fov_angle = 45 # total fov angle
                    
                    angle1 = (rot - 90) - fov_angle / 2
                    angle2 = (rot - 90) + fov_angle / 2
                    
                    a1_rad = math.radians(angle1)
                    a2_rad = math.radians(angle2)
                    
                    p1 = (int(px + cone_length * math.cos(a1_rad)), int(py + cone_length * math.sin(a1_rad)))
                    p2 = (int(px + cone_length * math.cos(a2_rad)), int(py + cone_length * math.sin(a2_rad)))
                    
                    # Highlight if active
                    fov_color = (0, 255, 0) if is_active else (255, 255, 255)
                    thickness = -1 if is_active else 2
                    
                    overlay = frame_img.copy()
                    cv2.fillPoly(overlay, [np.array([(px, py), p1, p2])], fov_color)
                    alpha = 0.4 if is_active else 0.1
                    cv2.addWeighted(overlay, alpha, frame_img, 1 - alpha, 0, frame_img)
                    
                    # Edges
                    cv2.line(frame_img, (px, py), p1, fov_color, 2 if is_active else 1)
                    cv2.line(frame_img, (px, py), p2, fov_color, 2 if is_active else 1)
                    cv2.line(frame_img, p1, p2, fov_color, 2 if is_active else 1, cv2.LINE_AA)
                    
                    # Label
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    text_size = cv2.getTextSize(label, font, 0.7, 2)[0]
                    text_x = px - text_size[0] // 2
                    text_y = py - 20
                    cv2.rectangle(frame_img, (text_x-2, text_y - text_size[1] - 2), (text_x + text_size[0] + 2, text_y + 2), (0, 0, 0), -1)
                    cv2.putText(frame_img, label, (text_x, text_y), font, 0.7, (255, 255, 255), 2)
            
            out.write(frame_img)
            if progress_callback:
                progress_callback(frame + 1, total_frames, elapsed_seconds=0, eta_seconds=0)
                
        out.release()

        # Move moov atom to beginning for browser streaming
        faststart_mp4(output_path)
        
    def _unwrap_angles(self, angles):
        if not angles:
            return []
        unwrapped = [angles[0]]
        for i in range(1, len(angles)):
            diff = (angles[i] - angles[i-1] + 180) % 360 - 180
            unwrapped.append(unwrapped[-1] + diff)
        return unwrapped

    def _catmull_rom_spline(self, t, t0, t1, t2, t3, p0, p1, p2, p3):
        if t2 == t1:
            return p1
        t_norm = (t - t1) / (t2 - t1)
        
        t_sq = t_norm ** 2
        t_cu = t_norm ** 3
        
        m = np.array([
            [0, 1, 0, 0],
            [-0.5, 0, 0.5, 0],
            [1, -2.5, 2, -0.5],
            [-0.5, 1.5, -1.5, 0.5]
        ])
        
        vec = np.array([1, t_norm, t_sq, t_cu])
        pts = np.array([p0, p1, p2, p3])
        
        return vec @ m @ pts

    def _interpolate(self, t, times, values):
        if not times:
            return 0
        if len(times) == 1:
            return values[0]
        
        if t <= times[0]: return values[0]
        if t >= times[-1]: return values[-1]
        
        idx = 0
        while idx < len(times) - 1 and times[idx+1] < t:
            idx += 1
            
        t1, t2 = times[idx], times[idx+1]
        p1, p2 = values[idx], values[idx+1]
        
        if idx > 0:
            t0 = times[idx-1]
            p0 = values[idx-1]
        else:
            t0 = t1 - (t2 - t1)
            p0 = p1 - (p2 - p1)
            
        if idx < len(times) - 2:
            t3 = times[idx+2]
            p3 = values[idx+2]
        else:
            t3 = t2 + (t2 - t1)
            p3 = p2 + (p2 - p1)
            
        return self._catmull_rom_spline(t, t0, t1, t2, t3, p0, p1, p2, p3)
