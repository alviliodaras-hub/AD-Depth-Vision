# 🔮 AD-Depth Vision

An AI-powered video conversion suite built for macOS. Transform flat videos into 3D Depth Maps, Multi-Character Motion Pivots, or 3D White Clay Mannequin Renders locally on Apple Silicon (MPS / Metal) and CUDA GPUs.

![AD-Depth Vision](frontend/index.html)

## ✨ Features

- 🗺️ **3D Spatial Depth Maps**: Converts 2D videos to high-definition 720p depth maps using state-of-the-art **Depth Anything V2**. Supports 6 color palettes:
  - Grayscale
  - Turbo (Google Rainbow)
  - Magma
  - Inferno
  - Plasma
  - Viridis
- 🕺 **Character Motion Pivot**: Multi-character skeleton keypoint tracking (> 3 people) powered by **YOLOv8 Pose**.
- 🗿 **3D White Character**: Renders untextured 3D white clay mannequin figures with real-time 3D Phong surface normal shading and sharp cel-shaded contour outlines.
- ⚡ **Apple Silicon Accelerated**: Optimized for macOS using `MPS` PyTorch acceleration, batch processing, and edge-preserving bilateral filtering.
- 📦 **Portable Installer**: Bundles into a standalone `.app` package for macOS.

---

## 🚀 Quick Start (Local Run)

### Requirements
- macOS 11.0+ (Apple Silicon M1/M2/M3 recommended)
- Python 3.9+

### Installation & Execution

1. **Clone the repository**:
   ```bash
   git clone https://github.com/<your-username>/AD-Depth-Vision.git
   cd AD-Depth-Vision
   ```

2. **Build Portable App Bundle**:
   ```bash
   bash install_mac.sh
   ```

3. **Run Application**:
   Double-click `AD-Depth Vision.app` or run directly:
   ```bash
   cd backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   uvicorn main:app --reload --port 8000
   ```
   Open your browser at: `http://127.0.0.1:8000/app/`

---

## 🛠️ Technology Stack

- **Backend**: Python, FastAPI, PyTorch (MPS / CUDA), OpenCV, HuggingFace Transformers, Ultralytics YOLOv8
- **Frontend**: HTML5, Vanilla CSS (Glassmorphism & Neon Mesh UI), Modern JavaScript (ES6)

---

## 📄 License
MIT License
