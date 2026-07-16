"""Validate PyTorch vs ONNX output parity (no accuracy degradation check).

For each model: build PyTorch model + load weights, run the same random
input through both PyTorch and ONNX Runtime, and report the max absolute
difference. FP32 export should give diff < 1e-3 (typically ~1e-5).

Usage:
    python ml/validate_parity.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
import onnxruntime as ort

from model_defs import build_model
from convert_to_onnx import _resolve_weight, _load_checkpoint

HERE = Path(__file__).resolve().parent
TOL = 1e-3


def check_one(name: str, weights_dir: Path, onnx_dir: Path, meta: dict) -> dict:
    info = meta["models"][name]
    h, w = info["input_h"], info["input_w"]
    num_classes = info["num_classes"]

    ckpt = _load_checkpoint(_resolve_weight(name, weights_dir))
    model = build_model(name, num_classes=num_classes, pretrained=False)
    model.load_state_dict(ckpt["model"], strict=False)
    model.eval()

    rng = np.random.default_rng(0)
    x = rng.standard_normal((1, 3, h, w)).astype(np.float32)

    with torch.no_grad():
        torch_out = model(torch.from_numpy(x)).numpy()

    sess = ort.InferenceSession(
        str(onnx_dir / info["onnx_file"]), providers=["CPUExecutionProvider"]
    )
    onnx_out = sess.run(["logits"], {"input": x})[0]

    assert torch_out.shape == onnx_out.shape, f"shape mismatch {torch_out.shape} vs {onnx_out.shape}"
    expected_shape = (1, num_classes, h, w)
    assert onnx_out.shape == expected_shape, f"unexpected shape {onnx_out.shape} != {expected_shape}"

    max_abs = float(np.max(np.abs(torch_out - onnx_out)))
    # Also compare the argmax masks (what actually drives the % area metric).
    mask_match = float((torch_out.argmax(1) == onnx_out.argmax(1)).mean())
    status = "PASS" if max_abs < TOL else "FAIL"
    print(
        f"[{name}] shape={onnx_out.shape} max_abs_diff={max_abs:.2e} "
        f"argmax_match={mask_match*100:.3f}%  -> {status}"
    )
    return {"name": name, "max_abs_diff": max_abs, "argmax_match": mask_match, "status": status}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights-dir", default=str(HERE / "weights"))
    ap.add_argument("--onnx-dir", default=str(HERE / "onnx"))
    args = ap.parse_args()

    onnx_dir = Path(args.onnx_dir)
    meta = json.loads((onnx_dir / "model_meta.json").read_text(encoding="utf-8"))

    results = [check_one(n, Path(args.weights_dir), onnx_dir, meta) for n in meta["models"]]

    all_pass = all(r["status"] == "PASS" for r in results)
    print("\n" + ("=" * 60))
    if all_pass:
        print("AKURASI IDENTIK (no degradation) — semua model lolos paritas < 1e-3.")
    else:
        print("ADA MODEL YANG GAGAL PARITAS — periksa kembali konversi.")
    print("=" * 60)
    raise SystemExit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
