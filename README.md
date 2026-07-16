# Shale Shaker Cutting Estimation Dashboard

Dashboard web full-stack untuk monitoring/estimasi cutting shale shaker dari video
menggunakan semantic segmentation (**MobileViT** / **BiSeNet v2**), disajikan via
**ONNX Runtime** (CPU, FP32). Parameter ROI (4 sudut perspektif), pilihan model, dan
threshold dapat disesuaikan dari UI. Dirancang untuk resource terbatas
(target VPS **2 vCPU / 2 GB RAM**, CPU-only).

Terinspirasi paper SPE-194084-PA (klasifikasi volume cutting real-time via video),
namun memakai segmentasi sehingga bisa menghitung **% luas area cutting** dan
**jumlah stone** per frame.

## Tampilan (UI/UX)

Desain **terang, aksen oranye, minimalis & profesional** (production-ready):
- **Header bar oranye**: tombol collapse sidebar + breadcrumb (Cutting Monitoring › halaman),
  **jam server + jam lokal** (responsif, menyusut/turun pada layar kecil), dan **toggle tema (terang/gelap)**.
- **Sidebar terang** yang bisa diciutkan (Dashboard / Settings / Riwayat / Panduan), status aktif oranye.
- **Kartu putih** (rounded, shadow halus), **tombol oranye**, dan panel **"Last Value"** oranye
  yang menampilkan coverage% terkini — mengikuti guideline desain (`eye log.png`).
- **Live View (fit-viewport, tanpa scroll)**: seluruh informasi tampil dalam satu layar tanpa
  perlu menggulir — video + grafik tren di baris atas, info/metrik/kontrol + panel **Last Value**
  di baris bawah. Tampilan bersifat **frame-accurate**: video di-seek tepat ke frame yang
  **benar-benar dianalisis** dan mask digambar tanpa ekstrapolasi, sehingga frame & mask selalu
  cocok (gerakan bisa terlihat patah-patah, tapi faithful/real — tidak ada kesan mask tertinggal).
  Tersedia tombol **Preview Area Deteksi** (modal zoom ROI, sinkron frame) dan **grafik tren vertikal**.
- **Metrik mengikuti pemutaran video**: coverage%, jumlah stone, Playback/Detect FPS, dan grafik
  digerakkan oleh posisi pemutaran (playhead). Tombol **Jeda/Lanjut** (di kiri tombol Stop) menjeda
  video **sekaligus menghentikan deteksi di backend** (hemat CPU) — bukan sekadar membekukan tampilan.
  Saat video **di-pause atau selesai**, semua tampilan **berhenti otomatis (freeze)**. Tombol **Stop**
  menghentikan sesi (data dibuang) dan menonaktifkan Jeda/Stop.
- **Tampilan video bersih**: kontrol bawaan (volume, fullscreen, unduh, PiP) disembunyikan; deteksi
  selalu **dibatasi di dalam area ROI** (mask di-clip ke poligon ROI). Saat berpindah tab lalu kembali,
  video melanjutkan di posisi terakhir dan **tetap dalam keadaan jeda** bila tadi dijeda.
- **Editor ROI dengan zoom-preview**: saat menggeser titik sudut, muncul mini-preview ter-zoom 3×
  beserta koordinatnya agar batas geseran terlihat jelas.
- Mode gelap tersedia via toggle (disimpan di localStorage).

Sistem desain ada di `frontend/tailwind.config.ts` (palet `brand` oranye) + `frontend/app/globals.css`
(class `.card`, `.btn-primary/outline/danger/muted`, `.input`, `.badge`, `.last-value`).


## Arsitektur

```
Browser (Next.js static export)
   │  REST + WebSocket
   ▼
FastAPI (uvicorn, 1 worker)
   ├─ Inference core   : ONNX Runtime (FP32, CPU, intra_op = jumlah core)
   ├─ ROI warp         : OpenCV perspective transform (4 sudut → 224×640)
   ├─ Refine           : morfologi + Canny (opsional, toggle)
   ├─ Tracking         : Kalman (kecepatan per blob, tanpa ID) untuk motion-comp mask
   ├─ Background worker : decode (stride) → warp → infer → refine → metrics → blobs
   │                     → buffer di memori → (saat selesai) bulk insert DB + tulis CSV
   ├─ WebSocket         : /ws/sessions/{id} streaming blobs (mask) + metrik live
   ├─ Export            : CSV (otomatis) + PDF (reportlab: ringkasan + chart)
   └─ SQLite            : presets / sessions / measurements (time-series)
```

Konversi `.pt → .onnx` dilakukan **offline sekali** (folder `ml/`). FP32 ONNX
identik secara numerik dengan model PyTorch (tervalidasi, diff < 1e-4).

## Struktur

| Folder | Isi |
|--------|-----|
| `ml/` | Definisi model + skrip konversi/validasi/kuantisasi ONNX (butuh PyTorch, jalan lokal). |
| `backend/` | FastAPI + ONNX Runtime + SQLite. |
| `frontend/` | Next.js (static export) + Tailwind + recharts. |
| `data/source_videos/` | Video demo pre-loaded (di-bake ke Docker image, satu klik pakai di Dashboard). |
| `Dockerfile` | Multi-stage: build FE static + bake source videos → image backend. |
| `docker-compose.yml` | Orkestrasi + batas resource 2 vCPU / 1.8 GB. |

## Langkah 0 — Siapkan model ONNX (sekali)

Letakkan bobot `mobilevit_final.pt` & `bisenetv2_final.pt` di `ml/weights/`
(atau biarkan skrip mengambil dari folder Results training), lalu:

```bash
cd ml
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
python convert_to_onnx.py        # -> ml/onnx/{mobilevit,bisenetv2}.onnx + model_meta.json
python validate_parity.py        # cek "akurasi identik (no degradation)"
```

## Menjalankan — Development

Backend (terminal 1):
```bash
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend (terminal 2):
```bash
cd frontend
copy .env.local.example .env.local      # set NEXT_PUBLIC_API_BASE=http://localhost:8000
npm install
npm run dev                              # http://localhost:3000
```

## Menjalankan — Production lokal (tanpa Docker)

Build FE statis dan sajikan langsung dari backend:
```bash
cd frontend && npm run build             # menghasilkan frontend/out
# salin hasil build ke folder static backend:
xcopy /E /I /Y out ..\backend\app\static
cd ..\backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
# buka http://localhost:8000  (UI + API satu origin)
```

## Menjalankan — Docker / VPS (rekomendasi)

Prasyarat: Docker + Docker Compose v2, `ml/onnx/` sudah berisi model, dan domain
sudah diarahkan (DNS A record) ke IP VPS.

```bash
# 1. Install Docker (jika belum)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 2. Clone project ke VPS
git clone <repo-url> shale-shaker-dashboard
cd shale-shaker-dashboard

# 3. Setup environment
cp .env.example .env
# Edit .env → isi DOMAIN=domain-anda.com (wajib!)

# 4. Generate Caddyfile otomatis dari .env
bash setup.sh

# 5. Build & jalankan
docker compose up -d --build

# Aplikasi tersedia di https://domain-anda.com (HTTPS otomatis via Caddy + Let's Encrypt)
# Caddy otomatis renew sertifikat TLS setiap 90 hari (zero maintenance)
```

- App hanya listen di internal Docker network (`app:8000`). Port 80/443 diekspos
  oleh Caddy untuk reverse proxy + auto-HTTPS. Tidak ada port yang terbuka langsung
  ke aplikasi.
- Model di-*mount* read-only dari `./ml/onnx` ke `/models`; data (SQLite + upload)
  persisten di volume `app-data` (`/data`).
- Video sumber (demo) di-*bake* ke dalam image dari `data/source_videos/` — tidak perlu
  copy manual ke VPS.
- **Auto-cleanup**: setiap jam, video sesi >3 hari otomatis dihapus (konfigurasi via
  `CLEANUP_RETENTION_DAYS` di `.env`).
- Batas resource: `cpus: 2`, `mem_limit: 1800m` (sesuai VPS Starter 2 vCPU / 2 GB).

### Catatan VPS 2 GB
- Serving memakai ONNX Runtime (bukan PyTorch) agar muat di RAM kecil.
- Default model **MobileViT** (akurasi terbaik). Untuk kecepatan, pilih **BiSeNet v2**
  di menu **Settings** (lebih ringan & cepat di CPU).
- Naikkan **stride** (mis. 3–5) untuk near-real-time; objek cutting tidak berubah
  drastis antar-frame. Stride adalah pengungkit kecepatan paling efektif di CPU.

## Test

```bash
cd backend && pytest -q            # 36 tests
python scripts/smoke_test.py       # end-to-end dengan video nyata (butuh ml/onnx)
```

## Alur pemakaian

Workflow ada dalam **satu halaman Dashboard**:
1. **Pilih video** — unggah file video, atau klik **video sumber** (demo pre-loaded) yang
   tampil otomatis di bawah area upload. Frame pertama muncul sebagai acuan ROI.
2. **Tentukan ROI** — geser 4 titik (TL, TR, BR, BL) langsung di atas frame; saat menggeser muncul
   **mini-preview ter-zoom** untuk melihat batas posisi titik.
3. **Start Deteksi Live** — tampilan **fit-viewport tanpa scroll**: video diputar mulus + overlay mask
   diperbarui live; kartu **Last Value** menampilkan coverage% terkini, plus jumlah stone & FPS — semua
   **mengikuti pemutaran video** dan **berhenti otomatis saat video di-pause/selesai**. Tombol **Stop**
   (buang data), **Sesi baru**, dan **Preview Area Deteksi** (modal zoom ROI, frame real-time sinkron
   playhead). Saat video selesai, proses berhenti & tersimpan otomatis (DB + CSV); ada tombol **Putar ulang**.
4. **Settings** — model, threshold, stride (preset kecepatan), parameter grid coverage,
   toggle penghalusan tepi (Canny), **pratinjau interaktif** (grid/τ/threshold dengan coverage% live),
   **dua tombol setelan terbaik per model** (MobileViT & BiSeNet v2), dan info **"i"** pada tiap parameter.
5. **Riwayat** — daftar sesi (aksi **Hapus** via modal konfirmasi berstyle), ringkasan + **grafik tren
   gabungan** (Coverage % oranye + Stone Count biru, tooltip Frame/Coverage/Stone), unduh **CSV** &
   **PDF laporan profesional** (berlogo, tabel ringkasan + tren). Sesi yang sedang berjalan tidak dapat dihapus.
6. **Panduan** — **walkthrough bertahap** cara penggunaan (bisa dilewati kapan saja, langkah akhir
   langsung mulai ke Dashboard).

> Parameter yang diatur (ROI/model/threshold/stride/grid/refine) disimpan di `localStorage`
> dan tetap ada saat berpindah tab.
>
> Video sesi >3 hari otomatis dihapus dari disk (background task tiap jam); data sesi tetap
> tersimpan di database untuk keperluan audit/riwayat.

## Kuantisasi INT8 (opsional, eksperimen)

`ml/quantize_int8.py` menghasilkan model INT8 + laporan FP32 vs INT8
(`ml/onnx/int8/QUANT_REPORT.md`). Temuan pada perangkat keras uji: speedup CPU
hanya ~1.1–1.2× dan mask MobileViT menyimpang cukup jauh dari FP32 (IoU ~0.50),
sehingga **default tetap FP32** dan INT8 tidak diaktifkan pada serving.

## Keamanan

Aplikasi ini **tidak memiliki autentikasi** (akses dibatasi via URL internal sesuai
kebutuhan). Bila diekspos ke internet publik, tambahkan minimal **basic-auth / IP
allowlist** pada reverse proxy (mis. nginx/Caddy) di depan layanan ini, dan
pertimbangkan TLS (wss/https) agar WebSocket overlay terenkripsi.
