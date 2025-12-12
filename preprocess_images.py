#!/usr/bin/env python3
"""
Inky Impression 5.7\" 用 事前リサイズスクリプト

- PHOTO_RAW_DIR にある元画像を読み込み
- Inky Impression 5.7\" (600x448) 向けにリサイズ＆中央トリミング
- JPEG の EXIF (特に DateTimeOriginal) を可能な限りコピー
- PHOTO_OUT_DIR に保存

想定ディレクトリ構成:
  inky57-slideshow/
    ├── slideshow.py
    ├── preprocess_images.py   ← このスクリプト
    ├── photos_raw/            ← 元画像(入力)
    └── photos/                ← リサイズ後(出力)  ※slideshow.py の PHOTO_DIR と合わせる
"""

import os
import sys
import logging
from pathlib import Path

from PIL import Image, ImageEnhance
from dotenv import load_dotenv

# .env 読み込み
load_dotenv()

# ===== 設定 =====

SCRIPT_DIR = Path(__file__).resolve().parent

# 入力元の生画像ディレクトリ（デフォルト: photos_raw）
PHOTO_RAW_DIR = Path(
    os.getenv("PHOTO_RAW_DIR", SCRIPT_DIR / "photos_raw")
)

# 出力先（slideshow が読むディレクトリ）デフォルト: photos
PHOTO_OUT_DIR = Path(
    os.getenv("PHOTO_OUT_DIR", SCRIPT_DIR / "photos")
)

# Inky Impression 5.7" のパネル解像度
TARGET_WIDTH = int(os.getenv("INKY_WIDTH", "600"))
TARGET_HEIGHT = int(os.getenv("INKY_HEIGHT", "448"))

# 画像調整（必要に応じて微調整）
CONTRAST = float(os.getenv("PRE_CONTRAST", "1.05"))
SATURATION = float(os.getenv("PRE_SATURATION", "1.00"))

# 対象とする拡張子
VALID_EXT = (".jpg", ".jpeg", ".png")

# ===== ログ設定 =====

LOG_DIR = Path(os.path.expanduser("~/.logs/inky57_preprocess"))
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "preprocess_images.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def find_images(src_dir: Path):
    """再帰的に画像ファイルを列挙"""
    if not src_dir.exists():
        return []

    files = []
    for p in src_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() in VALID_EXT:
            files.append(p)
    return sorted(files)


def resize_and_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """
    画像をパネル解像度に合わせてリサイズし、中央トリミング（レターボックス無し）。
    """
    # まず RGB に固定
    img = img.convert("RGB")

    # コントラスト調整（軽め）
    if abs(CONTRAST - 1.0) > 1e-3:
        img = ImageEnhance.Contrast(img).enhance(CONTRAST)

    # 彩度調整（必要なら）
    if abs(SATURATION - 1.0) > 1e-3:
        # Pillow には直接の Saturation はないので HSV などでも出来るが、
        # Inky ではそこまでシビアでないので一旦スキップしてもよい。
        # 必要であればここで実装する。
        pass

    src_w, src_h = img.size
    src_ratio = src_w / src_h
    tgt_ratio = target_w / target_h

    # アスペクト比に合わせて一辺をフィットさせる
    if src_ratio > tgt_ratio:
        # 横長 → 高さを合わせて横はオーバーさせる
        new_h = target_h
        new_w = int(new_h * src_ratio)
    else:
        # 縦長 or 同比率 → 幅を合わせて縦はオーバーさせる
        new_w = target_w
        new_h = int(new_w / src_ratio)

    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # 中央トリミング
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    right = left + target_w
    bottom = top + target_h

    img = img.crop((left, top, right, bottom))
    return img


def process_one(src_path: Path, dst_root: Path):
    """
    1ファイル処理:
      - リサイズ & トリミング
      - EXIF を可能な限りコピー
    """
    rel = src_path.relative_to(PHOTO_RAW_DIR)
    dst_path = dst_root / rel

    # 出力先の拡張子は JPEG に統一する場合はここで変更
    # 例: PNG も含めて全部 .jpg にしたい場合:
    if dst_path.suffix.lower() not in (".jpg", ".jpeg"):
        dst_path = dst_path.with_suffix(".jpg")

    dst_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with Image.open(src_path) as img:
            # 元画像の EXIF を取得（JPEG なら多くの場合入っている）
            exif_bytes = img.info.get("exif")

            resized = resize_and_crop(img, TARGET_WIDTH, TARGET_HEIGHT)

            save_kwargs = {
                "quality": 90,
                "optimize": True,
            }
            # EXIF があれば付けて保存（DateTimeOriginal などを保持）
            if exif_bytes is not None:
                save_kwargs["exif"] = exif_bytes

            resized.save(dst_path, format="JPEG", **save_kwargs)

        logger.info(f"OK  : {src_path} → {dst_path}")

    except Exception as e:
        logger.error(f"FAIL: {src_path} → {dst_path} : {e}")


def main():
    logger.info("=== preprocess_images: start ===")
    logger.info(f"入力ディレクトリ: {PHOTO_RAW_DIR}")
    logger.info(f"出力ディレクトリ: {PHOTO_OUT_DIR}")
    logger.info(f"ターゲット解像度: {TARGET_WIDTH}x{TARGET_HEIGHT}")

    images = find_images(PHOTO_RAW_DIR)
    if not images:
        logger.warning("処理対象の画像が見つかりませんでした。")
        return

    logger.info(f"処理対象ファイル数: {len(images)}")

    for src in images:
        process_one(src, PHOTO_OUT_DIR)

    logger.info("=== preprocess_images: done ===")


if __name__ == "__main__":
    main()
