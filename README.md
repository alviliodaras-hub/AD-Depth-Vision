# 🔮 AD-Depth Vision

An AI-powered video conversion suite built for macOS. Transform 2D videos into 3D Depth Maps, Multi-Character Motion Pivots, or 3D White Clay Mannequin Renders with crisp cel-shaded outlines — running 100% locally on Apple Silicon (MPS Acceleration) and CUDA.

---

## ✨ Features Overview

| Feature | Description | Key Tech |
|---|---|---|
| 🗺️ **3D Spatial Depth Map** | Converts 2D videos to high-definition 720p depth maps. Includes 6 colormaps (**Grayscale, Turbo Rainbow, Magma, Inferno, Plasma, Viridis**) with dual-stage edge-preserving denoising. | Depth Anything V2 |
| 🕺 **Character Motion Pivot** | Multi-character skeleton keypoint tracking (**> 3 people in frame**) with real-time person counting & colored bone joints. | YOLOv8 Pose |
| 🗿 **3D White Character** | Converts video subjects into 3D untextured white clay mannequin figures with Phong 3D surface shading and sharp ink contour border outlines. | Depth Anything V2 + Sobel 3D Normals |

---

## 💻 Cara Install & Menjalankan di macOS

### 🌟 Cara 1: Menggunakan Standalone App (`AD-Depth Vision.app`) — Tanpa Coding / Terminal

1. Unduh / ekstraksikan file **`AD-Depth-Vision-Mac.zip`** atau clone folder ini.
2. **Double-click** file **`AD-Depth Vision.app`**.
3. Aplikasi dan browser di `http://127.0.0.1:8000/app/` akan otomatis terbuka dan siap digunakan!

> 💡 **Tips macOS**: Jika muncul pesan *"App downloaded from internet"*, cukup **Klik Kanan `AD-Depth Vision.app` → pilih Open**.

---

### 🛠️ Cara 2: Build dari Source (Terminal / Developer Mode)

#### Prasyarat:
- macOS 11.0+ (Apple Silicon M1/M2/M3/M4 disarankan)
- Python 3.9+

#### Langkah-langkah:
1. **Clone repository**:
   ```bash
   git clone https://github.com/alviliodaras-hub/AD-Depth-Vision.git
   cd AD-Depth-Vision
   ```

2. **Buat Bundle `.app` Portabel (Otomatis)**:
   ```bash
   bash install_mac.sh
   ```

3. **Atau Jalankan Manual Backend & Frontend**:
   ```bash
   cd backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   uvicorn main:app --reload --port 8000
   ```
   Buka browser di: **[http://127.0.0.1:8000/app/](http://127.0.0.1:8000/app/)**

---

## ⚡ Performa & Optimasi Mac

- **Apple Silicon Hardware Acceleration**: Menggunakan PyTorch `MPS` (Metal Performance Shaders) untuk inferensi AI berkecepatan tinggi di GPU Mac.
- **Dual-Stage Bilateral & Median Filtering**: Menghilangkan grain/bintik noise tanpa mengaburkan garis luar objek.
- **Multi-Batching (Batch Size 4)**: Pengambilan dan kalkulasi frame secara paralel untuk efisiensi maksimal.

---

## 📄 Lisensi
MIT License - Dibuat untuk komersial & personal.
