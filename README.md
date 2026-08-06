# 🔮 AD-Depth Vision

An AI-powered video conversion suite built for macOS. Transform 2D videos into 3D Depth Maps, Multi-Character Motion Pivots, or 3D White Clay Mannequin Renders — running 100% locally on Apple Silicon (MPS Acceleration) and CUDA.

---

## ✨ Features Overview

| Feature | Description | Key Tech |
|---|---|---|
| 🗺️ **3D Spatial Depth Map** | Converts 2D videos to high-definition 720p depth maps. Includes 6 colormaps (**Grayscale, Turbo Rainbow, Magma, Inferno, Plasma, Viridis**) with dual-stage edge-preserving denoising. | Depth Anything V2 |
| 🕺 **Character Motion Pivot** | Multi-character skeleton keypoint tracking (**> 3 people in frame**) with real-time person counting & colored bone joints. | YOLOv8 Pose |
| 🗿 **3D White Character** | Converts video subjects into 3D untextured white clay mannequin figures with Phong 3D surface shading and sharp ink contour border outlines. | Depth Anything V2 + Sobel 3D Normals |

---

## 💻 Cara Install & Jalankan (macOS)

### Prasyarat
- macOS 11.0+ (Apple Silicon M1/M2/M3/M4 disarankan)
- Python 3.9+ (sudah terinstal di kebanyakan Mac)

### 🌟 Cara Tercepat: Download & Jalankan (1 Perintah)

Buka **Terminal** (⌘ + Space → ketik "Terminal") lalu paste perintah ini:

```bash
curl -L https://github.com/alviliodaras-hub/AD-Depth-Vision/archive/main.zip -o app.zip && unzip -qo app.zip && cd AD-Depth-Vision-main && bash run.sh
```

### 🛠️ Atau Jika Sudah Punya Foldernya

```bash
cd /path/ke/folder/AD-Depth-Vision
bash run.sh
```

### Apa yang terjadi saat menjalankan `bash run.sh`?

1. ✅ Cek Python 3 di komputer Anda
2. ⚙️ Buat virtual environment (hanya pertama kali)
3. 📦 Install semua package AI yang dibutuhkan (hanya pertama kali)
4. 🔍 Cari port yang tersedia (8000-8010)
5. 🚀 Nyalakan server AI
6. ❤️ Tunggu server siap (health-check)
7. 🌐 Buka browser otomatis → **Aplikasi siap digunakan!**

> **Tips**: Untuk menghentikan server, tekan `Ctrl+C` di Terminal.

---

## ⚡ Performa & Optimasi Mac

- **Apple Silicon Hardware Acceleration**: Menggunakan PyTorch `MPS` (Metal Performance Shaders) untuk inferensi AI berkecepatan tinggi di GPU Mac.
- **Dual-Stage Bilateral & Median Filtering**: Menghilangkan grain/bintik noise tanpa mengaburkan garis luar objek.
- **Multi-Batching (Batch Size 4)**: Pengambilan dan kalkulasi frame secara paralel untuk efisiensi maksimal.

---

## 📄 Lisensi
MIT License - Dibuat untuk komersial & personal.
