"""Model architecture definitions.

Copied verbatim (logic-identical) from the training notebook
`training-model-baru-tugas-akhir-v4.ipynb` cells 15-17 so that weights load
with the exact same module names. Used only offline for ONNX conversion &
parity validation (NOT imported by the backend, which serves ONNX).

Requires: torch, timm.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

NUM_CLASSES = 2


# ---------------------------------------------------------------------------
# Shared building block
# ---------------------------------------------------------------------------
class ConvBNReLU(nn.Module):
    def __init__(self, c_in, c_out, k=3, s=1, p=1, groups=1):
        super().__init__()
        self.conv = nn.Conv2d(c_in, c_out, k, s, p, groups=groups, bias=False)
        self.bn = nn.BatchNorm2d(c_out)
        self.act = nn.ReLU(inplace=True)

    def forward(self, x):
        return self.act(self.bn(self.conv(x)))


# ---------------------------------------------------------------------------
# MobileViT + U-Net decoder  (notebook cell 15)
# ---------------------------------------------------------------------------
class UNetDecoderBlock(nn.Module):
    def __init__(self, in_ch, skip_ch, out_ch):
        super().__init__()
        self.conv1 = ConvBNReLU(in_ch + skip_ch, out_ch)
        self.conv2 = ConvBNReLU(out_ch, out_ch)

    def forward(self, x, skip):
        x = F.interpolate(x, scale_factor=2, mode="bilinear", align_corners=False)
        if skip is not None:
            if x.shape[-2:] != skip.shape[-2:]:
                x = F.interpolate(x, size=skip.shape[-2:], mode="bilinear", align_corners=False)
            x = torch.cat([x, skip], dim=1)
        return self.conv2(self.conv1(x))


class MobileViTUNet(nn.Module):
    def __init__(self, num_classes=2, backbone="mobilevit_s", pretrained=True, dec_channels=(256, 128, 64, 32)):
        super().__init__()
        import timm

        self.encoder = timm.create_model(backbone, features_only=True, pretrained=pretrained)
        enc_ch = self.encoder.feature_info.channels()
        rev = enc_ch[::-1]
        skips = rev[1:]
        outs = list(dec_channels)[: len(skips)]
        in_ch = rev[0]
        blocks = []
        for skip_ch, out_ch in zip(skips, outs):
            blocks.append(UNetDecoderBlock(in_ch, skip_ch, out_ch))
            in_ch = out_ch
        self.blocks = nn.ModuleList(blocks)
        self.final = nn.Conv2d(in_ch, num_classes, 1)

    def forward(self, x):
        H, W = x.shape[-2:]
        feats = self.encoder(x)[::-1]
        out = feats[0]
        for blk, skip in zip(self.blocks, feats[1:]):
            out = blk(out, skip)
        out = self.final(out)
        if out.shape[-2:] != (H, W):
            out = F.interpolate(out, size=(H, W), mode="bilinear", align_corners=False)
        return out


# ---------------------------------------------------------------------------
# BiSeNet v2  (notebook cell 16)
# ---------------------------------------------------------------------------
class DetailBranch(nn.Module):
    def __init__(self):
        super().__init__()
        self.S1 = nn.Sequential(ConvBNReLU(3, 64, 3, 2, 1), ConvBNReLU(64, 64, 3, 1, 1))
        self.S2 = nn.Sequential(ConvBNReLU(64, 64, 3, 2, 1), ConvBNReLU(64, 64, 3, 1, 1), ConvBNReLU(64, 64, 3, 1, 1))
        self.S3 = nn.Sequential(ConvBNReLU(64, 128, 3, 2, 1), ConvBNReLU(128, 128, 3, 1, 1), ConvBNReLU(128, 128, 3, 1, 1))

    def forward(self, x):
        return self.S3(self.S2(self.S1(x)))


class StemBlock(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv = ConvBNReLU(3, 16, 3, 2, 1)
        self.left = nn.Sequential(ConvBNReLU(16, 8, 1, 1, 0), ConvBNReLU(8, 16, 3, 2, 1))
        self.right = nn.MaxPool2d(3, 2, 1)
        self.fuse = ConvBNReLU(32, 16, 3, 1, 1)

    def forward(self, x):
        x = self.conv(x)
        return self.fuse(torch.cat([self.left(x), self.right(x)], dim=1))


class CEBlock(nn.Module):
    def __init__(self):
        super().__init__()
        self.bn = nn.BatchNorm2d(128)
        self.conv_gap = ConvBNReLU(128, 128, 1, 1, 0)
        self.conv_last = ConvBNReLU(128, 128, 3, 1, 1)

    def forward(self, x):
        feat = torch.mean(x, dim=(2, 3), keepdim=True)
        feat = self.conv_gap(self.bn(feat))
        return self.conv_last(feat + x)


class GELayerS1(nn.Module):
    def __init__(self, c_in, c_out, exp=6):
        super().__init__()
        mid = c_in * exp
        self.conv1 = ConvBNReLU(c_in, c_in, 3, 1, 1)
        self.dw = nn.Sequential(nn.Conv2d(c_in, mid, 3, 1, 1, groups=c_in, bias=False), nn.BatchNorm2d(mid), nn.ReLU(inplace=True))
        self.conv2 = nn.Sequential(nn.Conv2d(mid, c_out, 1, 1, 0, bias=False), nn.BatchNorm2d(c_out))
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        return self.relu(self.conv2(self.dw(self.conv1(x))) + x)


class GELayerS2(nn.Module):
    def __init__(self, c_in, c_out, exp=6):
        super().__init__()
        mid = c_in * exp
        self.conv1 = ConvBNReLU(c_in, c_in, 3, 1, 1)
        self.dw1 = nn.Sequential(nn.Conv2d(c_in, mid, 3, 2, 1, groups=c_in, bias=False), nn.BatchNorm2d(mid))
        self.dw2 = nn.Sequential(nn.Conv2d(mid, mid, 3, 1, 1, groups=mid, bias=False), nn.BatchNorm2d(mid), nn.ReLU(inplace=True))
        self.conv2 = nn.Sequential(nn.Conv2d(mid, c_out, 1, 1, 0, bias=False), nn.BatchNorm2d(c_out))
        self.shortcut = nn.Sequential(
            nn.Conv2d(c_in, c_in, 3, 2, 1, groups=c_in, bias=False), nn.BatchNorm2d(c_in),
            nn.Conv2d(c_in, c_out, 1, 1, 0, bias=False), nn.BatchNorm2d(c_out))
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        feat = self.conv2(self.dw2(self.dw1(self.conv1(x))))
        return self.relu(feat + self.shortcut(x))


class SemanticBranch(nn.Module):
    def __init__(self):
        super().__init__()
        self.S1S2 = StemBlock()
        self.S3 = nn.Sequential(GELayerS2(16, 32), GELayerS1(32, 32))
        self.S4 = nn.Sequential(GELayerS2(32, 64), GELayerS1(64, 64))
        self.S5 = nn.Sequential(GELayerS2(64, 128), GELayerS1(128, 128), GELayerS1(128, 128), GELayerS1(128, 128))
        self.ce = CEBlock()

    def forward(self, x):
        x = self.S1S2(x)
        x = self.S3(x)
        x = self.S4(x)
        x = self.S5(x)
        return self.ce(x)


class BGALayer(nn.Module):
    def __init__(self):
        super().__init__()
        self.left1 = nn.Sequential(nn.Conv2d(128, 128, 3, 1, 1, groups=128, bias=False), nn.BatchNorm2d(128), nn.Conv2d(128, 128, 1, 1, 0, bias=False))
        self.left2 = nn.Sequential(nn.Conv2d(128, 128, 3, 2, 1, bias=False), nn.BatchNorm2d(128), nn.AvgPool2d(3, 2, 1, ceil_mode=False))
        self.right1 = nn.Sequential(nn.Conv2d(128, 128, 3, 1, 1, bias=False), nn.BatchNorm2d(128))
        self.right2 = nn.Sequential(nn.Conv2d(128, 128, 3, 1, 1, groups=128, bias=False), nn.BatchNorm2d(128), nn.Conv2d(128, 128, 1, 1, 0, bias=False))
        self.conv = ConvBNReLU(128, 128, 3, 1, 1)

    def forward(self, x_d, x_s):
        l1 = self.left1(x_d)
        l2 = self.left2(x_d)
        r1 = self.right1(x_s)
        r2 = self.right2(x_s)
        r1 = F.interpolate(r1, size=l1.shape[-2:], mode="bilinear", align_corners=False)
        left = l1 * torch.sigmoid(r1)
        right = l2 * torch.sigmoid(r2)
        right = F.interpolate(right, size=left.shape[-2:], mode="bilinear", align_corners=False)
        return self.conv(left + right)


class SegmentHead(nn.Module):
    def __init__(self, c_in, mid, n_classes):
        super().__init__()
        self.conv = ConvBNReLU(c_in, mid, 3, 1, 1)
        self.drop = nn.Dropout(0.1)
        self.out = nn.Conv2d(mid, n_classes, 1)

    def forward(self, x, size):
        x = self.out(self.drop(self.conv(x)))
        return F.interpolate(x, size=size, mode="bilinear", align_corners=False)


class BiSeNetV2(nn.Module):
    def __init__(self, num_classes=2):
        super().__init__()
        self.detail = DetailBranch()
        self.semantic = SemanticBranch()
        self.bga = BGALayer()
        self.head = SegmentHead(128, 1024, num_classes)

    def forward(self, x):
        size = x.shape[-2:]
        fd = self.detail(x)
        fs = self.semantic(x)
        return self.head(self.bga(fd, fs), size)


# ---------------------------------------------------------------------------
# Factory (notebook cell 17)
# ---------------------------------------------------------------------------
def build_model(name, num_classes=NUM_CLASSES, pretrained=False):
    name = name.lower()
    if name in ("mobilevit", "mobilevit_s"):
        return MobileViTUNet(num_classes=num_classes, backbone="mobilevit_s", pretrained=pretrained)
    elif name in ("bisenetv2", "bisenet_v2", "bisenet"):
        return BiSeNetV2(num_classes=num_classes)
    raise ValueError(f"Model tidak dikenal: {name}")


MODEL_NAMES = ["mobilevit", "bisenetv2"]
DISPLAY_NAME = {"mobilevit": "MobileViT", "bisenetv2": "BiSeNet v2"}
