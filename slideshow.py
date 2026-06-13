#!/usr/bin/python3
"""
Inky Impression 5.7" 7色版 スライドショー

重要:
- Pillow側での強制7色減色はしない
- Inkyライブラリ側の色変換に任せる
- images/photo/ と images/art/ を再帰的に読む
"""

import os
import time
import random
import logging
import json
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import piexif
from inky.auto import auto
from dotenv import load_dotenv

load_dotenv()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.expanduser("~/.cache/slideshow_state_57.json")

PANEL_WIDTH = 600
PANEL_HEIGHT = 448

CONFIG = {
    "PHOTO_DIR": os.path.join(SCRIPT_DIR, os.getenv("PHOTO_DIR", "images")),
    "FONT_PATH": os.getenv(
        "FONT_PATH",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    "INTERVAL_SECONDS": int(os.getenv("INTERVAL_SECONDS", 1607)),

    "FONT_SIZE": 14,
    "DATE_FONT_SIZE": 16,
    "DATE_POSITIONS": ["bottom-right", "top-right", "top-left", "bottom-left"],
    "MARGIN": 15,
    "BACKGROUND_PADDING": 10,
    "TEXT_PADDING": 8,
    "MAX_RETRY_ATTEMPTS": 3,

    "SATURATION": 0.85,
    "PHOTO_CONTRAST": 1.15,
    "ART_CONTRAST": 1.04,
}


def setup_logging():
    log_dir = os.path.expanduser("~/.logs/slideshow_logs")
    os.makedirs(log_dir, exist_ok=True)

    try:
        os.chmod(log_dir, 0o700)
    except Exception:
        pass

    log_file = os.path.join(log_dir, "slideshow_57.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),
        ],
    )

    return logging.getLogger(__name__)


logger = setup_logging()


def save_state(queue, total_count):
    state = {
        "total_count": total_count,
        "queue": queue,
    }

    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

        with open(STATE_FILE, "w") as f:
            json.dump(state, f)

        logger.info(f"状態保存: 残り {len(queue)} / {total_count} 枚")

    except Exception as e:
        logger.error(f"状態ファイル保存エラー: {e}")


def load_state():
    if not os.path.exists(STATE_FILE):
        return 0, []

    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)

        if isinstance(state, dict):
            count = state.get("total_count", 0)
            queue = state.get("queue", [])
            logger.info(f"状態復元: 残り {len(queue)} / {count} 枚")
            return count, queue

        logger.info("旧フォーマットの状態ファイルを検出しました。リセットします。")
        return 0, []

    except Exception as e:
        logger.error(f"状態ファイル読込エラー: {e}")
        return 0, []


def detect_image_mode(image_path: str) -> str:
    parts = os.path.normpath(image_path).lower().split(os.sep)

    if "art" in parts:
        return "art"

    if "photo" in parts:
        return "photo"

    return "photo"


def collect_images():
    image_paths = []

    for root, dirs, files in os.walk(CONFIG["PHOTO_DIR"]):
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        for filename in files:
            if filename.startswith("."):
                continue

            if filename.lower().endswith((".jpg", ".jpeg", ".png")):
                image_paths.append(os.path.join(root, filename))

    return image_paths


def extract_capture_date(image_path):
    ext = os.path.splitext(image_path)[1].lower()

    if ext == ".png":
        return None

    try:
        exif_dict = piexif.load(image_path)
        date_bytes = exif_dict["Exif"].get(piexif.ExifIFD.DateTimeOriginal)

        if not date_bytes:
            return None

        date_str = date_bytes.decode("utf-8")
        return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")

    except Exception as e:
        logger.warning(f"EXIF 取得エラー ({os.path.basename(image_path)}): {e}")
        return None


def format_date_and_elapsed_time(capture_date):
    if not capture_date:
        return "Unknown date", "Unknown date"

    formatted_date = capture_date.strftime("%Y-%m-%d")
    delta = datetime.now() - capture_date

    years = delta.days // 365

    if years > 0:
        elapsed = f"{years} year{'s' if years > 1 else ''} ago"
    else:
        months = delta.days // 30

        if months > 0:
            elapsed = f"{months} month{'s' if months > 1 else ''} ago"
        else:
            elapsed = "Within a month"

    return formatted_date, elapsed


def enhance_image(img, image_mode: str):
    if image_mode == "art":
        return ImageEnhance.Contrast(img).enhance(CONFIG["ART_CONTRAST"])

    return ImageEnhance.Contrast(img).enhance(CONFIG["PHOTO_CONTRAST"])


def _load_font(size):
    try:
        return ImageFont.truetype(CONFIG["FONT_PATH"], size)
    except Exception:
        logger.warning(
            f"フォント {CONFIG['FONT_PATH']} が見つからないため、デフォルトフォントを使用します。"
        )
        return ImageFont.load_default()


def add_date_overlay(img, capture_date):
    draw = ImageDraw.Draw(img)

    date_font = _load_font(CONFIG["DATE_FONT_SIZE"])
    elapsed_font = _load_font(CONFIG["FONT_SIZE"])

    formatted_date, elapsed_time = format_date_and_elapsed_time(capture_date)

    date_bbox = draw.textbbox((0, 0), formatted_date, font=date_font)
    elapsed_bbox = draw.textbbox((0, 0), elapsed_time, font=elapsed_font)

    date_w = date_bbox[2] - date_bbox[0]
    date_h = date_bbox[3] - date_bbox[1]

    elapsed_w = elapsed_bbox[2] - elapsed_bbox[0]
    elapsed_h = elapsed_bbox[3] - elapsed_bbox[1]

    max_width = max(date_w, elapsed_w)
    total_height = date_h + CONFIG["TEXT_PADDING"] + elapsed_h

    margin = CONFIG["MARGIN"]
    padding = CONFIG["BACKGROUND_PADDING"]

    position = random.choice(CONFIG["DATE_POSITIONS"])

    x = img.width - max_width - margin - padding if "right" in position else margin + padding
    y = img.height - total_height - margin - padding if "bottom" in position else margin + padding

    draw.rectangle(
        (
            x - padding,
            y - padding,
            x + max_width + padding,
            y + total_height + padding,
        ),
        fill="white",
    )

    draw.text((x, y), formatted_date, fill="black", font=date_font)
    draw.text(
        (x, y + date_h + CONFIG["TEXT_PADDING"]),
        elapsed_time,
        fill="black",
        font=elapsed_font,
    )

    return img


def prepare_image(image_path):
    try:
        image_mode = detect_image_mode(image_path)

        logger.info(
            f"画像処理開始: {os.path.basename(image_path)} / mode={image_mode}"
        )

        with Image.open(image_path) as original_img:
            rgb_img = original_img.convert("RGB")
            enhanced_img = enhance_image(rgb_img, image_mode)

            target_width = PANEL_WIDTH
            target_height = PANEL_HEIGHT

            if enhanced_img.size == (target_width, target_height):
                logger.info(
                    f"最適化済みサイズを検出: {enhanced_img.size} → リサイズをスキップ"
                )
                cropped_img = enhanced_img
            else:
                img_ratio = enhanced_img.width / enhanced_img.height
                target_ratio = target_width / target_height

                if img_ratio > target_ratio:
                    new_height = target_height
                    new_width = int(target_height * img_ratio)
                else:
                    new_width = target_width
                    new_height = int(target_width / img_ratio)

                resized_img = enhanced_img.resize(
                    (new_width, new_height),
                    resample=Image.Resampling.LANCZOS,
                )

                left = (new_width - target_width) // 2
                top = (new_height - target_height) // 2

                cropped_img = resized_img.crop(
                    (
                        left,
                        top,
                        left + target_width,
                        top + target_height,
                    )
                )

            capture_date = extract_capture_date(image_path)
            with_date = add_date_overlay(cropped_img, capture_date)

            return with_date.convert("RGB")

    except Exception as e:
        logger.error(f"画像処理エラー [{os.path.basename(image_path)}]: {str(e)[:200]}")
        return None


def main():
    logger.info('=== Inky Impression 5.7" スライドショーを起動します ===')

    try:
        inky_display = auto()

        try:
            inky_display.set_border(inky_display.WHITE)
        except Exception:
            pass

        logger.info(
            f"検出ディスプレイ: {inky_display} / "
            f"解像度: {inky_display.width}x{inky_display.height} "
            f"(論理パネル: {PANEL_WIDTH}x{PANEL_HEIGHT})"
        )

    except Exception as e:
        logger.error(f"ディスプレイ初期化エラー: {e}")
        return

    photo_dir = CONFIG["PHOTO_DIR"]

    if not os.path.isdir(photo_dir):
        logger.error(f"画像ディレクトリが見つかりません: {photo_dir}")
        return

    current_files = collect_images()
    current_file_count = len(current_files)

    saved_count, display_queue = load_state()

    if current_file_count != saved_count:
        logger.info(
            f"画像数の変動を検知: 前回 {saved_count} 枚 → 現在 {current_file_count} 枚。"
            "キューをリセットします。"
        )
        display_queue = []

    total_in_cycle = current_file_count

    while True:
        try:
            if not display_queue:
                logger.info("表示キューが空です。全画像から新しいキューを生成します。")

                all_files = collect_images()

                if not all_files:
                    logger.error(f"画像ファイルが 1 枚も見つかりません: {photo_dir}")

                    if os.path.exists(STATE_FILE):
                        os.remove(STATE_FILE)

                    time.sleep(60)
                    continue

                random.shuffle(all_files)
                display_queue = all_files
                total_in_cycle = len(display_queue)

            image_path = display_queue.pop(0)

            if not os.path.exists(image_path):
                logger.warning(f"存在しない画像をスキップします: {image_path}")
                save_state(display_queue, total_in_cycle)
                continue

            logger.info(
                f"表示対象: {os.path.basename(image_path)} "
                f"/ mode={detect_image_mode(image_path)}"
            )

            processed_image = prepare_image(image_path)

            if processed_image is None:
                logger.error(
                    f"画像処理に失敗したためスキップします: {os.path.basename(image_path)}"
                )
            else:
                success = False

                for attempt in range(1, CONFIG["MAX_RETRY_ATTEMPTS"] + 1):
                    try:
                        inky_display.set_image(
                            processed_image,
                            saturation=CONFIG["SATURATION"],
                        )
                        inky_display.show()

                        logger.info(
                            f"表示成功: {os.path.basename(image_path)} "
                            f"(attempt={attempt})"
                        )

                        save_state(display_queue, total_in_cycle)
                        success = True
                        break

                    except Exception as e:
                        logger.error(f"表示エラー (attempt={attempt}): {e}")
                        time.sleep(5)

                if not success:
                    logger.error(
                        f"連続表示エラーのためスキップ: {os.path.basename(image_path)}"
                    )

            interval = CONFIG["INTERVAL_SECONDS"]
            logger.info(f"次の表示まで {interval} 秒待機します...")
            time.sleep(interval)

        except KeyboardInterrupt:
            logger.info("ユーザー操作により中断されました。終了します。")
            break

        except Exception as e:
            logger.error(f"予期しないエラー: {e}")
            time.sleep(10)

    logger.info("=== スライドショーを終了しました ===")


if __name__ == "__main__":
    main()
