#!/usr/bin/env python3
import os
from pathlib import Path
from PIL import Image, ImageEnhance

# 5.7" Inky Impression の解像度
PANEL_WIDTH = 600
PANEL_HEIGHT = 448

BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "images_raw"   # 元画像
OUT_DIR = BASE_DIR / "images"       # リサイズ後（slideshow.py が読む方）

OUT_DIR.mkdir(exist_ok=True)

CONTRAST = 1.15  # slideshow.py の設定と合わせる

def preprocess_one(src: Path, dst: Path):
    with Image.open(src) as img:
        img = img.convert("RGB")

        # コントラスト強調（任意）
        img = ImageEnhance.Contrast(img).enhance(CONTRAST)

        # アスペクト比を保ったまま、少し大きめにリサイズ → 中央クロップ
        img_ratio = img.width / img.height
        target_ratio = PANEL_WIDTH / PANEL_HEIGHT

        if img_ratio > target_ratio:
            new_height = PANEL_HEIGHT
            new_width = int(PANEL_HEIGHT * img_ratio)
        else:
            new_width = PANEL_WIDTH
            new_height = int(PANEL_WIDTH / img_ratio)

        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        left = (new_width - PANEL_WIDTH) // 2
        top = (new_height - PANEL_HEIGHT) // 2
        img = img.crop((left, top, left + PANEL_WIDTH, top + PANEL_HEIGHT))

        # 保存（JPEGでもPNGでもお好みで）
        img.save(dst, format="JPEG", quality=90, optimize=True)

def main():
    for src in sorted(RAW_DIR.glob("*.jpg")) + sorted(RAW_DIR.glob("*.jpeg")) + sorted(RAW_DIR.glob("*.png")):
        dst = OUT_DIR / src.name
        print(f"{src.name} -> {dst.name}")
        preprocess_one(src, dst)

if __name__ == "__main__":
    main()
