# HANDOFF — Shale Shaker Cutting Estimation Dashboard

> Dokumen pegangan untuk **melanjutkan pengembangan** (oleh manusia atau agent AI lain).
> Berisi tujuan, keputusan terkunci, arsitektur, detail tiap modul, riwayat iterasi
> kronologis, status terkini, keterbatasan, dan langkah lanjutan.
> **Lokasi proyek:** `D:\Kuliah\Tugas Akhir\shale-shaker-dashboard`
> **Terakhir diperbarui:** 2026-07-16 (Auto-cleanup 3 hari + fitur video sumber + hapus emoji + hapus Well Site dari PDF).

---

## 1. Ringkasan & Tujuan

Aplikasi web full-stack untuk **monitoring/estimasi cutting (serpihan batuan) pada shale shaker**
dari video, memakai **semantic segmentation** (MobileViT / BiSeNet v2) yang disajikan via
**ONNX Runtime (CPU, FP32)**. Parameter utama (ROI 4-titik, model, threshold, dll.) dapat
disesuaikan user. Target jalan di **VPS hemat (2 vCPU / 2 GB RAM, CPU-only)** via Docker.

Acuan ilmiah: paper **SPE-194084-PA** (klasifikasi volume cutting real-time via video). Bedanya,
proyek ini memakai segmentasi sehingga bisa menghitung **% area tertutup cutting** dan jumlah blob.

Sumber model & dataset (di luar repo): `D:\Kuliah\Tugas Akhir\Dataset\Training Model Baru\Results\models\`
(`mobilevit_final.pt` 32MB, `bisenetv2_final.pt` 13.5MB). Video uji:
`D:\Kuliah\Tugas Akhir\Dataset\Kode Uji Coba Test Video\dataset_asli_pdu_2.mp4`.
Notebook training: `…\Training Model Baru\training-model-baru-tugas-akhir-v4.ipynb` (arsitektur cell 15-17, ROI cell 10, preprocessing cell 12).

---

## 2. Keputusan Terkunci (hasil diskusi dengan user)

- **Deployment hybrid**: lokal / on-prem / cloud (VPS Tencent Starter 2vCPU/2GB). Portabel via Docker.
- **Input (base)**: upload file video (live RTSP menyusul; arsitektur disiapkan).
- **User**: tim engineer internal, **tanpa auth** (akses via URL internal). Bila publik → tambah basic-auth/IP allowlist + TLS di reverse proxy.
- **Serving ML**: **ONNX Runtime FP32** (bukan PyTorch — PyTorch ~1GB tak muat di 2GB). FP32 identik numerik dengan PyTorch (paritas terbukti diff ~3e-5).
- **INT8**: diuji (Task 11 awal) → **TIDAK dipakai**. Speedup CPU kecil (1.1–1.2×) & MobileViT menyimpang (mask IoU ~0.5 vs FP32). Default tetap FP32. Laporan: `ml/onnx/int8/QUANT_REPORT.md`.
- **Output utama**: **% coverage grid-kuadrat** (lihat §5) + jumlah stone + FPS + latency.
- **Database**: SQLite (cukup untuk skala 1 stream).
- **Frontend**: Next.js **static export** (`output: 'export'`) — tanpa Node SSR di VPS. Disajikan oleh FastAPI.
- **Menu**: kini **4** — **Dashboard, Settings, Riwayat, Panduan** (semula 3; halaman **Panduan** ditambah pada iterasi 11 atas permintaan user).
- **Alur Dashboard**: satu halaman — upload → preview frame awal → gambar ROI → **Start (live)** → Stop. State persist antar-tab.
- **Overlay**: **mask saja, tanpa ID/label** (bersih).
- **Mode**: deteksi **live** (bukan proses-dulu-baru-lihat), dengan sinkronisasi agar mask tidak delay.

---

## 3. Arsitektur

```
Browser (Next.js static export, Tailwind, recharts)
   │  REST + WebSocket (same origin)
   ▼
FastAPI (uvicorn, 1 worker)
   ├─ Inference core  : ONNX Runtime (FP32, CPU, intra_op threads configurable)
   ├─ ROI warp        : OpenCV perspective transform (4 sudut → 224×640)
   ├─ Refine          : morfologi + Canny (opsional)
   ├─ Tracking        : Kalman (SORT-style) → kecepatan per blob (tanpa ID)
   ├─ Worker          : decode (stride) → warp → infer → refine → metrics → blobs
   │                    → BUFFER di memori → (saat selesai) bulk insert DB + tulis CSV
   ├─ WebSocket       : /ws/sessions/{id} streaming blobs+metrik live
   └─ SQLite          : presets / sessions / measurements
```

Konversi `.pt → .onnx` dilakukan **offline sekali** (folder `ml/`, butuh PyTorch).

**Alur live**: Start → buat session + upload video → frontend memutar **video lokal (objectURL) langsung**
(mulus, native) + buka WebSocket. Backend memproses; tiap deteksi mengirim `blobs` (poligon mask + kecepatan Kalman) + metrik.
Frontend menggambar mask di atas video, **disinkronkan ke waktu** (playbackRate mengikuti garis depan deteksi),
dengan **motion-compensation** Kalman antar-deteksi. Saat selesai → bulk simpan DB + CSV otomatis.
**Stop / WS putus** → pembatalan kooperatif, **buffer dibuang** (tidak tersimpan).

---

## 4. Struktur Folder (file penting)

```
shale-shaker-dashboard/
├── Dockerfile                  # multi-stage: build FE static -> bake ke image backend + source videos
├── docker-compose.yml          # service `app`, mem_limit 1800m, cpus 2, volume ml/onnx:ro + app-data
├── .env / .env.example         # APP_TIMEZONE, ORT_INTRA_OP_THREADS, DEFAULT_*, GRID_*, REFINE_EDGES, CLEANUP_RETENTION_DAYS
├── README.md                   # panduan run/deploy
├── HANDOFF.md                  # (dokumen ini)
├── data/
│   └── source_videos/          # video demo pre-loaded (.mp4); di-bake ke Docker image via COPY
├── ml/                         # offline (butuh PyTorch) — TIDAK dipakai backend runtime
│   ├── model_defs.py           # MobileViTUNet + BiSeNetV2 + build_model (salinan notebook)
│   ├── convert_to_onnx.py      # .pt -> .onnx FP32 + tulis model_meta.json
│   ├── validate_parity.py      # cek paritas PyTorch vs ONNX (<1e-3)
│   ├── quantize_int8.py         # eksperimen INT8 (opsional; tidak dipakai)
│   ├── weights/                # *.pt (gitignored)
│   └── onnx/                   # mobilevit.onnx, bisenetv2.onnx, model_meta.json, int8/
├── backend/
│   ├── requirements.txt        # fastapi, uvicorn, onnxruntime, opencv-headless, numpy, sqlalchemy, pydantic, Pillow, python-multipart, reportlab (PDF). NO torch. + onnx (quantize, opsional)
│   ├── Dockerfile              # image backend standalone (root Dockerfile dipakai compose)
│   ├── .venv/                  # virtualenv dev (sudah berisi semua dep + onnx)
│   ├── scripts/smoke_test.py   # smoke end-to-end via TestClient
│   ├── tests/                  # pytest (36 test) — conftest set DATA_DIR+DATABASE_URL temp
│   └── app/
│       ├── main.py             # create_app, CORS, lifespan(init_db + cleanup loop), mount static, register router
│       ├── config.py           # Settings (env-driven) — lihat §8
│       ├── api/
│       │   ├── routes_health.py        # GET /api/health (status + server_time + tz)
│       │   ├── routes_models.py        # GET /api/models (baca model_meta.json / default)
│       │   ├── routes_presets.py       # CRUD /api/presets
│       │   ├── routes_sessions.py      # sessions, upload, process, stop, measurements, video, tracks, export.csv, export.pdf, DELETE
│       │   ├── routes_source_videos.py # GET /api/source-videos + /download/{name} (video demo pre-loaded)
│       │   ├── routes_predict.py       # POST /api/predict-image (uji 1 gambar)
│       │   └── ws_stream.py            # WS /ws/sessions/{id} (cancel saat disconnect)
│       ├── core/
│       │   ├── inference.py    # InferenceManager (ONNX session, preprocess, predict)
│       │   ├── roi.py          # warp_to_roi / warp_mask_to_full / get_transforms / roi_bbox
│       │   ├── metrics.py      # fg_area, count_stones, grid_coverage, compute_metrics, mask_to_polygons, mask_to_blobs
│       │   ├── refine.py       # refine_mask (morfologi + Canny)
│       │   ├── tracking.py     # MultiObjectTracker (Kalman) -> kecepatan per-deteksi; mask_to_boxes
│       │   ├── report.py       # build_session_pdf (reportlab: ringkasan + LinePlot coverage/stone) — TANPA Well Site
│       │   └── video.py        # get_video_info, iter_frames, draw_overlay, encode_jpeg_b64
│       ├── workers/processor.py# process_session(...) — pipeline + cancel + buffer + persist+CSV (session_csv_path)
│       └── db/
│           ├── database.py     # engine sqlite, SessionLocal, get_db, init_db + _migrate_add_columns
│           ├── models.py       # Preset, Session, Measurement
│           ├── schemas.py      # Pydantic v2
│           └── crud.py         # preset/session CRUD (+delete_session) + bulk insert + summary
└── frontend/                   # Next.js 14 (app router), output:'export', Tailwind, recharts
    ├── next.config.js          # output:'export', trailingSlash:true, images.unoptimized
    ├── tailwind.config.ts      # darkMode:'class' + palet `brand` (oranye #F47A20)
    ├── app/
    │   ├── globals.css         # tema terang + class .card/.btn-*/.input/.badge/.last-value (+ varian .dark)
    │   ├── layout.tsx          # <DashboardProvider> + <AppShell>
    │   ├── page.tsx            # Dashboard (useDashboard): setup / live (kamera + Last Value + trend)
    │   ├── settings/page.tsx   # model/threshold/stride + grid + refine + detection-speed + preview ROI (scroll: h-full overflow-y-auto)
    │   ├── history/page.tsx    # SessionTable(aksi Hapus via ConfirmModal) + ringkasan + chart + Download CSV & PDF (scroll)
    │   └── panduan/page.tsx    # NEW: panduan penggunaan (langkah, istilah, tips, FAQ accordion)
    ├── components/
    │   ├── AppShell.tsx        # header oranye (toggle sidebar + breadcrumb + clock + theme) + sidebar + main (overflow-hidden; tiap page atur scroll sendiri)
    │   ├── Sidebar.tsx         # sidebar terang collapsible (prop `collapsed`), aktif oranye — 4 menu (+ Panduan)
    │   ├── Breadcrumb.tsx      # breadcrumb dari pathname; "Cutting Monitoring" = Next Link ke "/" (soft nav)
    │   ├── ThemeToggle.tsx     # toggle terang/gelap (localStorage 'shaker.theme', class `dark` di <html>)
    │   ├── Clock.tsx           # jam server (offset /api/health) + jam lokal — gaya header, responsif
    │   ├── DashboardContext.tsx# state workflow live (file/objUrl/frame/roi/phase/liveFrames/stats{+playing}/...) — di layout; start()/reset() reset stats
    │   ├── TrackedView.tsx     # <video> object-contain (onEnded, initialTime seek=resume) + canvas overlay letterbox-aware; stats playhead-driven (freeze saat pause/ended)
    │   ├── DetectionPreviewModal.tsx # modal zoom ROI crop, video seek ke playhead utama (frame real-time), backdrop blur, closable
    │   ├── RoiEditor.tsx       # 4 titik draggable; saat drag muncul zoom-preview 2D (background-position) + crosshair
    │   ├── ControlsPanel.tsx   # select model, slider threshold, input stride (class .input)
    │   ├── TrendChart.tsx      # LineChart VERTIKAL (height number|string, dukung "100%") + CustomTooltip
    │   ├── ConfirmModal.tsx    # NEW: modal konfirmasi berstyle (danger/busy, ESC) — pengganti window.confirm/alert
    │   └── SessionTable.tsx    # tabel terang + badge status + aksi tombol Hapus (onDelete)
    │   # (AreaGauge/StoneCountCard/FpsChart/LiveView DIHAPUS — digantikan StatChip inline + Last Value panel + TrackedView)
    └── lib/
        ├── api.ts              # REST client + tipe (SessionOut, TrackFrame{+ts}, Blob, dst.) + exportCsvUrl/exportPdfUrl/deleteSession
        ├── ws.ts               # wsUrl(), FramePayload (blobs)
        ├── config.ts           # ActiveConfig (localStorage) + DEFAULT_ROI + setLastFrame/getLastFrame
        └── frame.ts            # extractFirstFrame(file), dataUrlToFile()
```

---

## 5. Rumus % Coverage (grid-kuadrat) — berbasis riset

ROI 4-titik di-**rektifikasi** (perspective warp) → persegi **640×224 px** (menormalkan jarak & sudut kamera).
Dibagi grid sel `c` px (≈ rata-rata footprint batuan). Sel "terisi" bila fraksi piksel batuan ≥ `τ`.

```
coverage% = (jumlah sel terisi / total sel) × 100
n_cols = ⌊640/c⌋ , n_rows = ⌊224/c⌋ , min_px = max(1, τ·c·c)
```

Default: `c = GRID_CELL_PX = 16`, `τ = GRID_OCC_FRACTION = 0.05`. Dapat diatur di Settings (per-sesi).
Dasar ilmiah: **metode grid-kuadrat / point-intercept untuk percent cover** (ekologi/vegetation
monitoring — rangelandsgateway; PMC8564103). Metrik `fg_area_pct` (persen piksel mentah) tetap disimpan sebagai pembanding.
Contoh nyata: coverage ~5% jauh lebih intuitif sebagai "penutupan permukaan" dibanding piksel mentah ~0.8%.

---

## 6. Model & Inferensi

- Input model **224×640 (HxW)**, NUM_CLASSES=2, MEAN=(0.485,0.456,0.406) STD=(0.229,0.224,0.225).
- ROI default (TL,TR,BR,BL): `[[760,650],[1300,614],[1315,795],[780,845]]`.
- Threshold default: **MobileViT 0.65**, **BiSeNet v2 0.50** (dari `model_meta.json`).
- Latency CPU (intra_op=2): MobileViT ~390 ms/frame, BiSeNet v2 ~190 ms/frame. → BiSeNet v2 = opsi cepat, MobileViT = opsi akurat.
- ONNX I/O: input name `input`, output name `logits`. `get_manager()` = singleton InferenceManager.
- `model_meta.json`: `{mean, std, default_model, models:{name:{onnx_file,num_classes,input_h,input_w,fg_threshold,roi_src}}}`.

---

## 7. Skema Database (SQLite)

- **presets**: id, name(unik), roi_json, model, threshold, stride, created_at.
- **sessions**: id, name, source_type, model, threshold, roi_json, stride, status(created/running/done/cancelled/error),
  started_at, ended_at, created_at, video_fps, frame_width, frame_height, grid_cell_px, grid_occ_fraction, refine_edges.
- **measurements**: id, session_id(fk,idx), ts, frame_idx, fg_px, roi_px, fg_area_pct, stone_count, fps, infer_ms, model,
  tracks_json (berisi **blobs** = list `{poly,vx,vy}`), coverage_pct.

> **Migrasi**: `init_db()` memanggil `_migrate_add_columns()` yang menambah kolom baru via `ALTER TABLE` bila belum ada
> (SQLite, idempotent). Penting karena `create_all` tak meng-ALTER tabel lama (volume Docker `app-data` persisten).

---

## 8. Konfigurasi (env / `app/config.py`)

| Env | Default | Fungsi |
|-----|---------|--------|
| APP_TIMEZONE | Asia/Jakarta | stempel waktu server |
| ORT_INTRA_OP_THREADS | min(cpu,4) | thread ONNX (VPS set 2) |
| ORT_INTER_OP_THREADS | 1 | |
| DEFAULT_MODEL | mobilevit | |
| DEFAULT_STRIDE | 3 | proses tiap N frame |
| MIN_STONE_AREA | 8 | area min CC (ROI) |
| TRACK_MIN_AREA | 30 | area min blob (full-frame) |
| TRACK_MAX_AGE/MIN_HITS/IOU | 15/2/0.1 | parameter Kalman tracker |
| TRACK_DIST_GATE | 90 | gate jarak centroid (px) untuk asosiasi fallback non-overlap |
| GRID_CELL_PX | 16 | ukuran sel grid coverage |
| GRID_OCC_FRACTION | 0.05 | ambang okupansi sel (τ) |
| REFINE_EDGES | true | morfologi+Canny default |
| MODELS_DIR / DATA_DIR / STATIC_DIR / SOURCE_VIDEOS_DIR / DATABASE_URL | — | path |
| CLEANUP_RETENTION_DAYS | 3 | auto-hapus video sesi > N hari |

---

## 9. Endpoint API

- `GET /api/health` — status + server_time + timezone.
- `GET /api/models` — daftar model + metadata.
- `CRUD /api/presets`.
- `POST /api/sessions` — buat session (model, threshold, roi_json, stride, grid_cell_px, grid_occ_fraction, refine_edges).
- `GET /api/sessions` , `GET /api/sessions/{id}` (+summary).
- `POST /api/sessions/{id}/upload` — multipart `file` → `data/uploads/session_{id}.mp4`.
- `POST /api/sessions/{id}/process?max_frames=N` — proses sinkron (run_in_threadpool); dipakai test/batch.
- `POST /api/sessions/{id}/stop` — minta pembatalan (buang data).
- `GET /api/sessions/{id}/measurements` — time-series (setelah selesai).
- `GET /api/sessions/{id}/video` — FileResponse (mendukung HTTP Range untuk `<video>`).
- `GET /api/sessions/{id}/tracks` — `{fps,width,height,stride,roi,frames:[{frame_idx,t,coverage_pct,fg_area_pct,stone_count,blobs:[{poly,vx,vy}]}]}`.
- `GET /api/sessions/{id}/export.csv` — sajikan CSV tersimpan (atau generate dari DB).
- `GET /api/sessions/{id}/export.pdf` — laporan PDF (reportlab): ringkasan + chart coverage/stone.
- `DELETE /api/sessions/{id}` — hapus sesi + measurements + file video & CSV (204). **Menolak (409) bila `status=="running"`** (sesi aktif/di-jeda harus di-Stop dulu).
- `WS /ws/sessions/{id}?max_frames=N` — streaming payload per frame:
  `{frame_idx,t,server_time,fg_area_pct,coverage_pct,grid_cols,grid_rows,stone_count,fps,infer_ms,blobs}`,
  diakhiri `{done:true, ...summary}`. **Disconnect → cancel + buang data.** Klien dapat mengirim `{"action":"pause"}` / `{"action":"resume"}` untuk **menjeda/melanjutkan deteksi** (worker memblok di pause-gate, CPU idle).
- `GET /api/source-videos` — daftar video sumber (demo) yang tersedia (`{videos: [{name, path, size_bytes, size_mb}]}`).
- `GET /api/source-videos/{name}/download` — unduh video sumber (FileResponse dengan Accept-Ranges).

---

## 10. Detail Pipeline (`workers/processor.py`)

`process_session(session_id, emit=None, max_frames=None, include_overlay=False)`:
1. Ambil session, video; baca `video_fps/width/height` → simpan ke session; status `running`.
2. Tracker Kalman; `use_refine = session.refine_edges`; `vel_scale = fps/stride` (px/step → px/sec).
3. Loop frame (stride): cek `cancel_ev`; warp ROI → `predict` → (opsional) `refine_mask` →
   `compute_metrics` (coverage grid + fg_area + stone_count) → `warp_mask_to_full` →
   `mask_to_blobs` (poly+bbox) → `tracker.update(boxes)` → kecepatan per blob →
   `blobs=[{poly,vx,vy}]` → **append ke buffer memori** → `emit(...)` (live).
4. **Cancel** → `delete_measurements` (tak perlu, buffer dibuang), status `cancelled`, return.
5. **Selesai** → `delete_measurements` (idempotent) → `add_measurements_bulk(buffer)` (1 commit) →
   `write_session_csv` (otomatis ke `data/exports/session_{id}.csv`) → status `done`.

**Caching/efisiensi**: tidak ada commit DB per-frame; persistensi sekali di akhir → loop fokus inferensi.

---

## 11. Frontend — perilaku kunci

- **State persist antar-tab**: `DashboardProvider` di `layout.tsx` (mounted sekali). Menyimpan file/objUrl/frame/roi/name/phase/liveFrames/stats. WebSocket hidup di provider → tetap menerima walau pindah tab.
- **TrackedView**: `<video>` native (autoPlay, loop, muted) + `<canvas>` overlay.
  - Gambar **mask** = poligon merah transparan (tanpa ID), motion-compensated: `poly[i] + (vx,vy)*(t - det.t)` (cap `MAX_EXTRAP=0.6s`).
  - **Sync playbackRate** (default ON): `rate = clamp(gap/0.5, 0.1, 1.0)` agar playhead menempel di belakang garis depan deteksi → mask tidak delay. (`sync` adalah prop; saat ini hardcoded true — lihat §13).
- **ActiveConfig** disimpan di `localStorage` (`shaker.activeConfig`); frame awal disimpan (`shaker.lastFrame`, full-res JPEG dataURL) untuk preview ROI di Settings.
- **frame.ts**: ekstraksi frame awal video di browser (offscreen `<video>`+canvas) → bukti upload + ukuran natural untuk koordinat ROI.
- **Design system (tema terang/oranye, production-ready)**: `AppShell` = header oranye (toggle sidebar + `Breadcrumb` + `Clock` + bell + `ThemeToggle`) + `Sidebar` terang collapsible + main. Palet `brand` (#F47A20) di `tailwind.config.ts` (`darkMode:'class'`); class reusable di `globals.css` (`.card`, `.btn-primary/outline/danger/muted`, `.input`, `.badge`, `.last-value`). Dashboard live mengikuti guideline `eye log.png`: panel kamera + kartu info (tombol Stop/Sesi baru/Download) + **panel "Last Value" oranye** (coverage%) + grafik tren oranye. Toggle gelap menyimpan ke `localStorage` `shaker.theme`.

---

## 12. Cara Menjalankan & Menguji

**Konversi ONNX (sekali, butuh PyTorch):**
```
cd ml ; python -m venv .venv ; .venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cpu ; pip install -r requirements.txt
python convert_to_onnx.py ; python validate_parity.py
```

**Backend dev:** `cd backend ; .venv\Scripts\activate ; uvicorn app.main:app --reload --port 8000`
**Frontend dev:** `cd frontend ; npm install ; npm run dev` (set `.env.local` NEXT_PUBLIC_API_BASE=http://localhost:8000)
**Test backend:** `cd backend ; .\.venv\Scripts\python.exe -m pytest -q`  → **35 passed**
**Smoke e2e:** `backend\.venv\Scripts\python.exe scripts\smoke_test.py`
**Docker (produksi):** `docker compose up -d --build` → http://localhost:8000 (UI+API satu origin)

Catatan: tes pakai DB+DATA_DIR temporer (di `conftest.py`, di-set sebelum import app).
PowerShell: upload multipart pakai `curl.exe -F` (Invoke-RestMethod 5.x tak punya `-Form`).

---

## 13. Status Terkini & Keterbatasan / Open Items

**Selesai & tervalidasi (Docker + 36 test):**
- Pipeline penuh: upload → ROI → live detect → overlay mask → metrik → simpan DB+CSV di akhir.
- Coverage grid-kuadrat; refine (morfologi+Canny); Kalman motion-comp (tanpa ID); sync playback; stop/cancel; persistensi buffer; migrasi DB; 3 menu; state persist antar-tab.
- **Auto-cleanup**: background task di lifespan hapus video sesi >3 hari (default) + file yatim piatu tiap jam.
- **Video sumber**: Dashboard menampilkan video demo pre-loaded dari `data/source_videos/` (di-bake ke Docker image). Klik langsung pakai tanpa upload manual.
- **PDF**: tanpa referensi Well Site (data rahasia dihapus).
- **UI**: tanpa emoticon/emoji di seluruh halaman (produksi, standar industri).
- **UI production-ready** (tema terang/oranye, header bar + breadcrumb + jam + toggle tema, panel Last Value, grafik oranye) — sesuai guideline `eye log.png`.
- **Dashboard live fit-viewport (tanpa scroll)**: video + tren di baris atas, info+kontrol + Last Value di baris bawah; semua tombol selalu terlihat.
- **Metrik live berbasis playhead** (coverage/stone/FPS/grafik dari posisi pemutaran video) → **berhenti otomatis (freeze)** saat video di-pause atau selesai. Mask overlay letterbox-aware (presisi walau video object-contain).
- **ROI drag** menampilkan mini-preview ter-zoom 3× + koordinat. **Preview Area Deteksi** sinkron ke playhead utama (frame real-time, bukan loop independen).

**Keterbatasan / hal yang BISA jadi langkah lanjutan:**
1. **Kalman velocity pada stride besar — DIPERBAIKI (iterasi 11).** Kini ada **gate jarak centroid** sebagai fallback IoU (`TRACK_DIST_GATE`), sehingga batuan kecil/cepat yang tidak overlap antar-deteksi tetap ter-asосiasi dan velocity-nya tertangkap. Untuk gerakan ekstrem, stride kecil (1–3) tetap paling akurat.
2. **Sync = video melambat.** Dengan `sync` ON, video diputar pada laju deteksi (playbackRate<1, tetap mulus) agar mask selaras. Belum ada toggle UI untuk mematikan sync (prop `sync` di `TrackedView` masih hardcoded `true`). **Saran**: jadikan toggle di Settings (real-time penuh vs sinkron).
3. **Grafik & metrik tampil mengikuti playhead** (frame `t<=waktu pemutaran`). Untuk video panjang, deteksi WS tetap berjalan di latar (buffer memori); pertimbangkan **flush berkala** (mis. tiap 500 frame). Catatan: saat video di-pause, deteksi backend secara teknis masih berproses; yang dihentikan adalah TAMPILAN (sesuai permintaan). Bila ingin benar-benar menjeda komputasi backend, perlu dukungan pause di worker.
4. **Live = re-proses dari awal** tiap Start (tidak menyimpan video overlay). Riwayat hanya memutar ulang video + metrik tersimpan.
5. **INT8 tidak dipakai** (lihat §2). File ada di `ml/onnx/int8/` bila ingin dieksplor lagi.
6. **Keamanan**: tanpa auth. Tambahkan reverse-proxy auth/TLS bila publik.
7. **Akurasi model**: FG IoU model memang rendah (MobileViT 0.30, BiSeNet 0.26) karena dataset training kecil — itu ranah training (notebook), bukan app. App hanya menyajikan.

---

## 14. Riwayat Iterasi (kronologis)

1. **Diskusi requirement** → keputusan terkunci (§2).
2. **Build awal (12 task)**: scaffold, konversi ONNX+paritas, inference core, ROI, DB+presets, upload+worker, WebSocket, dashboard FE, ROI editor, history, INT8 (ditolak), Docker+deploy. Tervalidasi di Docker (mem ~90–180 MB).
3. **Perf/Kalman v1**: keluhan FPS patah-patah → tambah Kalman tracking + endpoint video + replay; overlay box ber-ID.
4. **Tombol Stop & cancel**: pembatalan kooperatif + buang data + cancel saat WS disconnect (fix "proses jalan terus di Docker").
5. **Coverage grid-kuadrat + UI restruktur**: rumus coverage (riset), 3 menu, single-page dashboard (upload→preview→ROI→start/stop), preview ROI di Settings, coverage di Riwayat.
6. **Rework live + mask-only**: state persist antar-tab (Context di layout); mode **live** (video langsung main + overlay live, bukan proses-dulu); overlay **mask polygon tanpa ID**; performa (ORT threads = cpu, preset kecepatan deteksi).
7. **Caching/efisiensi penyimpanan**: hasil di-buffer di memori; **bulk insert DB + CSV otomatis saat selesai**; stop = tak tersimpan.
8. **Fix "mask delay/fake"**: **Kalman motion-compensation** mask (kecepatan per blob, tanpa ID) + **sinkronisasi playbackRate ke garis depan deteksi**; **Canny+morfologi edge refinement** (toggle Settings, default ON). Payload `/tracks` & WS memakai `blobs:[{poly,vx,vy}]`.
9. **Refactor UI/UX → production-ready (TERAKHIR)**: tema **terang + aksen oranye** sesuai guideline `eye log.png`. Header bar oranye (collapse sidebar + breadcrumb + jam server/lokal + bell + toggle tema terang/gelap), sidebar terang collapsible, kartu putih, tombol oranye, panel **"Last Value"** oranye (coverage%), grafik tren oranye. Komponen lama AreaGauge/StoneCountCard/FpsChart/LiveView dihapus (diganti StatChip inline + Last Value + TrackedView). Sistem desain: `tailwind.config.ts` (palet `brand`) + `globals.css` (class reusable). Build OK, Docker rebuilt, UI tersaji (200).
10. **Fit-viewport + sinkron playhead + fix "state tak berhenti" (TERBARU)**:
    - **Layout no-scroll**: Dashboard live kini **full-viewport tanpa scroll** — `globals.css` (`html,body{height:100%}`), `AppShell main` (`flex-1 overflow-hidden`, padding dipindah ke halaman), `page.tsx` live = kolom flex `h-full`: **baris atas** (`flex-1 min-h-0`) berisi video (2/3) + tren (1/3); **baris bawah** (`flex-shrink-0`) berisi info+stat+tombol (2/3) + panel Last Value (1/3). Semua kontrol (Stop/Sesi baru/Preview) selalu terlihat.
    - **Video object-contain + canvas align**: `TrackedView` video kini `h-full object-contain` (mengisi tinggi kpartu). Overlay mask dihitung dengan **letterbox-aware rect** (offX/offY + skala rW/rH) agar tetap presisi walau ada bilah hitam.
    - **Fix bug "state jalan terus"**: SEMUA metrik live (coverage, stone, Playback FPS, Detect FPS, grafik) kini **digerakkan oleh PLAYHEAD video** (`d.stats` dari `TrackedView`), bukan stream WS mentah. Saat video **pause/selesai** (`video.paused||video.ended` → `playing=false`): mask & stats **freeze** (currentTime konstan), Playback FPS=0, Detect FPS dibekukan ke nilai terakhir, dan **grafik difilter `f.t<=playhead`** sehingga ikut berhenti. Sebelumnya metrik ikut `progress`/`liveFrames` (WS) yang terus tumbuh walau video berhenti. Emit `onStats` di-guard agar idle saat paused. Indikator "· berhenti" muncul di header info.
    - **TrendChart** mendukung `height="100%"` (mengisi kontainer flex).
    - **RoiEditor**: saat menggeser titik muncul **mini-preview ter-zoom 3×** (floating) menampilkan area di sekitar titik + koordinat natural, agar tahu batas geseran.
    - **DetectionPreviewModal**: tidak lagi memutar video loop independen; kini **seek `currentTime` ke playhead utama** (prop `currentTime=d.stats.t`) sehingga preview ROI ter-zoom menampilkan **frame real-time yang sama** dengan deteksi live.
    - Build FE OK (`npm run build`). File diubah: `app/page.tsx`, `app/globals.css`, `components/{TrackedView,RoiEditor,DetectionPreviewModal,TrendChart,AppShell}.tsx`, `components/DashboardContext.tsx` (Stats + `playing`).
11. **Batch fix UI/UX + tracking + halaman Panduan + modal berstyle (TERBARU)**:
    - **ROI zoom-preview 2D (fix)**: pratinjau geser titik dulu hanya bergeser horizontal (kombinasi `objectFit:cover`+`objectPosition`+`scale` keliru). Diganti pakai **`background-position`** terhitung (`boxW/2 - x*Z`, `boxH/2 - y*Z`, zoom 2.6×) + crosshair di pusat → mengikuti titik di **kedua sumbu** secara akurat. Panel muncul fixed kanan-atas.
    - **Scroll Settings/History (fix)**: akibat `main` di `AppShell` kini `overflow-hidden`, halaman panjang ke-clip. Solusi: tiap halaman non-dashboard membungkus kontennya dalam **`h-full overflow-y-auto p-4 md:p-6`** (Settings, History, Panduan) sehingga scroll per-halaman, dashboard tetap fit-viewport. Konten dibatasi `max-w-*` + `mx-auto`.
    - **Optimasi Kalman** (`core/tracking.py`): tuning `processNoiseCov` = diag([1e-2,1e-2,5e-1,5e-1]) (velocity lebih agile) + `measurementNoiseCov` 0.5 (lebih percaya deteksi). Asosiasi kini **dua tahap**: (1) greedy IoU, lalu (2) **gate jarak centroid** (`max(TRACK_DIST_GATE, 1.5*max(w,h))`) untuk blob yang tak overlap antar-deteksi (batuan kecil/cepat pada stride besar) → gerakan tertangkap, bukan velocity 0. Param baru `TRACK_DIST_GATE` (default 90 px) di `config.py`, diteruskan dari `processor.py`. (Mencabut keterbatasan §13 no.1 — kini dikerjakan atas permintaan user.)
    - **Navbar reset (fix)**: navigasi balik ke Dashboard me-remount `TrackedView` → `<video>` baru main dari t=0 → tampak "reset". Solusi: `start()`/`reset()` mereset `stats`; `TrackedView` punya prop **`initialTime`** dan **seek saat `onLoadedMetadata`** ke playhead tersimpan (`stats.t`, persist di provider) → navigasi balik **melanjutkan**, bukan mengulang. Tombol **Putar ulang** set `resumeAt=0`. Breadcrumb "Cutting Monitoring" kini **Next `<Link>`** (soft nav, tanpa reload).
    - **Halaman baru `/panduan`** (`app/panduan/page.tsx`): langkah cepat (6 langkah), istilah penting, tips akurasi, FAQ (accordion `<details>`), CTA. Ditambahkan ke `Sidebar` (MODULES) + label di `Breadcrumb`. **Catatan: menu jadi 4** (Dashboard/Settings/Riwayat/Panduan) — perubahan disetujui user (mengubah keputusan "3 menu" di §2).
    - **Modal konfirmasi berstyle** (`components/ConfirmModal.tsx`): pengganti `window.confirm`/`alert`. Backdrop blur, ESC untuk batal, varian `danger`, state `busy`. Dipakai di **History** untuk hapus sesi (state `pendingDelete`/`deleting`/`deleteError`).
    - Validasi: **36 backend test passed**, **`npm run build` OK** (route `/panduan` tergenerate), **Docker rebuilt** → health 200, `/panduan/` 200.
12. **Pause-nyata + clip ROI + kontrol video bersih (TERBARU)**:
    - **ROI zoom-preview dekat titik (fix lagi)**: panel preview tidak lagi `fixed` kanan-atas; kini **`absolute` menempel di sekitar handle** (posisi = % titik) dan otomatis bergeser ke ruang kosong (`translate` tergantung kuadran) agar tidak menutupi titik.
    - **Pause = benar-benar menghentikan deteksi**: dulu pause hanya membekukan TAMPILAN; worker backend tetap memproses seluruh video (stream WS jalan terus). Sekarang ada **pause gate** di `processor.py` (`_pause_events`; loop `while pause_ev.is_set() and not cancel: sleep`) + `request_pause/resume`. WS handler (`ws_stream.py`) menambah **task receiver** `websocket.receive_json()` → aksi `pause`/`resume`. Frontend `DashboardContext.togglePause()` kirim `{action}` lewat `wsRef`. Jadi video di-pause → deteksi backend berhenti (CPU idle), bukan cuma display.
    - **Deteksi keluar ROI (fix)**: mask full-frame kini **di-clip hard ke poligon ROI** di backend (`cv2.fillPoly` → `full_mask * roi_clip`) sehingga blob tak pernah lahir di luar ROI. Frontend `TrackedView` juga **`ctx.clip()` ke poligon ROI** sebelum menggambar mask (jaga-jaga extrapolasi motion).
    - **Auto-play saat pindah tab (fix) + kontrol video disembunyikan**: `<video>` kini **tanpa `controls`/`autoPlay`** (bersih: tanpa volume/fullscreen/PiP; `controlsList` + `disablePictureInPicture` + blok context-menu). Playback **dikontrol prop `paused`** (persist di provider) → balik tab tetap pause, tidak main sendiri; tetap resume di `initialTime`. Overlay bersih; tombol **Putar ulang** hanya muncul saat video selesai.
    - **Tombol Jeda/Lanjut** ditambah **di kiri tombol Stop** (ikon ⏸/▶). **Stop** kini menghentikan deteksi tapi **tetap di live view** (state `stopped`), menonaktifkan tombol Jeda & Stop; indikator status "· dijeda"/"· dihentikan" di header kartu. "Sesi baru" kembali ke setup.
    - Validasi: **36 backend test passed**, **`npm run build` OK**, **Docker rebuilt** → health 200.
13. **Settings UX: preview interaktif + info tips (TERBARU)**:
    - **Endpoint baru `POST /api/roi/analyze`** (`routes_roi.py`): warp frame referensi → ROI ter-rektifikasi → inferensi → balikan **rectified image (PNG) + mask biner (PNG L 0/255) + `fg_area_pct`** (param `model`/`threshold`/`refine_edges`). Memungkinkan frontend memvisualkan coverage tanpa banyak round-trip.
    - **`RoiTuningPreview.tsx`**: canvas menampilkan rectified ROI + **mask merah** + **grid** + **highlight sel terisi**, dan **menghitung coverage% di sisi klien** (rumus identik backend: `nCols=⌊640/cell⌋`, `nRows=⌊224/cell⌋`, `min_px=max(1,⌊τ·cell²⌋)`). Geser slider **ukuran sel / τ** → update **seketika** (tanpa backend); ganti **model/threshold/refine** → auto **re-analyze** (debounce 450 ms) sehingga efek threshold pada mask terlihat langsung.
    - **`InfoTip.tsx`**: tombol kecil **"i"** (hover/klik) berisi penjelasan, dipasang di **model, threshold, stride, ukuran sel, τ okupansi, refine, & grup coverage**. Threshold & stride juga diberi label skala (sensitif↔ketat, dst.).
    - **`settings/page.tsx` ditulis ulang**: panel "Pratinjau & Penyetelan Langsung" dengan preview + **readout coverage% live + fg piksel% + jumlah sel terisi**, plus catatan edukatif **"kenapa persentase kecil → tergantung ukuran batuan relatif sel"**. `ControlsPanel` diberi InfoTip. (Menjawab keluhan coverage selalu <5% & slider tanpa visualisasi.)
    - Validasi: **36 backend test passed**, **`npm run build` OK** (settings 7.66 kB), **Docker rebuilt** → health 200, `/settings/` 200.
14. **Tooltip portal, default optimal, live frame-accurate, tooltip Riwayat, PDF pro + logo (TERBARU)**:
    - **InfoTip pakai portal**: tooltip dirender via `createPortal` ke `<body>` dengan **posisi fixed terhitung dari rect tombol + clamp viewport + flip atas/bawah** → tooltip panjang tidak lagi terpotong scroll-container/overflow atau tertutup kartu lain.
    - **Tombol "Setelan default optimal"** di Settings: sekali klik menyetel **MobileViT + threshold default + stride 3 + grid 16/τ0.05 + refine on** (rekomendasi akurat-cepat-realistis).
    - **Live view FRAME-ACCURATE** (`TrackedView` ditulis ulang): tidak lagi memutar video mulus dengan mask ter-extrapolasi (yang terasa delay/"fake"). Sekarang `<video>` **di-seek ke waktu frame yang BENAR-BENAR dianalisis** dan mask digambar **tanpa motion-extrapolation** → frame & mask selalu cocok (boleh patah-patah, tapi real). Live = snap ke frontier; replay = clock internal real-time snap ke frame analisis. Context menambah `detectionDone` (set saat WS `done`/stop) + `replay()`; `page.tsx` pass `done`, Putar ulang panggil `replay()`. (Mencabut keterbatasan §13 no.2 — pendekatan sync diganti frame-accurate.)
    - **Tooltip chart Riwayat**: `HistChartTip` custom (Frame #, Coverage %, Jumlah stone) menggantikan tooltip default yang ambigu.
    - **PDF profesional** (`report.py` ditulis ulang dgn **Platypus**): header berlogo + judul, tabel **Informasi Sesi** (zebra) + tabel **Ringkasan** (header oranye), grafik tren, catatan metodologi. 
    - **Logo aplikasi** dari `app_icon.ico` → dikonversi PNG: `frontend/app/favicon.ico` + `app/icon.png` (favicon), `frontend/public/logo.png` (header sidebar), `backend/app/assets/logo.png` (PDF). Sidebar memakai logo menggantikan kotak "S".
    - Validasi: **36 backend test passed**, **`npm run build` OK** (favicon `/icon.png` tergenerate), **Docker rebuilt** → health/`logo.png`/`favicon.ico` 200; PDF tervalidasi lokal (22 KB, logo termuat).
15. **Preset per-model, 2 chart Riwayat, navigasi smooth, tooltip sidebar collapsed (TERBARU)**:
    - **Dua tombol setelan terbaik per model** (Settings): **MobileViT** (threshold 0.15 · sel 23 · τ 0.01 · stride 3) dan **BiSeNet v2** (threshold 0.20 · sel 20 · τ 0.03 · stride 3) — nilai hasil troubleshooting. Menggantikan tombol tunggal sebelumnya (`applyPreset(modelName)` + map `PRESETS`).
    - **Riwayat = 2 grafik terpisah**: Coverage % (area oranye) dan Stone Count (area biru) masing-masing kartu sendiri (sebelumnya 1 chart dual-axis yang membuat seri kedua tak terlihat). `Line` recharts dihapus dari import.
    - **Navigasi antar-tab smooth saat deteksi**: `DashboardContext` kini **mem-buffer frame WS di ref** (`framesBufRef`/`progressBufRef`) dan **flush ke state tiap 160 ms** (`startFlush`/`stopFlush`/`flushNow`) — bukan `setState` per pesan. Re-render turun dari ~per-frame menjadi ~6/dtk sehingga pindah tab tidak lagi nge-freeze. Flush final saat `done`/`stop`; buffer dibersihkan di `reset`/`start`.
    - **Sidebar collapsed**: tiap item nav `group relative` + **tooltip nama halaman** muncul saat hover (slide-in dari kiri, `z-50`).
    - Validasi: **`npm run build` OK** (backend tak berubah), **Docker rebuilt** → health/`/settings/`//`/history/` 200.
16. **Riwayat 1 grafik, dashboard reset saat selesai, footer PDF, panduan walkthrough (TERBARU)**:
    - **Riwayat kembali 1 grafik**: `ComposedChart` (Area coverage oranye sumbu-kiri + Line stone biru sumbu-kanan) dengan legend + `HistChartTip`. (Membatalkan pemisahan 2 chart pada iterasi 15 atas permintaan user.)
    - **Dashboard auto-reset saat selesai**: ketika deteksi mencapai frame terakhir (`done` & playhead di akhir), `TrackedView.onEnded` → `d.reset()` sehingga **seluruh tombol/tampilan kembali ke kondisi awal** (setup). Tombol "Putar ulang" + state `ended/replayKey/resumeAt` dihapus. Hasil tetap tersimpan otomatis ke Riwayat.
    - **PDF footer credentials**: kalimat "Dokumen ini dihasilkan otomatis oleh sistem." dipindah ke **footer tiap halaman** (via `onFirstPage/onLaterPages`) + garis pemisah + nomor halaman, dan di bawahnya **"Well Site : Pertamina Hulu Rokan"**. Paragraf catatan metodologi dirampingkan jadi satu kalimat (tanpa kalimat auto-generated).
    - **Panduan = walkthrough**: `app/panduan/page.tsx` ditulis ulang jadi **bertahap** (7 langkah, progress bar + dots, tombol Sebelumnya/Berikutnya), bisa **"Lewati panduan & mulai"** kapan saja, dan langkah terakhir tombol **"Mulai Menggunakan Aplikasi"** → Dashboard.
    - Validasi: PDF lokal OK (22.6 KB, footer+Well Site), **`npm run build` OK**, **Docker rebuilt** → health/`/panduan/`//`/history/`//`/settings/` 200.
17. **Fix: ROI reset ke default saat unggah video baru (TERBARU)**: dulu koordinat ROI persist di `localStorage`, sehingga mengunggah video lain memakai ROI hasil adjust video sebelumnya. Kini `DashboardContext.pickFile()` **mereset `roi` ke `DEFAULT_ROI`** (dan menyimpannya ke config) setiap kali frame video baru dimuat. Validasi: `npm run build` OK, Docker rebuilt → health 200.
18. **ROI tidak boleh keluar area video (batas mutlak, TERBARU)**: dua lapis jaminan untuk segala resolusi video:
    - **Clamp saat muat**: `pickFile()` me-reset ROI ke `DEFAULT_ROI` **yang di-clamp ke `fr.width`/`fr.height`** frame aktual (memakai dimensi dari `extractFirstFrame`), jadi titik default tak pernah mulai di luar frame meski resolusi video lebih kecil dari koordinat default.
    - **Clamp saat render** (`RoiEditor`): polygon & handle digambar dari koordinat yang **di-clamp ke (0..nw, 0..nh)** (`disp`), dan drag sudah di-clamp via `pointerToNatural`. Jadi titik/garis ROI **mutlak tidak bisa keluar** dari area video player.
    - Validasi: `npm run build` OK, Docker rebuilt → health 200.
19. **PDF: judul & Well Site (TERBARU)**: judul header jadi **"Laporan Analisis Cutting Shale Shaker"** (tanpa em-dash). **"Well Site : Pertamina Hulu Rokan"** dipindah dari footer ke **subtitle header** (baris ketiga, di bawah Sesi & Dibuat). Footer kini hanya "Dokumen ini dihasilkan otomatis oleh sistem." + nomor halaman. Validasi: PDF lokal OK, Docker rebuilt → health 200.
20. **Cegah hapus sesi yang sedang berjalan (TERBARU)**: dulu sesi berstatus `running` (termasuk saat di-jeda — status backend tetap `running`) bisa dihapus dari Riwayat → risiko hapus tak sengaja saat analisis berjalan. Kini:
    - **Backend**: `DELETE /api/sessions/{id}` menolak bila `status=="running"` → **409** ("hentikan/Stop dulu").
    - **Frontend** (`SessionTable`): tombol Hapus untuk sesi `running` diganti label **"Terkunci"** (ikon gembok, non-aktif) dengan tooltip. Sesi lain (done/cancelled/error/created) tetap bisa dihapus.
    - Validasi: 36 pytest passed, `npm run build` OK, Docker rebuilt → health 200.
21. **Fix: sesi ter-cancel & "reset" saat pindah tab ketika running (TERBARU)**: penyebabnya fitur **auto-reset saat selesai** (`onEnded → d.reset()`) — `reset()` menutup WS → backend menganggap disconnect → status jadi **cancelled**, dan phase balik ke setup (terlihat "mengulang dari awal"). Perbaikan: `onEnded` dijadikan **no-op** (tidak lagi mereset/menutup WS). Saat deteksi **selesai**, tampilan **freeze di frame terakhir** (TrackedView: jika `done` saat mount → clock di akhir, bukan replay dari 0), status kartu menampilkan **"· selesai & tersimpan"**, dan tombol **Jeda/Stop dinonaktifkan** (`disabled` saat `detectionDone`); gunakan **"Sesi baru"** untuk mulai lagi. Hasil tetap tersimpan otomatis (status `done`). Validasi: `npm run build` OK, Docker rebuilt → health 200.
22. **Auto-cleanup + video sumber + hapus emoji + hapus Well Site PDF (TERBARU)**:
    - **Auto-cleanup 3 hari**: background task `_cleanup_loop()` di `main.py` lifespan — tiap jam hapus file video sesi `done`/`cancelled`/`error` yang `ended_at` > 3 hari + bersihkan file yatim piatu (session ID tidak ada di DB). Dikonfigurasi via env `CLEANUP_RETENTION_DAYS` (default 3).
    - **Video sumber (demo)**: folder `data/source_videos/` berisi video `.mp4` uji coba yang **di-bake ke Docker image** (`COPY data/source_videos/ ./source_videos/`), disajikan via endpoint baru `GET /api/source-videos` + `GET /api/source-videos/{name}/download`. Dashboard menampilkan tombol pilih video sumber di bawah area upload — klik langsung pakai tanpa upload manual. Flow: fetch blob → `pickFile()` seperti upload biasa.
    - **Hapus emoji**: karakter `👋` di Panduan dan `✕` di DetectionPreviewModal diganti teks biasa (standar industri, profesional).
    - **Hapus Well Site PDF**: baris "Well Site : Pertamina Hulu Rokan" dihapus dari header PDF (`report.py`) — data rahasia/riskan.
    - File baru: `app/api/routes_source_videos.py`, `data/source_videos/`.
    - File diubah: `main.py` (lifespan+cleanup), `config.py` (SOURCE_VIDEOS_DIR, CLEANUP_RETENTION_DAYS), `Dockerfile` (COPY source_videos + env), `docker-compose.yml` (hapus bind mount source_videos), `report.py` (hapus Well Site), `api.ts` (SourceVideo tipe + listSourceVideos + sourceVideoUrl), `DashboardContext.tsx` (sourceVideos state + loadSourceVideos + pickSourceVideo), `page.tsx` (daftar video sumber), `panduan/page.tsx` (hapus emoji), `DetectionPreviewModal.tsx` (hapus emoji), `.env.example` (CLEANUP_RETENTION_DAYS).
    - Validasi: **36 pytest passed**, **`npm run build` OK**.

> **Catatan diskusi**: user MEMUTUSKAN **skip** (a) toggle sync & (b) asосiasi centroid Kalman (poin keterbatasan §13 no.1-2 tetap berlaku, tidak dikerjakan atas permintaan user). User minta: setiap kali diminta "update README dan handoff" setelah suatu pekerjaan, **perbarui kedua file** (README + HANDOFF §13/§14).

---

## 15. Konvensi untuk Agent Penerus

- Backend: router di `app/api/` (APIRouter, prefix `/api`), import `from app.config import settings`. Jalankan tes via `backend/.venv`.
- Tambah kolom DB → daftarkan juga di `_migrate_add_columns()` (database.py) agar volume lama termigrasi.
- Frontend: komponen interaktif butuh `"use client"`. Static export → semua fetch di sisi klien. Alias `@/` = root frontend.
- Setelah ubah kode: jalankan `pytest` (backend) + `npm run build` (frontend) + `docker compose up -d --build` untuk validasi e2e.
- Kontrak data live: WS & `/tracks` memakai `blobs:[{poly:number[][], vx, vy}]` + `t` (detik) + `coverage_pct`. Jangan kembali ke skema box ber-ID kecuali diminta (user ingin mask tanpa ID).
- Jaga keputusan: FP32 (bukan INT8), mask-only, 3 menu, live mode, hemat 2GB.
