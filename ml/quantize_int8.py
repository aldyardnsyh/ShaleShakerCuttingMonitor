"""OPTIONAL: INT8 dynamic quantization experiment + FP32-vs-INT8 report.

Dynamic quantization is weight-only and CPU-friendly. We DO NOT change the
served model automatically — this script only produces evidence so the user
can decide. Accuracy is assessed against the trusted FP32 outputs on REAL
ROI frames sampled from a video (mask IoU + argmax agreement), plus latency.

Run (using the backend venv which has onnxruntime + opencv + numpy):
    backend/.venv/Scripts/python ml/quantize_int8.py \
        --video "D:/Kuliah/Tugas Akhir/Dataset/Kode Uji Coba Test Video/dataset_asli_pdu_2.mp4" \
        --frames 40 --stride 10
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ONNX_DIR = HERE / "onnx"
INT8_DIR = ONNX_DIR / "int8"

DEFAULT_VIDEO = r"D:/Kuliah/Tugas Akhir/Dataset/Kode Uji Coba Test Video/dataset_asli_pdu_2.mp4"


def _softmax(logits, axis=1):
    z = logits - logits.max(axis=axis, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=axis, keepdims=True)


def _sample_inputs(meta, info, video, n_frames, stride):
    """Return a list of preprocessed NCHW float32 batches (real ROI frames if
    a video is available, else random noise)."""
    import cv2

    mean = np.array(meta["mean"], dtype=np.float32)
    std = np.array(meta["std"], dtype=np.float32)
    h, w = info["input_h"], info["input_w"]
    roi = np.array(info["roi_src"], dtype=np.float32)
    dst = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(roi, dst)

    inputs = []
    cap = cv2.VideoCapture(str(video)) if video else None
    if cap is not None and cap.isOpened():
        idx = 0
        while len(inputs) < n_frames:
            ret, frame = cap.read()
            if not ret:
                break
            if idx % stride == 0:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                warped = cv2.warpPerspective(rgb, M, (w, h), flags=cv2.INTER_LINEAR)
                x = (warped.astype(np.float32) / 255.0 - mean) / std
                inputs.append(np.ascontiguousarray(np.transpose(x, (2, 0, 1))[None], dtype=np.float32))
            idx += 1
        cap.release()
    if not inputs:
        rng = np.random.default_rng(0)
        inputs = [rng.standard_normal((1, 3, h, w)).astype(np.float32) for _ in range(n_frames)]
    return inputs


def _bench(sess, inputs, runs=30):
    # warmup
    for _ in range(3):
        sess.run(["logits"], {"input": inputs[0]})
    times = []
    i = 0
    while len(times) < runs:
        t0 = time.perf_counter()
        sess.run(["logits"], {"input": inputs[i % len(inputs)]})
        times.append((time.perf_counter() - t0) * 1000.0)
        i += 1
    return float(np.mean(times)), float(np.median(times))


def main():
    import onnxruntime as ort
    from onnxruntime.quantization import quantize_static, QuantType, QuantFormat, CalibrationDataReader

    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=DEFAULT_VIDEO)
    ap.add_argument("--frames", type=int, default=40)
    ap.add_argument("--stride", type=int, default=10)
    args = ap.parse_args()

    meta = json.loads((ONNX_DIR / "model_meta.json").read_text(encoding="utf-8"))
    INT8_DIR.mkdir(parents=True, exist_ok=True)

    def make_sess(path):
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        return ort.InferenceSession(str(path), sess_options=opts, providers=["CPUExecutionProvider"])

    class _Reader(CalibrationDataReader):
        """Feeds real ROI frames to the static-quantization calibrator."""
        def __init__(self, inputs):
            self._it = iter([{"input": x} for x in inputs])

        def get_next(self):
            return next(self._it, None)

    report = []
    for name, info in meta["models"].items():
        fp32_path = ONNX_DIR / info["onnx_file"]
        int8_path = INT8_DIR / f"{name}.int8.onnx"

        inputs = _sample_inputs(meta, info, args.video, args.frames, args.stride)

        print(f"[{name}] static-quantizing (QDQ) -> {int8_path.name}  [{len(inputs)} calib frames]")
        # QDQ + QLinearConv is supported on the CPU EP (unlike ConvInteger).
        quantize_static(
            str(fp32_path),
            str(int8_path),
            calibration_data_reader=_Reader(inputs),
            quant_format=QuantFormat.QDQ,
            per_channel=True,
            weight_type=QuantType.QInt8,
            activation_type=QuantType.QUInt8,
        )

        s32, s8 = make_sess(fp32_path), make_sess(int8_path)

        # accuracy vs trusted FP32
        thr = info["fg_threshold"]
        inter = union = agree = total = 0
        max_abs = 0.0
        for x in inputs:
            o32 = _softmax(s32.run(["logits"], {"input": x})[0], 1)[0]
            o8 = _softmax(s8.run(["logits"], {"input": x})[0], 1)[0]
            m32 = o32[1] >= thr
            m8 = o8[1] >= thr
            inter += int(np.logical_and(m32, m8).sum())
            union += int(np.logical_or(m32, m8).sum())
            agree += int((m32 == m8).sum())
            total += m32.size
            max_abs = max(max_abs, float(np.abs(o32 - o8).max()))

        iou = (inter / union) if union > 0 else 1.0
        agreement = agree / total
        lat32 = _bench(s32, inputs)
        lat8 = _bench(s8, inputs)

        row = {
            "model": name,
            "fp32_mb": round(fp32_path.stat().st_size / 1e6, 2),
            "int8_mb": round(int8_path.stat().st_size / 1e6, 2),
            "fp32_ms_mean": round(lat32[0], 1),
            "int8_ms_mean": round(lat8[0], 1),
            "speedup": round(lat32[0] / lat8[0], 2) if lat8[0] else 0.0,
            "mask_iou_vs_fp32": round(iou, 4),
            "pixel_agreement": round(agreement, 4),
            "max_prob_diff": round(max_abs, 4),
        }
        report.append(row)
        print("   ", row)

    (INT8_DIR / "quant_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Markdown summary
    lines = ["# FP32 vs INT8 — Laporan Kuantisasi\n",
             "| Model | FP32 MB | INT8 MB | FP32 ms | INT8 ms | Speedup | Mask IoU vs FP32 | Pixel Agreement |",
             "|---|---|---|---|---|---|---|---|"]
    for r in report:
        lines.append(
            f"| {r['model']} | {r['fp32_mb']} | {r['int8_mb']} | {r['fp32_ms_mean']} | "
            f"{r['int8_ms_mean']} | {r['speedup']}x | {r['mask_iou_vs_fp32']} | {r['pixel_agreement']} |"
        )
    lines += [
        "",
        "- **Mask IoU vs FP32** mengukur seberapa identik mask INT8 terhadap FP32 (1.0 = identik).",
        "- Default serving tetap **FP32** (tidak ada penurunan akurasi). Aktifkan INT8 hanya bila",
        "  speedup sepadan dan IoU/agreement masih dapat diterima untuk kebutuhan lapangan.",
    ]
    (INT8_DIR / "QUANT_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n[OK] Laporan -> ml/onnx/int8/QUANT_REPORT.md & quant_report.json")


if __name__ == "__main__":
    main()
