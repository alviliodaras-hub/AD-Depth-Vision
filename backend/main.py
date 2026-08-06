from fastapi import FastAPI, File, UploadFile, BackgroundTasks, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import shutil
import os
import uuid

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

# Lazy loaded AI processors (Instant server startup!)
depth_processor = None
pose_processor = None
three_d_processor = None
playground_processor = None

processing_status = {}

@app.get("/colormaps")
async def get_colormaps():
    return {"colormaps": list(COLORMAP_OPTIONS.keys())}

@app.post("/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mode: str = Form("depth"),
    colormap: str = Form("grayscale")
):
    if not file.filename.endswith(('.mp4', '.avi', '.mov')):
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
        
    processing_status[video_id] = {"status": "processing", "progress": 0, "total": 0}
    
    background_tasks.add_task(process_video_task, video_id, input_path, output_path, mode, colormap)
    
    return {"video_id": video_id, "status": "processing"}

def process_video_task(video_id: str, input_path: str, output_path: str, mode: str = "depth", colormap: str = "grayscale"):
    global depth_processor, pose_processor, three_d_processor, playground_processor
    
    def update_progress(current, total, **kwargs):
        processing_status[video_id] = {
            "status": "processing",
            "progress": current,
            "total": total,
            "elapsed": round(kwargs.get("elapsed_seconds", 0), 1),
            "eta": round(kwargs.get("eta_seconds", 0), 1)
        }

    try:
        if mode == "pose":
            if not pose_processor:
                from pose_processor import PoseVideoProcessor
                pose_processor = PoseVideoProcessor()
            pose_processor.process_video(input_path, output_path, progress_callback=update_progress)
        elif mode == "3d_white":
            if not three_d_processor:
                from three_d_processor import ThreeDWhiteCharacterProcessor
                three_d_processor = ThreeDWhiteCharacterProcessor()
            three_d_processor.process_video(input_path, output_path, progress_callback=update_progress)
        elif mode == "playground":
            if not playground_processor:
                from playground_processor import PlaygroundProcessor
                playground_processor = PlaygroundProcessor()
            playground_processor.process_video(input_path, output_path, progress_callback=update_progress)
        else:
            if not depth_processor:
                from processor import DepthVideoProcessor
                depth_processor = DepthVideoProcessor()
            depth_processor.process_video(input_path, output_path, progress_callback=update_progress, colormap=colormap)
            
        processing_status[video_id] = {"status": "completed"}
    except Exception as e:
        print(f"Error processing video {video_id}: {e}")
        processing_status[video_id] = {"status": "error"}

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

@app.get("/scene/{video_id}")
async def get_scene(video_id: str):
    output_path = os.path.join(PROCESSED_DIR, f"{video_id}.json")
    if os.path.exists(output_path):
        return FileResponse(output_path, media_type="application/json")
    return JSONResponse(status_code=404, content={"message": "Scene data not found or not processed yet"})

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "AD-Depth Vision API is running. Visit /app for the UI."}
