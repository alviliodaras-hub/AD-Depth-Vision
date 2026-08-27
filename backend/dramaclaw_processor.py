import re
import json
import csv
import io
from typing import List, Dict, Any, Optional

class DramaClawProcessor:
    """
    DramaClaw AI Storyboard & Camera Director Engine.
    Transforms raw manuscripts/scripts into structured AIGC production storyboard panels,
    with camera movement directives, shot types, character action vectors, lighting cues,
    dialogue timing, and optimized prompts for Runway Gen-3, Luma, Flux, and Midjourney.
    """

    GENRE_STYLES = {
        "cinematic": {
            "name": "Cinematic Drama",
            "lighting_pool": ["Dramatic rim lighting, soft fill, 35mm film grain, anamorphic flare", "Chiaroscuro high contrast, moody atmospheric shadows", "Golden hour warm directional backlight, hazy cinematic glow"],
            "camera_pool": ["Slow Dolly In, shallow depth of field f/1.8", "Smooth Steadicam Tracking Shot", "Cinematic Low Angle Push-in", "Subtle Pan Right, 50mm prime lens"]
        },
        "scifi": {
            "name": "Sci-Fi / Cyberpunk",
            "lighting_pool": ["Neon teal and magenta backlight, volumetric fog, dark ambient reflections", "Holographic glow, harsh laser rim light, futuristic lens flare"],
            "camera_pool": ["Dynamic Fast Tracking Pan", "High Angle Crane Shot, wide 24mm angle", "Rapid Orbit around subject, motion blur"]
        },
        "commercial": {
            "name": "E-Commerce / Commercial Ad",
            "lighting_pool": ["Clean studio softbox lighting, crisp product highlights, pure color rendering", "Modern commercial beauty lighting, high key, vibrant soft reflections"],
            "camera_pool": ["Precision Macro Dolly In", "Smooth Turntable Orbit 360", "Top-Down Flat Lay Slow Zoom In"]
        },
        "anime": {
            "name": "Anime / Otome Game",
            "lighting_pool": ["Vibrant cel-shaded illumination, sparkling bokeh, soft pastel ambient glow", "Dramatic anime rim glow, ethereal rim highlights"],
            "camera_pool": ["Dynamic Dutch Angle Close-Up", "Speedline Push-in on eyes", "Gentle Upward Tilt, cherry blossom foreground blur"]
        },
        "product": {
            "name": "Product Showcase",
            "lighting_pool": ["Studio edge lighting, clean specular reflections on surfaces, neutral dark background", "Spotlight beam, dramatic gradient backdrop, premium rim lighting"],
            "camera_pool": ["Slow Motion Parallax Pan", "Floating Camera Glide", "Extreme Macro Detail Reveal"]
        }
    }

    SHOT_TYPES = [
        "EXTREME LONG SHOT (ELS)",
        "WIDE SHOT (WS)",
        "MEDIUM SHOT (MS)",
        "MEDIUM CLOSE-UP (MCU)",
        "CLOSE-UP (CU)",
        "EXTREME CLOSE-UP (ECU)",
        "OVER-THE-SHOULDER (OTS)",
        "POV (POINT OF VIEW)"
    ]

    CAMERA_MOVEMENTS = [
        "Static (Locked Off)",
        "Slow Dolly In",
        "Dolly Out",
        "Pan Left to Right",
        "Pan Right to Left",
        "Tilt Up",
        "Tilt Down",
        "Steadicam Tracking",
        "360 Degree Orbit",
        "Crane Up / Jib Shot",
        "Dutch Angle Tilt"
    ]

    def generate_storyboard(
        self,
        script_text: str,
        genre_style: str = "cinematic",
        target_model: str = "runway",
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main entrypoint: parses script text into storyboard shots using Gemini if api_key provided,
        or using local intelligent NLP heuristic parser.
        """
        cleaned_script = script_text.strip()
        if not cleaned_script:
            raise ValueError("Script text cannot be empty.")

        if api_key and api_key.strip():
            try:
                return self._generate_with_gemini(cleaned_script, genre_style, target_model, api_key.strip())
            except Exception as e:
                # Fallback to local heuristic if Gemini API encounters error
                print(f"Gemini API generation failed ({e}), falling back to local heuristic parser.")
                result = self._generate_heuristic(cleaned_script, genre_style, target_model)
                result["warning"] = f"Gemini API fallback: {str(e)}"
                return result
        else:
            return self._generate_heuristic(cleaned_script, genre_style, target_model)

    def _generate_with_gemini(
        self,
        script_text: str,
        genre_style: str,
        target_model: str,
        api_key: str
    ) -> Dict[str, Any]:
        from google import genai

        client = genai.Client(api_key=api_key)

        prompt_system = f"""
You are DramaClaw Director, an elite AI Cinematographer and Storyboard Director engine (inspired by DramaClaw AIGC production pipeline).
Your task is to analyze the following screenplay/script/manuscript and decompose it into a sequence of professional storyboard shots.

Parameters:
- Target Genre / Visual Style: {genre_style}
- Target AI Video Model Format: {target_model} (Optimize the 'ai_prompt' specifically for {target_model}, using vivid descriptors, camera lens specifications, atmospheric lighting, and action tags).

You MUST output ONLY valid JSON matching this exact schema:
{{
  "title": "Scene Title or Inferred Logline",
  "genre": "{genre_style}",
  "total_shots": <number>,
  "estimated_total_duration_sec": <number>,
  "shots": [
    {{
      "shot_number": 1,
      "shot_type": "WIDE SHOT (WS) | MEDIUM SHOT (MS) | CLOSE-UP (CU) | etc",
      "camera_movement": "Slow Dolly In | Pan Right | Steadicam Tracking | etc",
      "camera_angle": "Eye Level | Low Angle | High Angle | Dutch Angle | Birds Eye",
      "focal_length": "24mm | 35mm | 50mm | 85mm",
      "lighting": "Description of lighting & color temperature",
      "character_action": "Exact character movement, physical interaction, expression",
      "dialogue_audio": "Spoken line or audio/sound effect cue (or 'None')",
      "duration_sec": 4,
      "ai_prompt": "Highly detailed production prompt tailored for {target_model} with cinematic parameters."
    }}
  ]
}}

Screenplay / Script text:
\"\"\"{script_text}\"\"\"
"""
        models_to_try = [
            'gemini-2.0-flash',
            'gemini-1.5-flash',
            'gemini-1.5-pro',
            'gemini-2.5-flash'
        ]

        last_error = None
        for model_name in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt_system
                )
                if response and response.text:
                    response_text = response.text.strip()
                    
                    # Extract JSON payload with regex
                    match = re.search(r'\{[\s\S]*\}', response_text)
                    if match:
                        json_str = match.group(0)
                        data = json.loads(json_str)
                        data["engine_used"] = f"Gemini AI ({model_name})"
                        return data
                    else:
                        data = json.loads(response_text)
                        data["engine_used"] = f"Gemini AI ({model_name})"
                        return data
            except Exception as e:
                last_error = e
                print(f"Model {model_name} failed: {e}, trying next model...")

        raise RuntimeError(f"All Gemini models failed. Last error: {last_error}")

    def _generate_heuristic(
        self,
        script_text: str,
        genre_style: str,
        target_model: str
    ) -> Dict[str, Any]:
        """
        Intelligent offline parser that extracts sentences, dialogue cues, and character actions,
        and constructs cinematic storyboard panels.
        """
        style_cfg = self.GENRE_STYLES.get(genre_style, self.GENRE_STYLES["cinematic"])
        
        # Split script by scene headers, double newlines, or sentence boundaries
        raw_lines = [l.strip() for l in script_text.split("\n") if l.strip()]
        
        # Segment into logical shot beats
        beats = []
        current_beat = []
        for line in raw_lines:
            current_beat.append(line)
            if len(" ".join(current_beat)) > 60 or line.endswith((".", "!", "?", ":")):
                beats.append(" ".join(current_beat))
                current_beat = []
        if current_beat:
            beats.append(" ".join(current_beat))

        if not beats:
            beats = [script_text]

        # Ensure at least 2 shots if text has multiple phrases
        if len(beats) == 1 and len(script_text) > 80:
            sentences = [s.strip() for s in re.split(r'[.!?]+', script_text) if s.strip()]
            if len(sentences) > 1:
                beats = sentences

        shots = []
        total_duration = 0

        for i, beat in enumerate(beats):
            shot_num = i + 1
            
            # Determine shot progression (Establishing -> Action -> Reaction / Close-up -> Climax)
            if i == 0:
                shot_type = "WIDE SHOT (WS)"
                cam_move = "Slow Dolly In, 35mm cinematic lens"
                cam_angle = "Eye Level"
                focal_len = "35mm"
            elif i == len(beats) - 1:
                shot_type = "MEDIUM CLOSE-UP (MCU)"
                cam_move = "Subtle Handheld Push-In"
                cam_angle = "Slight Low Angle"
                focal_len = "50mm"
            elif i % 3 == 1:
                shot_type = "MEDIUM SHOT (MS)"
                cam_move = "Steadicam Tracking Shot"
                cam_angle = "Eye Level"
                focal_len = "50mm"
            elif i % 3 == 2:
                shot_type = "CLOSE-UP (CU)"
                cam_move = "Static with shallow depth of field"
                cam_angle = "Low Angle"
                focal_len = "85mm"
            else:
                shot_type = "OVER-THE-SHOULDER (OTS)"
                cam_move = "Pan Left to Right"
                cam_angle = "Eye Level"
                focal_len = "50mm"

            # Check if dialogue is present (e.g., 'Character: "dialogue"' or quotes)
            dialogue = "None"
            dialogue_match = re.search(r'([A-Za-z0-9_ ]+):\s*["\']?([^"\']+)["\']?', beat)
            if dialogue_match:
                dialogue = f"{dialogue_match.group(1)}: \"{dialogue_match.group(2)}\""
            elif '"' in beat or "'" in beat:
                quotes = re.findall(r'["\']([^"\']+)["\']', beat)
                if quotes:
                    dialogue = f"\"{quotes[0]}\""

            # Pick lighting based on style
            lighting_list = style_cfg["lighting_pool"]
            lighting = lighting_list[i % len(lighting_list)]

            # Action description
            character_action = beat

            # Duration calculation (3 to 6 seconds per beat)
            word_count = len(beat.split())
            duration = max(3, min(7, 3 + (word_count // 10)))
            total_duration += duration

            # Format AI Prompt tailored for target model
            ai_prompt = self._build_prompt_string(
                shot_type=shot_type,
                cam_move=cam_move,
                action=beat,
                lighting=lighting,
                focal_len=focal_len,
                style_name=style_cfg["name"],
                target_model=target_model
            )

            shots.append({
                "shot_number": shot_num,
                "shot_type": shot_type,
                "camera_movement": cam_move,
                "camera_angle": cam_angle,
                "focal_length": focal_len,
                "lighting": lighting,
                "character_action": character_action,
                "dialogue_audio": dialogue,
                "duration_sec": duration,
                "ai_prompt": ai_prompt
            })

        return {
            "title": f"{style_cfg['name']} Scene Breakdown",
            "genre": genre_style,
            "total_shots": len(shots),
            "estimated_total_duration_sec": total_duration,
            "shots": shots
        }

    def _build_prompt_string(
        self,
        shot_type: str,
        cam_move: str,
        action: str,
        lighting: str,
        focal_len: str,
        style_name: str,
        target_model: str
    ) -> str:
        base_desc = f"{shot_type}, {style_name} style. {action}. {cam_move}, shot on {focal_len} lens. {lighting}, hyperrealistic textures, cinematic color grading, 8k resolution, Masterpiece."
        
        if target_model.lower() == "midjourney":
            return f"/imagine prompt: {base_desc} --ar 16:9 --style raw --v 6.0"
        elif target_model.lower() == "flux":
            return f"{base_desc}, photorealistic, fine details, raytraced lighting, ultra-sharp focus."
        elif target_model.lower() == "luma":
            return f"[Camera: {cam_move}] {base_desc} Fluid motion, seamless temporal coherence, photoreal cinematic."
        elif target_model.lower() == "runway":
            return f"{base_desc} Camera motion: {cam_move}. Highly stable photoreal scene, 4k cinematic render."
        else:
            return base_desc

    def export_csv(self, storyboard_data: Dict[str, Any]) -> str:
        """
        Converts storyboard shot list into formatted CSV table for filmmaking & production use.
        """
        output = io.StringIO()
        writer = csv.writer(output)
        
        # CSV Headers
        writer.writerow([
            "Shot #",
            "Shot Type",
            "Camera Movement",
            "Camera Angle",
            "Focal Length",
            "Action / Visual Beat",
            "Dialogue / Audio Cue",
            "Duration (sec)",
            "Lighting & Atmosphere",
            "AI Generation Prompt"
        ])

        for shot in storyboard_data.get("shots", []):
            writer.writerow([
                shot.get("shot_number", ""),
                shot.get("shot_type", ""),
                shot.get("camera_movement", ""),
                shot.get("camera_angle", ""),
                shot.get("focal_length", ""),
                shot.get("character_action", ""),
                shot.get("dialogue_audio", ""),
                shot.get("duration_sec", ""),
                shot.get("lighting", ""),
                shot.get("ai_prompt", "")
            ])

        return output.getvalue()
