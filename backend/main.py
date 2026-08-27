from fastapi import FastAPI, File, UploadFile, BackgroundTasks, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import shutil
import os
import uuid
from dotenv import load_dotenv

# Load environment variables from .env file (if it exists)
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

# Resolve paths relative to this script's directory (not CWD)
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_BACKEND_DIR)

COLORMAP_OPTIONS = {
    "grayscale": None,
    "turbo": "turbo",
    "magma": "magma",
    "inferno": "inferno",
    "plasma": "plasma",
    "viridis": "viridis",
}

app = FastAPI(title="AD-Depth Vision API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(_PROJECT_DIR, "uploads"))
PROCESSED_DIR = os.environ.get("PROCESSED_DIR", os.path.join(_PROJECT_DIR, "processed"))
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

_FRONTEND_DIR = os.path.join(_PROJECT_DIR, "frontend")
app.mount("/app", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")
app.mount("/outputs", StaticFiles(directory=PROCESSED_DIR), name="outputs")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Lazy loaded AI processors (Instant server startup!)
depth_processor = None
three_d_processor = None
playground_processor = None
autocut_processor = None
blocking_processor = None
sceneflow_aligner = None

processing_status = {}

@app.get("/colormaps")
async def get_colormaps():
    return {"colormaps": list(COLORMAP_OPTIONS.keys())}

import socket
@app.get("/network-ip")
async def get_network_ip():
    try:
        # Use a dummy connection to a private IP space. 
        # This forces the OS to pick the active local network interface, even without internet.
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        
        # If it still returns localhost, try gethostname
        if ip.startswith("127."):
            ip = socket.gethostbyname(socket.gethostname())
            
        return {"ip": ip}
    except Exception:
        return {"ip": "127.0.0.1"}

# --- WebSocket Manager for Camera Sync ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str, sender: WebSocket):
        for connection in self.active_connections:
            if connection != sender:
                try:
                    await connection.send_text(message)
                except Exception:
                    pass

camera_manager = ConnectionManager()

@app.websocket("/ws/camera")
async def websocket_camera_endpoint(websocket: WebSocket):
    await camera_manager.connect(websocket)
    try:
        while True:
            # Receive quaternion data as text
            data = await websocket.receive_text()
            # Broadcast to all other clients
            await camera_manager.broadcast(data, websocket)
    except WebSocketDisconnect:
        camera_manager.disconnect(websocket)
    except Exception:
        camera_manager.disconnect(websocket)


@app.post("/playground/process-image")
async def playground_process_image(
    file: UploadFile = File(...)
):
    """Process a single image to generate depth map for 3D playground use."""
    global playground_processor
    
    if not file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        return JSONResponse(status_code=400, content={"message": "Please upload an image file (JPG/PNG)"})
    
    video_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    input_path = os.path.join(UPLOAD_DIR, f"{video_id}{ext}")
    
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        if not playground_processor:
            from playground_processor import PlaygroundProcessor
            playground_processor = PlaygroundProcessor()
        
        output_path = os.path.join(PROCESSED_DIR, f"{video_id}.json")
        playground_processor.process_image(input_path, output_path, video_id, PROCESSED_DIR)
        
        return {
            "status": "completed",
            "base_url": f"/outputs/{video_id}_base.jpg",
            "depth_url": f"/outputs/{video_id}_depth.jpg"
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": str(e)})

from typing import Optional

@app.post("/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mode: str = Form("depth"),
    colormap: str = Form("grayscale"),
    safe_mode: str = Form("none"),
    autocut_capture: str = Form("mid_frame"),
    location_sheet: Optional[UploadFile] = File(None)
):
    is_image = file.filename.lower().endswith(('.jpg', '.jpeg', '.png'))
    is_video = file.filename.lower().endswith(('.mp4', '.avi', '.mov'))
    
    if not is_video and not (is_image and mode == "playground"):
        return JSONResponse(status_code=400, content={"message": "Invalid file format. Please upload a video."})
    if colormap not in COLORMAP_OPTIONS:
        colormap = "grayscale"
    
    video_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    input_path = os.path.join(UPLOAD_DIR, f"{video_id}{ext}")
    
    if mode == "playground":
        output_path = os.path.join(PROCESSED_DIR, f"{video_id}.json")
    else:
        output_path = os.path.join(PROCESSED_DIR, f"{video_id}.mp4")
    
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    location_sheet_path = None
    if location_sheet:
        import tempfile
        location_sheet_path = os.path.join(tempfile.gettempdir(), location_sheet.filename)
        with open(location_sheet_path, "wb") as buffer:
            shutil.copyfileobj(location_sheet.file, buffer)
            
    processing_status[video_id] = {"status": "processing", "progress": 0, "total": 0}
    
    background_tasks.add_task(process_video_task, video_id, input_path, output_path, mode, colormap, safe_mode, autocut_capture, location_sheet_path)
    
    return {"video_id": video_id, "status": "processing"}

def process_video_task(video_id: str, input_path: str, output_path: str, mode: str = "depth", colormap: str = "grayscale", safe_mode: str = "none", autocut_capture: str = "mid_frame", location_sheet_path: str = None):
    global depth_processor, three_d_processor, playground_processor, autocut_processor
    
    def update_progress(current, total, **kwargs):
        processing_status[video_id] = {
            "status": "processing",
            "progress": current,
            "total": total,
            "elapsed": round(kwargs.get("elapsed_seconds", 0), 1),
            "eta": round(kwargs.get("eta_seconds", 0), 1)
        }

    try:
        if mode == "3d_white":
            if not three_d_processor:
                from three_d_processor import ThreeDWhiteCharacterProcessor
                three_d_processor = ThreeDWhiteCharacterProcessor()
            three_d_processor.process_video(input_path, output_path, progress_callback=update_progress, safe_mode=safe_mode)
        elif mode == "playground":
            if not playground_processor:
                from playground_processor import PlaygroundProcessor
                playground_processor = PlaygroundProcessor()
            
            # Check if input is image or video
            if input_path.lower().endswith(('.jpg', '.jpeg', '.png')):
                playground_processor.process_image(input_path, output_path, video_id, PROCESSED_DIR, progress_callback=update_progress)
            else:
                playground_processor.process_video(input_path, output_path, progress_callback=update_progress)
        elif mode == "autocut":
            if not autocut_processor:
                from autocut_processor import AutocutProcessor
                autocut_processor = AutocutProcessor()
            res = autocut_processor.process_video(
                input_path, output_path, progress_callback=update_progress, 
                autocut_capture=autocut_capture
            )
        else:
            if not depth_processor:
                from processor import DepthVideoProcessor
                depth_processor = DepthVideoProcessor()
            depth_processor.process_video(input_path, output_path, progress_callback=update_progress, colormap=colormap, safe_mode=safe_mode)
        # Ensure Safari compatibility
        if mode != "autocut" and mode != "playground":
            from safari_encode import convert_for_web
            convert_for_web(output_path)
            
        status_data = {"status": "completed"}
        if mode == "autocut" and 'res' in locals() and isinstance(res, list):
            status_data["frames"] = [
                f"/outputs/{os.path.relpath(p, PROCESSED_DIR)}" for p in res
            ]
        
        processing_status[video_id] = status_data
    except Exception as e:
        print(f"Error processing video {video_id}: {e}")
        processing_status[video_id] = {"status": "error"}

@app.post("/generate_blocking")
async def generate_blocking(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    tracks: str = Form(...),
    duration: float = Form(...)
):
    import json
    
    video_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    input_path = os.path.join(UPLOAD_DIR, f"{video_id}_bg{ext}")
    output_path = os.path.join(PROCESSED_DIR, f"{video_id}.mp4")
    
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        tracks_data = json.loads(tracks)
    except Exception as e:
        return JSONResponse(status_code=400, content={"message": "Invalid tracks JSON"})
        
    processing_status[video_id] = {"status": "processing", "progress": 0, "total": 0}
    
    background_tasks.add_task(process_blocking_task, video_id, input_path, output_path, tracks_data, duration)
    
    return {"video_id": video_id, "status": "processing"}

def process_blocking_task(video_id: str, input_path: str, output_path: str, tracks_data: dict, duration: float):
    global blocking_processor
    
    def update_progress(current, total, **kwargs):
        processing_status[video_id] = {
            "status": "processing",
            "progress": current,
            "total": total,
            "elapsed": round(kwargs.get("elapsed_seconds", 0), 1),
            "eta": round(kwargs.get("eta_seconds", 0), 1)
        }
        
    try:
        if not blocking_processor:
            from blocking_processor import BlockingProcessor
            blocking_processor = BlockingProcessor()
            
        blocking_processor.process_blocking(input_path, output_path, tracks_data, duration, fps=30, progress_callback=update_progress)
        
        json_log_path = os.path.join(PROCESSED_DIR, f"{video_id}_log.json")
        import json
        with open(json_log_path, "w") as f:
            json.dump({"duration": duration, "tracks": tracks_data}, f, indent=4)
        from safari_encode import convert_for_web
        convert_for_web(output_path)
        
        processing_status[video_id] = {
            "status": "completed", 
            "log": f"/outputs/{video_id}_log.json"
        }
    except Exception as e:
        print(f"Error processing blocking {video_id}: {e}")
        processing_status[video_id] = {"status": "error", "message": str(e)}

from typing import Optional
from pydantic import BaseModel
class GenerateGridRequest(BaseModel):
    video_id: str
    frames: list
    layout_mode: Optional[str] = "all"
    autocut_capture: Optional[str] = "mid_frame"

@app.post("/generate_grid")
async def generate_grid(request: GenerateGridRequest):
    import cv2
    import numpy as np
    
    if not request.frames:
        return JSONResponse(status_code=400, content={"message": "No frames provided."})
        
    loaded_frames = []
    for frame_url in request.frames:
        # url is /outputs/...
        rel_path = frame_url.replace("/outputs/", "")
        abs_path = os.path.join(PROCESSED_DIR, rel_path)
        if os.path.exists(abs_path):
            img = cv2.imread(abs_path)
            if img is not None:
                loaded_frames.append(img)
                
    if not loaded_frames:
        return JSONResponse(status_code=400, content={"message": "Could not load any of the selected frames."})
        
    target_w = 640
    aspect_ratios = [f.shape[1] / f.shape[0] for f in loaded_frames]
    avg_aspect = sum(aspect_ratios) / len(aspect_ratios)
    target_h = int(target_w / avg_aspect)
    gap = 2  # Clean minimal border between cells
    
    # Split frames based on layout mode
    chunks = []
    if request.layout_mode == "3x3":
        for i in range(0, len(loaded_frames), 9):
            chunks.append(loaded_frames[i:i+9])
    else:
        chunks.append(loaded_frames)
        
    grid_urls = []
    
    for chunk_idx, chunk in enumerate(chunks):
        num_frames = len(chunk)
        
        if request.layout_mode == "3x3":
            cols = min(3, num_frames)
            rows = int(np.ceil(num_frames / 3))
        else:
            cols = min(3, num_frames) if num_frames <= 6 else int(np.ceil(np.sqrt(num_frames)))
            rows = int(np.ceil(num_frames / cols))
            
        # Calculate seamless grid dimensions
        grid_w = (cols * target_w) + (max(0, cols - 1) * gap)
        grid_h = (rows * target_h) + (max(0, rows - 1) * gap)
        
        # Background canvas
        grid_img = np.zeros((grid_h, grid_w, 3), dtype=np.uint8)
        
        for i, frame in enumerate(chunk):
            r = i // cols
            c = i % cols
            
            # Resize frame
            resized = cv2.resize(frame, (target_w, target_h))
            
            # Calculate positions
            x_offset = c * (target_w + gap)
            y_offset = r * (target_h + gap)
            
            # Place frame
            grid_img[y_offset:y_offset+target_h, x_offset:x_offset+target_w] = resized
            
        part_suffix = f"_part{chunk_idx+1}" if len(chunks) > 1 else ""
        grid_filename = f"{request.video_id}_grid{part_suffix}.jpg"
        grid_path = os.path.join(PROCESSED_DIR, grid_filename)
        cv2.imwrite(grid_path, grid_img)
        
        grid_urls.append(f"/outputs/{grid_filename}")
        
    return {"grid_urls": grid_urls}

# --- SceneFlow: Screenplay-Video Sync & Cue Analyzer Endpoints ---
@app.post("/sceneflow/align_video_script")
async def sceneflow_align_video_script(
    video: UploadFile = File(...),
    script_text: str = Form(...)
):
    global sceneflow_aligner
    try:
        if not script_text or not script_text.strip():
            return JSONResponse(status_code=400, content={"status": "error", "message": "Script text is required."})

        # Save uploaded video
        video_id = f"sceneflow_{uuid.uuid4()}"
        ext = os.path.splitext(video.filename)[1] or ".mp4"
        video_filename = f"{video_id}{ext}"
        saved_video_path = os.path.join(PROCESSED_DIR, video_filename)

        with open(saved_video_path, "wb") as buffer:
            shutil.copyfileobj(video.file, buffer)

        # Run SceneFlow Aligner
        if not sceneflow_aligner:
            from sceneflow_aligner import SceneFlowAligner
            sceneflow_aligner = SceneFlowAligner()

        alignment_result = sceneflow_aligner.align(saved_video_path, script_text)
        alignment_result["video_url"] = f"/outputs/{video_filename}"
        alignment_result["video_id"] = video_id
        alignment_result["raw_script"] = script_text

        return JSONResponse(content=alignment_result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

class SceneFlowExportRequest(BaseModel):
    project_data: dict

@app.post("/sceneflow/export_project")
async def sceneflow_export_project(req: SceneFlowExportRequest):
    try:
        from fastapi.responses import Response
        json_str = json.dumps(req.project_data, indent=2)
        return Response(
            content=json_str,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=sceneflow_project.json"}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.post("/sceneflow/extract_document")
async def sceneflow_extract_document(file: UploadFile = File(...)):
    try:
        filename = file.filename or "script.txt"
        ext = os.path.splitext(filename)[1].lower()
        content = await file.read()

        if ext == ".pdf":
            import io
            from pypdf import PdfReader
            pdf_file = io.BytesIO(content)
            reader = PdfReader(pdf_file)
            extracted_text = []
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    extracted_text.append(t.strip())
            full_text = "\n\n".join(extracted_text)
            if not full_text.strip():
                return JSONResponse(status_code=400, content={"status": "error", "message": "No readable text found in PDF."})
            return {"status": "success", "text": full_text}
        
        else:
            # Try decoding as text (.txt, .fountain, .md)
            try:
                full_text = content.decode("utf-8")
            except UnicodeDecodeError:
                full_text = content.decode("latin-1", errors="ignore")
            return {"status": "success", "text": full_text}

    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": f"Failed to read file: {str(e)}"})

@app.get("/status/{video_id}")
async def get_status(video_id: str):
    info = processing_status.get(video_id, {"status": "not_found"})
    if isinstance(info, str):
        info = {"status": info}
    return {"video_id": video_id, **info}

@app.get("/download/{video_id}")
async def download_video(video_id: str):
    output_path = os.path.join(PROCESSED_DIR, f"{video_id}.mp4")
    if os.path.exists(output_path):
        return FileResponse(output_path, media_type="video/mp4", filename=f"processed_{video_id}.mp4")
    return JSONResponse(status_code=404, content={"message": "Video not found or not processed yet"})

@app.get("/download_log/{video_id}")
async def download_log(video_id: str):
    output_path = os.path.join(PROCESSED_DIR, f"{video_id}_log.json")
    if os.path.exists(output_path):
        return FileResponse(output_path, media_type="application/json", filename=f"blocking_log_{video_id}.json")
    return JSONResponse(status_code=404, content={"message": "Log not found or not processed yet"})

@app.get("/scene/{video_id}")
async def get_scene(video_id: str):
    output_path = os.path.join(PROCESSED_DIR, f"{video_id}.json")
    if os.path.exists(output_path):
        return FileResponse(output_path, media_type="application/json")
    return JSONResponse(status_code=404, content={"message": "Scene data not found or not processed yet"})

sketch_processor = None

@app.get("/sketch/styles")
async def get_sketch_styles():
    global sketch_processor
    if not sketch_processor:
        from sketch_processor import SketchProcessor
        sketch_processor = SketchProcessor()
    return {"styles": sketch_processor.get_styles()}

class TestConnectionRequest(BaseModel):
    api_key: str

@app.post("/sketch/test_connection")
async def test_sketch_connection(req: TestConnectionRequest):
    global sketch_processor
    if not sketch_processor:
        from sketch_processor import SketchProcessor
        sketch_processor = SketchProcessor()
    
    final_key = req.api_key.strip() if req.api_key and req.api_key.strip() else os.environ.get("GEMINI_API_KEY", "")
    if not final_key:
        return JSONResponse(status_code=400, content={"status": "error", "message": "API Key tidak boleh kosong (baik dari client maupun server)."})
        
    result = sketch_processor.test_connection(final_key)
    if result.get("status") == "error":
        return JSONResponse(status_code=400, content=result)
    return result

@app.post("/sketch/convert")
async def convert_image_to_sketch(
    file: UploadFile = File(...),
    style: str = Form("storyboard_pencil"),
    line_weight: float = Form(1.0),
    shading: float = Form(1.0),
    contrast: float = Form(1.2),
    paper_texture: bool = Form(True),
    api_key: Optional[str] = Form(None),
    custom_instructions: Optional[str] = Form(None),
    sketch_variant: str = Form("pencil")
):
    global sketch_processor
    try:
        if not sketch_processor:
            from sketch_processor import SketchProcessor
            sketch_processor = SketchProcessor()

        img_id = str(uuid.uuid4())
        ext = os.path.splitext(file.filename)[1].lower()
        if not ext or ext not in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]:
            ext = ".jpg"

        input_path = os.path.join(UPLOAD_DIR, f"{img_id}_orig{ext}")
        output_filename = f"{img_id}_sketch_{style}.jpg"
        output_path = os.path.join(PROCESSED_DIR, output_filename)

        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        if style == "ai_storyboard":
            res = sketch_processor.ai_redraw_storyboard(
                input_path=input_path,
                output_path=output_path,
                api_key=api_key,
                custom_instructions=custom_instructions,
                sketch_variant=sketch_variant
            )
        else:
            res = sketch_processor.convert_image(
                input_path=input_path,
                output_path=output_path,
                style=style,
                line_weight=line_weight,
                shading_intensity=shading,
                contrast=contrast,
                paper_texture=paper_texture
            )

        return {
            "status": "success",
            "image_id": img_id,
            "style": style,
            "original_url": f"/uploads/{os.path.basename(input_path)}",
            "sketch_url": f"/outputs/{output_filename}",
            "width": res["width"],
            "height": res["height"],
            "scene_analysis": res.get("scene_analysis"),
            "download_filename": f"storyboard_sketch_{style}_{file.filename}"
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.post("/sketch/smart_convert")
async def smart_convert_image_to_sketch(
    file: UploadFile = File(...),
    style: str = Form("pure_outline"),
    line_weight: float = Form(1.0),
    shading: float = Form(1.0),
    contrast: float = Form(1.2),
    paper_texture: bool = Form(True),
    api_key: Optional[str] = Form(None),
    custom_instructions: Optional[str] = Form(None)
):
    global sketch_processor
    try:
        # Fallback to server environment variable if frontend doesn't send an API Key
        final_api_key = api_key.strip() if api_key and api_key.strip() else os.environ.get("GEMINI_API_KEY", "")

        if not sketch_processor:
            from sketch_processor import SketchProcessor
            sketch_processor = SketchProcessor()

        img_id = str(uuid.uuid4())
        ext = os.path.splitext(file.filename)[1].lower()
        if not ext or ext not in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]:
            ext = ".jpg"

        input_path = os.path.join(UPLOAD_DIR, f"{img_id}_orig{ext}")
        output_filename = f"{img_id}_smart_{style}.jpg"
        output_path = os.path.join(PROCESSED_DIR, output_filename)

        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        res = sketch_processor.smart_convert(
            input_path=input_path,
            output_path=output_path,
            style=style,
            api_key=final_api_key,
            custom_instructions=custom_instructions,
            line_weight=line_weight,
            shading_intensity=shading,
            contrast=contrast,
            paper_texture=paper_texture
        )

        return {
            "status": "success",
            "image_id": img_id,
            "style": style,
            "engine": res.get("engine", "local"),
            "fallback_reason": res.get("fallback_reason"),
            "original_url": f"/uploads/{os.path.basename(input_path)}",
            "sketch_url": f"/outputs/{output_filename}",
            "width": res.get("width"),
            "height": res.get("height"),
            "scene_analysis": res.get("scene_analysis"),
            "download_filename": f"storyboard_{style}_{file.filename}"
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

class TextToMotionRequest(BaseModel):
    instruction: str
    character_id: int

@app.post("/api/text-to-motion")
async def text_to_motion(req: TextToMotionRequest):
    try:
        from google import genai
        import json
        
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return JSONResponse(status_code=500, content={"status": "error", "message": "GEMINI_API_KEY not set"})
            
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
You are an AI that converts natural language instructions into 3D motion keyframes for a character.
The character is at the origin facing positive Z axis by default.
User Instruction: "{req.instruction}"

Respond with ONLY a JSON object in the following format. Do not include markdown formatting or backticks.
{{
    "actions": [
        {{ "type": "move", "axis": "z", "amount": 2, "duration": 1000 }},
        {{ "type": "rotate", "axis": "y", "amount": 90, "duration": 500 }}
    ]
}}

"type" must be "move" or "rotate".
"axis" must be "x", "y", or "z".
"amount" is distance for move, degrees for rotate.
"duration" is in milliseconds.
"""
        response = client.models.generate_content(
            model='gemini-1.5-pro',
            contents=prompt
        )
        
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        
        try:
            motion_data = json.loads(text)
        except json.JSONDecodeError:
            print("Failed to parse JSON:", text)
            return JSONResponse(status_code=500, content={"status": "error", "message": "Failed to parse AI response as JSON"})
            
        return motion_data
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "AD-Depth Vision API is running. Visit /app for the UI."}

