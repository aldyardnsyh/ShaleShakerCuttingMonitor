# Shale Shaker Cutting Estimation Dashboard

> Real-time cutting (rock cuttings) estimation on shale shakers using semantic segmentation.  
> Powered by MobileViT / BiSeNet v2 via ONNX Runtime on CPU.

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-success.svg)]()
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)]()
[![ONNX](https://img.shields.io/badge/ONNX-Runtime-orange.svg)]()
[![Docker](https://img.shields.io/badge/Docker-ready-blue.svg)]()

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Model Conversion](#1-model-conversion-offline)
  - [Development](#2-local-development)
  - [Docker Deployment](#3-docker-deployment-vps)
- [Usage Guide](#usage-guide)
- [API Documentation](#api-documentation)
- [Running Tests](#running-tests)
- [Project Structure](#project-structure)
- [License](#license)

---

## Overview

This web application monitors and estimates **cutting volume** on shale shakers from video input.  
Inspired by the methodology in **SPE-194084-PA** (real-time cutting volume classification via video), this project uses **semantic segmentation** instead of classification — enabling pixel-level measurement of cutting coverage and stone count.

The system is designed to run on resource-constrained hardware (target: **2 vCPU / 2 GB RAM VPS, CPU-only**) using ONNX Runtime instead of PyTorch.

---

## Features

- **Video-based Analysis** — Upload recorded video or use pre-loaded demo videos
- **Customizable ROI** — Define the detection area with 4 draggable perspective-corner points
- **Live Detection** — Frame-accurate overlay with motion-compensated masks
- **Grid Coverage Metric** — Quadrat-based percentage coverage (research-backed methodology)
- **Multiple Models** — MobileViT (accurate) or BiSeNet v2 (fast), switchable from UI
- **Historical Records** — Session history with interactive trend charts
- **Export** — CSV data export and professional PDF report generation
- **Auto-cleanup** — Old session videos automatically purged after configurable retention period
- **Dark Mode** — Light/dark theme toggle with persistence

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | **Next.js 14** (static export), **Tailwind CSS**, **Recharts** |
| Backend | **FastAPI**, **uvicorn** (1 worker), **SQLAlchemy** |
| ML Runtime | **ONNX Runtime** (CPU, FP32) |
| Computer Vision | **OpenCV** (headless) |
| Database | **SQLite** (via SQLAlchemy) |
| PDF | **ReportLab** |
| Container | **Docker** + **Caddy** (reverse proxy, auto HTTPS) |

---

## Architecture

```
Browser (Next.js static export)
   │  REST + WebSocket (same origin)
   ▼
FastAPI (uvicorn, 1 worker)
   ├─ Inference      : ONNX Runtime (FP32, CPU)
   ├─ ROI Warp       : OpenCV perspective transform (4 corners → 224×640)
   ├─ Refine         : Morphology + Canny (optional toggle)
   ├─ Tracking       : Kalman filter (velocity per blob, no ID)
   ├─ Worker         : decode → warp → infer → refine → metrics
   │                  → memory buffer → bulk DB insert + CSV at completion
   ├─ WebSocket      : /ws/sessions/{id} — real-time blob + metric stream
   ├─ Export         : CSV (auto) + PDF (reportlab)
   └─ SQLite         : presets / sessions / measurements
```

---

## Getting Started

### Prerequisites

- **Python 3.11+** (for model conversion and backend dev)
- **Node.js 20+** (for frontend dev)
- **Docker + Docker Compose v2** (for production deployment)
- Model weights: `mobilevit_final.pt` and/or `bisenetv2_final.pt`

### 1. Model Conversion (offline)

Run once to convert PyTorch weights to ONNX:

```bash
cd ml
python -m venv .venv && source .venv/bin/activate   # Linux
# or .\.venv\Scripts\activate                        # Windows

pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

python convert_to_onnx.py        # → ml/onnx/{mobilevit,bisenetv2}.onnx + model_meta.json
python validate_parity.py        # Verify PyTorch vs ONNX parity (< 1e-4 diff)
```

### 2. Local Development

**Backend:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend (separate terminal):**
```bash
cd frontend
cp .env.local.example .env.local   # Set NEXT_PUBLIC_API_BASE=http://localhost:8000
npm install
npm run dev                         # → http://localhost:3000
```

### 3. Docker Deployment (VPS)

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Clone & deploy
cd /opt
git clone https://github.com/aldyardnsyh/ShaleShakerCuttingMonitor.git
cd ShaleShakerCuttingMonitor

cp .env.example .env
# Edit .env — set DOMAIN=your-domain.com (required for HTTPS)

bash setup.sh                     # Generate Caddyfile
docker compose up -d --build       # Build & run
```

The app is now available at `https://your-domain.com` with automatic HTTPS via Caddy + Let's Encrypt.

---

## Usage Guide

| Step | Action | Description |
|------|--------|-------------|
| 1 | **Select Video** | Upload an MP4 file or click a pre-loaded demo video |
| 2 | **Set ROI** | Drag 4 corner points (TL, TR, BR, BL) to define the shale shaker surface |
| 3 | **Configure** | Adjust model, threshold, stride, grid parameters in Settings |
| 4 | **Start Detection** | Click "Start Deteksi Live" — real-time masks and metrics appear |
| 5 | **Review History** | Browse sessions with trend charts, export CSV/PDF reports |

Sessions older than 3 days are automatically cleaned up (configurable via `CLEANUP_RETENTION_DAYS`).

---

## API Documentation

### REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Server health + timezone |
| GET | `/api/models` | Available models + metadata |
| GET/POST | `/api/presets` | Configuration presets |
| POST | `/api/sessions` | Create analysis session |
| GET | `/api/sessions/{id}` | Session details + summary |
| POST | `/api/sessions/{id}/upload` | Upload video file |
| POST | `/api/sessions/{id}/stop` | Cancel running session |
| GET | `/api/sessions/{id}/measurements` | Time-series measurement data |
| GET | `/api/sessions/{id}/video` | Stream uploaded video |
| GET | `/api/sessions/{id}/tracks` | Per-frame blobs + velocity |
| GET | `/api/sessions/{id}/export.csv` | CSV download |
| GET | `/api/sessions/{id}/export.pdf` | PDF report download |
| DELETE | `/api/sessions/{id}` | Delete session + files |
| GET | `/api/source-videos` | List pre-loaded demo videos |
| POST | `/api/roi/analyze` | Preview rectified ROI + mask |

### WebSocket

**Path:** `ws://host/ws/sessions/{id}`

Streams per-frame detection payload:
```json
{
  "frame_idx": 42,
  "t": 1.68,
  "coverage_pct": 4.2,
  "stone_count": 7,
  "fps": 0.5,
  "blobs": [{ "poly": [[x1,y1],...], "vx": 0.3, "vy": 1.2 }]
}
```

Clients can send `{"action": "pause"}` / `{"action": "resume"}` to control processing.

---

## Running Tests

```bash
cd backend
pytest -q              # 36 tests
python scripts/smoke_test.py   # End-to-end with real video (requires ml/onnx)
```

---

## Project Structure

```
ShaleShakerCuttingMonitor/
├── ml/                  # Model definitions, ONNX conversion scripts
├── backend/             # FastAPI app (api/, core/, db/, workers/)
├── frontend/            # Next.js 14 app (app/, components/, lib/)
├── data/source_videos/  # Pre-loaded demo videos
├── Dockerfile           # Multi-stage build
├── docker-compose.yml   # Services (app + caddy reverse proxy)
├── Caddyfile            # Caddy reverse proxy config
└── setup.sh             # Generate Caddyfile from .env
```

---

## License

Internal use. Not licensed for commercial redistribution.
