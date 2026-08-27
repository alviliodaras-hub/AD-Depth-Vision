import cv2
from google import genai
from PIL import Image
import os

class PromptAnalyzer:
    @staticmethod
    def analyze(video_path: str, location_sheet_path: str, raw_prompt: str, api_key: str) -> str:
        client = genai.Client(api_key=api_key)

        if not os.path.exists(location_sheet_path):
            raise FileNotFoundError(f"Location sheet not found: {location_sheet_path}")
        location_sheet_img = Image.open(location_sheet_path)

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")
            
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            raise ValueError("Video has no frames")

        frame_indices = [
            int(total_frames * 0.1),
            int(total_frames * 0.5),
            int(total_frames * 0.9)
        ]

        frames = []
        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb)
                frames.append(pil_img)
            else:
                print(f"Warning: Could not read frame at index {idx}")

        cap.release()

        prompt_instructions = (
            "You are an expert AI Video Prompt Engineer (for tools like Seedance). "
            "Your task is to rewrite the raw prompt into a highly detailed 'Adjusted Prompt'. "
            "The adjusted prompt must explicitly command the AI to keep the background exactly "
            "like the location sheet, to keep static props (beds, chairs, etc. found in the "
            "location sheet/video) completely frozen, and to correct any camera blocking.\n\n"
            f"Raw Prompt: {raw_prompt}"
        )

        contents = [
            "This is the location sheet/target background:",
            location_sheet_img,
            "This is the source video motion (frames at 10%, 50%, 90%):"
        ]
        contents.extend(frames)
        contents.append(prompt_instructions)

        for model_name in ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-pro']:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents
                )
                if response and response.text:
                    return response.text
            except Exception:
                continue
        raise RuntimeError("Failed to generate content with available Gemini models.")
