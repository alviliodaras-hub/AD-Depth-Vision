import os
import io
import cv2
import numpy as np
from PIL import Image
from typing import Dict, Any, Optional

class SketchProcessor:
    """
    Advanced Storyboard & Concept Sketch Converter.
    Converts photographic / real images into hand-drawn storyboard sketches,
    either via Pure AI Redraw (Gemini Vision + Imagen 3) or Fast Local Lineart Synthesis.
    """

    AVAILABLE_STYLES = {
        "ai_storyboard": {
            "name": "🤖 Pure AI Storyboard Redraw",
            "description": "True AI artist re-draw from scratch: preserves composition & poses, drawn as professional storyboard.",
            "icon": "✨"
        },
        "storyboard_pencil": {
            "name": "Storyboard Graphite Pencil",
            "description": "Loose rough graphite pencil sketch with organic shading and warm paper grain.",
            "icon": "✏️"
        },
        "charcoal_draft": {
            "name": "Dramatic Film Charcoal",
            "description": "High contrast chiaroscuro charcoal sketch for dramatic cinematic shots.",
            "icon": "🎬"
        },
        "clean_ink": {
            "name": "Clean Comic / Manga Inking",
            "description": "Sharp black & white lineart with clean contours and hatching.",
            "icon": "✒️"
        },
        "anime_lineart": {
            "name": "Anime Production Lineart",
            "description": "Ultra-crisp fine linework used in animation keyframe production.",
            "icon": "🎌"
        },
        "color_sketch": {
            "name": "Watercolor Storyboard Wash",
            "description": "Concept storyboard with colored wash and marker tones over pencil outlines.",
            "icon": "🎨"
        },
        "blueprint_sketch": {
            "name": "Architectural Blueprint",
            "description": "Technical drafting sketch with classic cyanotype blueprint tones.",
            "icon": "📐"
        }
    }

    def __init__(self):
        self._cached_vision_model = None
        self._cached_api_key = None

    def get_styles(self) -> Dict[str, Any]:
        return self.AVAILABLE_STYLES

    def test_connection(self, api_key: str) -> Dict[str, Any]:
        """
        Tests internet connectivity to Google servers and validates the Gemini API key.
        """
        import time
        import socket

        # 1. Test basic DNS resolution
        try:
            socket.gethostbyname("generativelanguage.googleapis.com")
        except socket.gaierror:
            return {
                "status": "error",
                "error_type": "DNS_OR_OFFLINE",
                "message": "Gagal terhubung ke Google AI (DNS / Offline). Pastikan Mac kamu terhubung ke internet dan DNS aktif."
            }

        # 2. Validate API key and discover vision-capable model
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            
            start_t = time.time()

            # First, discover a vision-capable model (this does actual image test)
            vision_model = self._discover_vision_model(client)

            # Also find any working text model (faster fallback check)
            text_model = None
            if not vision_model:
                candidate_models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash-latest", "gemini-pro"]
                for mod in candidate_models:
                    try:
                        resp = client.models.generate_content(model=mod, contents="Reply OK")
                        if resp and resp.text:
                            text_model = mod
                            break
                    except Exception:
                        continue

                if not text_model:
                    # Try any available model with text
                    try:
                        for m in client.models.list():
                            name = m.name.replace("models/", "") if hasattr(m, "name") else str(m)
                            if "embed" in name.lower() or "aqa" in name.lower():
                                continue
                            try:
                                resp = client.models.generate_content(model=name, contents="Reply OK")
                                if resp and resp.text:
                                    text_model = name
                                    break
                            except Exception:
                                continue
                    except Exception:
                        pass

            latency = round((time.time() - start_t) * 1000)

            if vision_model:
                return {
                    "status": "success",
                    "latency_ms": latency,
                    "model": vision_model,
                    "is_vision_capable": True,
                    "message": f"Koneksi Berhasil! Terhubung ke {vision_model} ({latency}ms). ✅ Vision & Image Generation siap."
                }
            elif text_model:
                return {
                    "status": "success",
                    "latency_ms": latency,
                    "model": text_model,
                    "is_vision_capable": False,
                    "message": (
                        f"Koneksi Berhasil ke {text_model} ({latency}ms). "
                        f"⚠️ Tapi model ini TIDAK mendukung Vision (analisis gambar). "
                        f"AI Artist Redraw mungkin gagal. Gunakan Fast Lineart (Offline) atau buat API Key baru."
                    )
                }
            else:
                raise RuntimeError("Tidak ada model yang kompatibel untuk API Key ini.")
        except Exception as e:
            err_str = str(e)
            if "API_KEY_INVALID" in err_str or "API key not valid" in err_str or "400" in err_str or "403" in err_str:
                msg = "API Key tidak valid. Silakan buat/copy key baru dari aistudio.google.com/app/apikey"
            elif "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                msg = "Quota limit tercapai (Rate Limited). Tunggu sebentar atau gunakan key lain."
            else:
                msg = f"Gagal terhubung: {err_str}"
            return {
                "status": "error",
                "error_type": "API_KEY_ERROR",
                "message": msg
            }

    def _discover_vision_model(self, client, api_key: str = "") -> Optional[str]:
        """
        Discovers a vision-capable model from the user's API key.
        Actually tests with a tiny image to confirm vision support.
        Caches result per API key for performance.
        Returns the model name string or None if no vision model is found.
        """
        # Use cache if same API key
        if api_key and api_key == self._cached_api_key and self._cached_vision_model:
            return self._cached_vision_model

        from PIL import Image as PILImage
        import io

        # Create a tiny 8x8 red test image to probe vision capability
        test_img = PILImage.new("RGB", (8, 8), color=(255, 0, 0))

        # Priority-ordered list of known vision-capable models
        vision_candidates = [
            "gemini-3.6-flash",
            "gemini-3.6-pro",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash-8b",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-1.5-pro-latest",
            "gemini-pro-vision",
            "gemini-pro",
        ]

        def _cache_and_return(model_name):
            if api_key:
                self._cached_api_key = api_key
                self._cached_vision_model = model_name
            return model_name

        # Phase 1: Try hardcoded candidates with actual image
        for mod in vision_candidates:
            try:
                resp = client.models.generate_content(
                    model=mod,
                    contents=["What color is this image? Reply in one word.", test_img]
                )
                if resp and resp.text:
                    return _cache_and_return(mod)
            except Exception:
                continue

        # Phase 2: List ALL available models and try each one with a vision test
        # This catches Gemma 4, future model names, etc.
        try:
            available = list(client.models.list())
            all_model_names = []
            for m in available:
                name = m.name.replace("models/", "") if hasattr(m, "name") else str(m)
                # Skip embedding models and models unlikely to support generateContent
                if "embed" in name.lower() or "aqa" in name.lower():
                    continue
                all_model_names.append(name)

            # Prioritize: gemini first, then gemma, then others
            def sort_key(n):
                nl = n.lower()
                if "gemini" in nl and "flash" in nl:
                    return 0
                if "gemini" in nl and "pro" in nl:
                    return 1
                if "gemini" in nl:
                    return 2
                if "gemma" in nl:
                    return 3
                return 4

            all_model_names.sort(key=sort_key)

            for mod in all_model_names:
                try:
                    resp = client.models.generate_content(
                        model=mod,
                        contents=["What color is this image? Reply in one word.", test_img]
                    )
                    if resp and resp.text:
                        return _cache_and_return(mod)
                except Exception:
                    continue
        except Exception:
            pass

        # Phase 3: Last resort — try any model with text-only (for scene description without image)
        # These models can still be used if we describe the image via local CV analysis
        return None

    def ai_redraw_storyboard(
        self,
        input_path: str,
        output_path: str,
        api_key: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        sketch_variant: str = "pencil"
    ) -> Dict[str, Any]:
        """
        Pure AI Re-Draw: Uses Gemini Vision to analyze composition, characters, and blocking,
        then uses Imagen 3 / GenAI to re-draw a genuine hand-drawn storyboard sketch from scratch.
        """
        from google import genai
        from google.genai import types

        resolved_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not resolved_key:
            raise ValueError("Gemini API Key is required for Pure AI Redraw. Please enter your API key.")

        client = genai.Client(api_key=resolved_key)

        pil_img = Image.open(input_path)

        # Step 0: Check connectivity
        import socket
        try:
            socket.gethostbyname("generativelanguage.googleapis.com")
        except socket.gaierror:
            raise RuntimeError(
                "Gagal terhubung ke Google AI: Koneksi internet offline atau DNS bermasalah. "
                "Pastikan Mac terhubung ke internet."
            )

        # Step 1: Discover a working vision model
        vision_model = self._discover_vision_model(client)
        if not vision_model:
            raise RuntimeError(
                "Tidak ada model Gemini yang tersedia di API Key kamu. "
                "API Key kamu mungkin hanya mendukung model Gemma (text-only) yang tidak bisa menganalisis gambar. "
                "Pastikan kamu menggunakan API Key dari https://aistudio.google.com/app/apikey "
                "yang mendukung model Gemini (bukan Gemma). "
                "Atau gunakan mode 'Fast Lineart (Offline)' yang tidak memerlukan API Key."
            )

        # Step 2: Analyze the visual structure with discovered model
        analysis_prompt = (
            "You are a master film storyboard director and concept artist. "
            "Analyze this reference image in precise visual detail so an artist can RE-DRAW it as a storyboard sketch. "
            "Describe:\n"
            "1. Shot type & Camera Angle (e.g. Extreme Close-Up, Low-Angle Medium Shot, Wide Establishing Shot).\n"
            "2. Subject(s): Exact pose, head orientation, eye gaze, facial expression, body posture, and clothing silhouette.\n"
            "3. Composition & Framing: Rule of thirds, foreground elements, subject placement (left/center/right), background environment geometry.\n"
            "4. Lighting & Shadows: Key light direction, shadow areas.\n\n"
            "Output a single concise paragraph (under 120 words) describing the scene purely for drawing reference. "
            "Do NOT include photo meta descriptions, just pure visual staging."
        )

        scene_analysis = None
        last_err = ""

        # Try the discovered model with the image
        try:
            analysis_resp = client.models.generate_content(
                model=vision_model,
                contents=[analysis_prompt, pil_img]
            )
            if analysis_resp and analysis_resp.text:
                scene_analysis = analysis_resp.text.strip()
        except Exception as e:
            last_err = str(e)
            # The model might exist but not support vision; try other gemini models with image
            vision_candidates_with_image = [
                "gemini-3.6-flash", "gemini-3.6-pro",
                "gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite",
                "gemini-1.5-flash-latest", "gemini-1.5-flash-8b", "gemini-1.5-flash",
                "gemini-1.5-pro", "gemini-pro-vision",
            ]
            for mod in vision_candidates_with_image:
                if mod == vision_model:
                    continue
                try:
                    analysis_resp = client.models.generate_content(
                        model=mod,
                        contents=[analysis_prompt, pil_img]
                    )
                    if analysis_resp and analysis_resp.text:
                        scene_analysis = analysis_resp.text.strip()
                        vision_model = mod
                        break
                except Exception as e2:
                    last_err = str(e2)
                    continue

        # If still no analysis, try dynamic model discovery with image
        if not scene_analysis:
            try:
                available = list(client.models.list())
                gemini_models = []
                for m in available:
                    name = m.name.replace("models/", "") if hasattr(m, "name") else str(m)
                    if "gemini" in name.lower():
                        gemini_models.append(name)
                for mod in gemini_models:
                    try:
                        analysis_resp = client.models.generate_content(
                            model=mod,
                            contents=[analysis_prompt, pil_img]
                        )
                        if analysis_resp and analysis_resp.text:
                            scene_analysis = analysis_resp.text.strip()
                            vision_model = mod
                            break
                    except Exception as e3:
                        last_err = str(e3)
                        continue
            except Exception:
                pass

        if not scene_analysis:
            err_text = str(last_err)
            if "nodename nor servname" in err_text or "gaierror" in err_text:
                raise RuntimeError("Koneksi Internet / DNS gagal: Tidak dapat mengakses generativelanguage.googleapis.com.")
            if "API_KEY_INVALID" in err_text or "403" in err_text:
                raise RuntimeError("Gemini API Key tidak valid. Silakan periksa kembali API Key kamu di Google AI Studio.")
            if "not found" in err_text.lower() or "404" in err_text:
                raise RuntimeError(
                    f"Tidak ada model Gemini Vision yang tersedia untuk API Key ini. "
                    f"Model yang ditemukan ({vision_model}) mungkin tidak mendukung analisis gambar. "
                    f"Coba buat API Key baru di https://aistudio.google.com/app/apikey atau gunakan mode Fast Lineart (Offline). "
                    f"Detail: {err_text}"
                )
            raise RuntimeError(f"Gagal menganalisis gambar: {err_text}")

        # Step 3: Formulate generation prompt for true hand-drawn storyboard
        style_prompt_map = {
            "pure_outline": "pure black and white outline drawing, clean minimalist contour line art, crisp animation keyframe cel linework, absolutely NO shading, NO shadows, NO gradients, NO dark tone fills, pure crisp black line contours on clean pure white paper background, high clarity line drawing",
            "pencil": "authentic film storyboard sketch, rough graphite pencil linework, hand-drawn animatic illustration, expressive loose pencil shading, clean white storyboard paper, black and white charcoal lines, highly detailed linework, production concept sketch",
            "charcoal": "dramatic chiaroscuro charcoal storyboard drawing, bold dark charcoal shading, cinematic film lighting, expressive hand-drawn black and white art, rough sketch contours",
            "ink": "clean black and white comic book lineart, sharp ink contours, manga storyboard panel, hatching shading, no grayscale noise, crisp graphic novel sketch",
            "color": "storyboard concept art sketch, loose pencil line drawing with soft watercolor and marker color wash, expressive brush strokes, film production design sketch"
        }
        chosen_style = style_prompt_map.get(sketch_variant, style_prompt_map["pencil"])

        no_shading_directive = ""
        if sketch_variant == "pure_outline" or (custom_instructions and "tanpa shading" in custom_instructions.lower()):
            no_shading_directive = " STRICT REQUIREMENT: Pure black outline lines ONLY on white background. DO NOT add any shading, shadows, gradients, or grayscale fills."

        final_draw_prompt = (
            f"A masterfully drawn {chosen_style}. "
            f"Scene: {scene_analysis}. "
            f"Strictly hand-drawn storyboard sketch aesthetic, authentic hand-drawn linework, perfectly matched composition and poses. "
            f"{no_shading_directive} "
            f"{custom_instructions if custom_instructions else ''}"
        )

        # Step 4: Generate the redrawn sketch with Imagen 3
        try:
            gen_result = client.models.generate_images(
                model="imagen-3.0-generate-002",
                prompt=final_draw_prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    output_mime_type="image/jpeg",
                    aspect_ratio="1:1" if abs(pil_img.width - pil_img.height) < 50 else ("16:9" if pil_img.width > pil_img.height else "9:16")
                )
            )
        except Exception as e_gen:
            err_text = str(e_gen)
            if "nodename nor servname" in err_text or "gaierror" in err_text:
                raise RuntimeError("Koneksi terputus saat menghubungi AI Image Generator. Periksa koneksi internet Anda.")
            if "RESOURCE_EXHAUSTED" in err_text or "429" in err_text:
                raise RuntimeError("Batas kuota Gemini Image Generation tercapai. Silakan coba lagi beberapa saat.")
            raise RuntimeError(f"Gagal menggambar ulang storyboard: {err_text}")

        if not gen_result.generated_images:
            raise RuntimeError("AI model did not return any generated storyboard sketch.")

        gen_image_bytes = gen_result.generated_images[0].image.image_bytes
        out_image = Image.open(io.BytesIO(gen_image_bytes))
        out_image.save(output_path, "JPEG", quality=95)

        return {
            "width": out_image.width,
            "height": out_image.height,
            "style": "ai_storyboard",
            "output_path": output_path,
            "scene_analysis": scene_analysis,
            "model_used": vision_model
        }


    def convert_image(
        self,
        input_path: str,
        output_path: str,
        style: str = "storyboard_pencil",
        line_weight: float = 1.0,
        shading_intensity: float = 1.0,
        contrast: float = 1.2,
        paper_texture: bool = True
    ) -> Dict[str, Any]:
        """
        Processes an image and saves the resulting storyboard sketch.
        """
        img_bgr = cv2.imread(input_path)
        if img_bgr is None:
            raise ValueError(f"Could not load image from {input_path}")

        h, w = img_bgr.shape[:2]

        # Prevent extreme sizes while preserving high resolution
        max_dim = 2560
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            img_bgr = cv2.resize(img_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            h, w = img_bgr.shape[:2]

        # 1. Grayscale conversion
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        # 2. Bilateral filter for edge-preserving noise reduction
        d_val = max(5, int(9 * (max(h, w) / 1000.0)))
        smoothed = cv2.bilateralFilter(gray, d=d_val, sigmaColor=75, sigmaSpace=75)

        # 3. Invert smoothed image for dodge blending
        inv_smoothed = 255 - smoothed

        # 4. Pencil Dodge Blend algorithm
        base_blur = int(max(3, int(21 * line_weight * (max(h, w) / 1000.0))))
        if base_blur % 2 == 0:
            base_blur += 1
        blurred_inv = cv2.GaussianBlur(inv_smoothed, (base_blur, base_blur), 0)
        dodge = cv2.divide(gray, 255 - blurred_inv, scale=256)

        # 5. Difference of Gaussians (DoG) for artist-like contour lines
        k1 = int(max(3, int(3 * (max(h, w) / 1000.0))))
        if k1 % 2 == 0: k1 += 1
        k2 = int(max(7, int(11 * (max(h, w) / 1000.0))))
        if k2 % 2 == 0: k2 += 1
        
        g1 = cv2.GaussianBlur(gray, (k1, k1), 0)
        g2 = cv2.GaussianBlur(gray, (k2, k2), 0)
        dog = cv2.subtract(g2, g1)
        dog = cv2.normalize(dog, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)
        dog_edges = 255 - dog

        # 6. Adaptive threshold lines for deep linework
        block_size = int(max(7, int(11 * (max(h, w) / 1000.0))))
        if block_size % 2 == 0: block_size += 1
        edges = cv2.adaptiveThreshold(
            smoothed, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block_size, 3
        )

        # Apply specific artistic styles
        if style == "pure_outline" or shading_intensity <= 0.05:
            # Pure black outlines only, absolutely NO shading
            kernel = np.ones((2, 2), np.uint8)
            cleaned_edges = cv2.morphologyEx(edges, cv2.MORPH_OPEN, kernel)
            combined = cv2.multiply(dog_edges, cleaned_edges, scale=1.0 / 255.0)
            _, pure_lines = cv2.threshold(combined, 215, 255, cv2.THRESH_BINARY)
            final_img = cv2.cvtColor(pure_lines, cv2.COLOR_GRAY2BGR)

        elif style == "clean_ink":
            result = cv2.multiply(dodge, edges, scale=1.0 / 255.0)
            result = np.clip((result.astype(np.float32) - 128) * (1.5 * contrast) + 128, 0, 255).astype(np.uint8)
            final_img = cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)

        elif style == "anime_lineart":
            kernel = np.ones((2, 2), np.uint8)
            morphed_edges = cv2.morphologyEx(edges, cv2.MORPH_OPEN, kernel)
            res_gray = cv2.multiply(dodge, morphed_edges, scale=1.0 / 255.0)
            res_gray = np.clip((res_gray.astype(np.float32) - 90) * 1.8 * contrast + 90, 0, 255).astype(np.uint8)
            final_img = cv2.cvtColor(res_gray, cv2.COLOR_GRAY2BGR)

        elif style == "charcoal_draft":
            base = cv2.multiply(dodge, edges, scale=1.0 / 255.0)
            darkened = np.power(base / 255.0, 1.4 * shading_intensity) * 255.0
            if paper_texture:
                noise = np.random.normal(0, 5, darkened.shape)
                darkened = np.clip(darkened + noise, 0, 255)
            charcoal = darkened.astype(np.uint8)
            charcoal_bgr = cv2.cvtColor(charcoal, cv2.COLOR_GRAY2BGR)
            # Film charcoal tone (neutral-slate with warm highlights)
            tint = np.array([0.96, 0.98, 1.0])
            final_img = np.clip(charcoal_bgr * tint, 0, 255).astype(np.uint8)

        elif style == "color_sketch":
            # Edge preserving color smoothing for watercolor feel
            color_smooth = cv2.edgePreservingFilter(img_bgr, flags=1, sigma_s=40, sigma_r=0.35)
            sketch_gray = cv2.multiply(dodge, edges, scale=1.0 / 255.0) / 255.0
            sketch_3ch = np.dstack([sketch_gray, sketch_gray, sketch_gray])
            blended = (color_smooth.astype(np.float32) * sketch_3ch)
            final_img = np.clip(blended * contrast, 0, 255).astype(np.uint8)

        elif style == "blueprint_sketch":
            # Inverted lineart on blueprint blue background
            inv_edges = 255 - cv2.multiply(dog_edges, edges, scale=1.0 / 255.0).astype(np.uint8)
            inv_edges = cv2.threshold(inv_edges, 35, 255, cv2.THRESH_TOZERO)[1]
            
            # Blueprint background: Deep cobalt blue #0b3c6d -> BGR (109, 60, 11)
            bg_b = np.full((h, w), 109, dtype=np.float32)
            bg_g = np.full((h, w), 60, dtype=np.float32)
            bg_r = np.full((h, w), 11, dtype=np.float32)
            
            line_factor = (inv_edges.astype(np.float32) / 255.0) * shading_intensity
            
            # Lines are bright cyan/white
            final_b = np.clip(bg_b + line_factor * (255 - 109), 0, 255)
            final_g = np.clip(bg_g + line_factor * (240 - 60), 0, 255)
            final_r = np.clip(bg_r + line_factor * (220 - 11), 0, 255)
            
            final_img = np.dstack([final_b, final_g, final_r]).astype(np.uint8)

        else:  # Default: storyboard_pencil
            sketch = cv2.multiply(dodge, dog_edges, scale=1.0 / 255.0)
            sketch = cv2.multiply(sketch, edges, scale=1.0 / 255.0)

            # Soft pencil shading gradations
            shading_k = int(max(11, int(21 * (max(h, w) / 1000.0))))
            if shading_k % 2 == 0: shading_k += 1
            shading = cv2.GaussianBlur(gray, (shading_k, shading_k), 0)
            shading = cv2.normalize(shading, None, alpha=90, beta=255, norm_type=cv2.NORM_MINMAX)

            final_gray = (0.75 * sketch.astype(np.float32) + 0.25 * shading.astype(np.float32))
            final_gray = np.clip((final_gray - 128) * contrast + 128, 0, 255)
            
            if shading_intensity != 1.0:
                final_gray = np.power(np.clip(final_gray / 255.0, 0, 1), shading_intensity) * 255.0

            if paper_texture:
                noise = np.random.normal(0, 3, final_gray.shape)
                final_gray = np.clip(final_gray + noise, 0, 255)

            final_gray = final_gray.astype(np.uint8)
            bgr = cv2.cvtColor(final_gray, cv2.COLOR_GRAY2BGR)
            # Storyboard paper ivory warm tone
            paper_tint = np.array([0.94, 0.97, 1.0])
            final_img = np.clip(bgr * paper_tint, 0, 255).astype(np.uint8)

        # Save output
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        cv2.imwrite(output_path, final_img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])

        return {
            "width": w,
            "height": h,
            "style": style,
            "output_path": output_path
        }

    def smart_convert(
        self,
        input_path: str,
        output_path: str,
        style: str = "pure_outline",
        api_key: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        line_weight: float = 1.0,
        shading_intensity: float = 1.0,
        contrast: float = 1.2,
        paper_texture: bool = True
    ) -> Dict[str, Any]:
        """
        Unified conversion method. Tries Pure AI Redraw first if API key is provided.
        Falls back to local Fast Lineart if API key is invalid, missing, or generation fails.
        """
        # Map unified frontend styles to specific AI variants and local styles
        style_mapping = {
            "pure_outline": {"ai": "pure_outline", "local": "pure_outline"},
            "rough_graphite": {"ai": "pencil", "local": "storyboard_pencil"},
            "film_charcoal": {"ai": "charcoal", "local": "charcoal_draft"},
            "clean_ink": {"ai": "ink", "local": "clean_ink"},
            "concept_wash": {"ai": "color", "local": "color_sketch"}
        }
        
        mapping = style_mapping.get(style, style_mapping["pure_outline"])
        
        fallback_msg = None
        if api_key and api_key.strip():
            try:
                res = self.ai_redraw_storyboard(
                    input_path=input_path,
                    output_path=output_path,
                    api_key=api_key.strip(),
                    custom_instructions=custom_instructions,
                    sketch_variant=mapping["ai"]
                )
                res["engine"] = "ai"
                return res
            except Exception as e:
                print(f"AI Redraw failed, falling back to local: {e}")
                fallback_msg = str(e)
                
        # Local Fallback
        res = self.convert_image(
            input_path=input_path,
            output_path=output_path,
            style=mapping["local"],
            line_weight=line_weight,
            shading_intensity=shading_intensity,
            contrast=contrast,
            paper_texture=paper_texture
        )
        res["engine"] = "local"
        if fallback_msg:
            res["fallback_reason"] = f"AI gagal (fallback offline): {fallback_msg}"
        elif not api_key or not api_key.strip():
            res["fallback_reason"] = "API Key tidak disetel, menggunakan mode offline."
        return res
