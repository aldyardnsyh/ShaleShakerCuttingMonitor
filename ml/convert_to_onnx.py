"""Convert trained PyTorch checkpoints (.pt) to ONNX (FP32).

FP32 export is mathematically identical to the PyTorch model (no accuracy
degradation) — only the graph format changes. Run this ONCE locally on a
machine that has torch + timm installed.

Usage:
    python ml/convert_to_onnx.py \
        --weights-dir ml/weights \
        --out-dir ml/onnx \
        --opset 17

Each checkpoint is a dict saved by the training notebook (cell 41) with keys:
    model (state_dict), fg_threshold, arch, num_classes, model_h, model_w,
    use_roi_crop, roi_src, ...
We read those metadata fields to build model_meta.json automatically.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from model_defs import build_model, DISPLAY_NAME

HERE = Path(__file__).resolve().parent

# Fallback location of the original training results (if ml/weights is empty).
RESULTS_MODELS = Path(
    r"D:/Kuliah/Tugas Akhir/Dataset/Training Model Baru/Results/models"
)

# Preprocessing constants (notebook cell 12).
MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)

# Default ROI source corners (notebook cell 10): TL, TR, BR, BL.
DEFAULT_ROI_SRC = [[760, 650], [1300, 614], [1315, 795], [780, 845]]


def _resolve_weight(name: str, weights_dir: Path) -> Path:
    """Find <name>_final.pt in weights_dir, else in the Results fallback."""
    fname = f"{name}_final.pt"
    cand = weights_dir / fname
    if cand.exists():
        return cand
    fallback = RESULTS_MODELS / fname
    if fallback.exists():
        return fallback
    raise FileNotFoundError(
        f"Tidak menemukan {fname} di {weights_dir} maupun {RESULTS_MODELS}"
    )


def _load_checkpoint(path: Path) -> dict:
    try:
        return torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:
        # Older torch without weights_only kwarg.
        return torch.load(path, map_location="cpu")


def convert_one(name: str, weights_dir: Path, out_dir: Path, opset: int) -> dict:
    ckpt_path = _resolve_weight(name, weights_dir)
    print(f"[{name}] memuat checkpoint: {ckpt_path}")
    ckpt = _load_checkpoint(ckpt_path)

    num_classes = int(ckpt.get("num_classes", 2))
    model_h = int(ckpt.get("model_h", 224))
    model_w = int(ckpt.get("model_w", 640))
    fg_threshold = float(ckpt.get("fg_threshold", 0.5))
    roi_src = ckpt.get("roi_src", DEFAULT_ROI_SRC)

    model = build_model(name, num_classes=num_classes, pretrained=False)
    state = ckpt["model"] if "model" in ckpt else ckpt
    missing, unexpected = model.load_state_dict(state, strict=False)
    if missing:
        print(f"[{name}] WARN missing keys: {len(missing)} (contoh: {missing[:3]})")
    if unexpected:
        print(f"[{name}] WARN unexpected keys: {len(unexpected)} (contoh: {unexpected[:3]})")
    model.eval()

    out_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = out_dir / f"{name}.onnx"
    dummy = torch.randn(1, 3, model_h, model_w)

    torch.onnx.export(
        model,
        dummy,
        str(onnx_path),
        input_names=["input"],
        output_names=["logits"],
        opset_version=opset,
        do_constant_folding=True,
        dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
    )
    print(f"[{name}] ONNX disimpan -> {onnx_path} ({onnx_path.stat().st_size/1e6:.1f} MB)")

    return {
        "name": name,
        "display_name": DISPLAY_NAME.get(name, name),
        "onnx_file": f"{name}.onnx",
        "num_classes": num_classes,
        "input_h": model_h,
        "input_w": model_w,
        "fg_threshold": fg_threshold,
        "roi_src": roi_src,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights-dir", default=str(HERE / "weights"))
    ap.add_argument("--out-dir", default=str(HERE / "onnx"))
    ap.add_argument("--opset", type=int, default=17)
    ap.add_argument("--models", nargs="*", default=["mobilevit", "bisenetv2"])
    args = ap.parse_args()

    weights_dir = Path(args.weights_dir)
    out_dir = Path(args.out_dir)

    entries = [convert_one(n, weights_dir, out_dir, args.opset) for n in args.models]

    meta = {
        "mean": list(MEAN),
        "std": list(STD),
        "default_model": "mobilevit",
        "models": {e["name"]: e for e in entries},
    }
    meta_path = out_dir / "model_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"\n[OK] model_meta.json -> {meta_path}")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
