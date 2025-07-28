#!/usr/bin/python3
"""
Pimoroni Inky Impression用 スライドショープログラム
（汎用版：パスや設定を外部ファイルで管理）
"""

# ===== 標準ライブラリのインポート =====
import os
import time
import random
import logging
from datetime import datetime

# ===== サードパーティライブラリのインポート =====
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import piexif
from inky.auto import auto
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# ==================== 設定定数（環境変数と固定値） ====================

# スクリプト自身の場所を基準にする
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG = {
    # --- .envファイルから読み込む設定 ---
    # PHOTO_DIR: 環境変数 "PHOTO_DIR" から読み込み、なければ "images" をデフォルトとする
    "PHOTO_DIR": os.path.join(SCRIPT_DIR, os.getenv("PHOTO_DIR", "images")),
    
    # FONT_PATH: 環境変数 "FONT_PATH" から読み込み、なければDejaVuSans-Boldをデフォルトとする
    "FONT_PATH": os.getenv("FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    
    # INTERVAL_SECONDS: 環境変数 "INTERVAL_SECONDS" を整数で読み込み、なければ1607をデフォルトとする
    "INTERVAL_SECONDS": int(os.getenv("INTERVAL_SECONDS", 1607)),

    # --- スクリプト内に記述する固定設定 ---
    "FONT_SIZE": 14,
    "DATE_FONT_SIZE": 16,
    "DATE_POSITIONS": [
        'bottom-right',
        'top-right',
        'top-left',
        'bottom-left'
    ],
    "MARGIN": 15,
    "BACKGROUND_PADDING": 10,
    "TEXT_PADDING": 8,
    "MAX_RETRY_ATTEMPTS": 3,
    "SATURATION": 0.85,
    "CONTRAST": 1.15
}

# ==================== ログシステムの初期化 ====================
def setup_logging():
    """
    ログ設定を初期化し、ロガーオブジェクトを返す
    - ログファイルはユーザーのホームディレクトリ下の.logsに保存
    - ログディレクトリのパーミッションを700に設定（セキュリティ対策）
    """
    log_dir = os.path.expanduser("~/.logs/slideshow_logs")

    os.makedirs(log_dir, exist_ok=True)
    try:
        os.chmod(log_dir, 0o700)
    except Exception:
        pass

    log_file = os.path.join(log_dir, "slideshow.log")

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# ==================== 画像処理関連関数 ====================
def extract_capture_date(image_path):
    """
    画像からEXIF情報を読み込み、撮影日時を抽出する
    """
    file_ext = os.path.splitext(image_path)[1].lower()
    if file_ext == '.png':
        logger.info(f"PNGファイルのため撮影日時は取得できません: {os.path.basename(image_path)}")
        return None

    try:
        exif_dict = piexif.load(image_path)
        date_str = exif_dict['Exif'].get(piexif.ExifIFD.DateTimeOriginal)

        if date_str:
            decoded_date = date_str.decode('utf-8')
            return datetime.strptime(decoded_date, "%Y:%m:%d %H:%M:%S")
        else:
            return None
    except Exception as e:
        logger.warning(f"EXIF取得エラー ({os.path.basename(image_path)}): {e}")
        return None

def format_date_and_elapsed_time(capture_date):
    """
    撮影日と経過時間をフォーマットする
    """
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

def enhance_image(img):
    """
    画像のコントラストを調整する
    """
    contrast_enhancer = ImageEnhance.Contrast(img)
    return contrast_enhancer.enhance(CONFIG["CONTRAST"])

def add_date_overlay(img, capture_date, inky_display):
    """
    画像に撮影日と経過時間をオーバーレイ表示する
    """
    draw = ImageDraw.Draw(img)
    elapsed_font = ImageFont.truetype(CONFIG["FONT_PATH"], CONFIG["FONT_SIZE"])
    date_font = ImageFont.truetype(CONFIG["FONT_PATH"], CONFIG["DATE_FONT_SIZE"])

    formatted_date, elapsed_time = format_date_and_elapsed_time(capture_date)

    date_bbox = draw.textbbox((0,0), formatted_date, font=date_font)
    elapsed_bbox = draw.textbbox((0,0), elapsed_time, font=elapsed_font)
    max_width = max(date_bbox[2], elapsed_bbox[2])
    date_height = date_bbox[3] - date_bbox[1]
    elapsed_height = elapsed_bbox[3] - elapsed_bbox[1]
    total_height = date_height + elapsed_height + CONFIG["TEXT_PADDING"]

    margin = CONFIG["MARGIN"]
    padding = CONFIG["BACKGROUND_PADDING"]
    position = random.choice(CONFIG["DATE_POSITIONS"])

    if position == 'bottom-right':
        x = img.width - max_width - margin - padding
        y = img.height - total_height - margin - padding
    elif position == 'top-right':
        x = img.width - max_width - margin - padding
        y = margin + padding
    elif position == 'top-left':
        x = margin + padding
        y = margin + padding
    else:  # bottom-left
        x = margin + padding
        y = img.height - total_height - margin - padding

    bg_left, bg_top = x - padding, y - padding
    bg_right = x + max_width + padding
    bg_bottom = y + total_height + padding

    draw.rectangle((bg_left, bg_top, bg_right, bg_bottom), fill="white")
    draw.text((x, y), formatted_date, fill="black", font=date_font)
    text_y = y + date_height + CONFIG["TEXT_PADDING"]
    draw.text((x, text_y), elapsed_time, fill="black", font=elapsed_font)

    return img

# ==================== Inkyディスプレイ用画像処理 ====================
def prepare_image(image_path, inky_display):
    """
    Inkyディスプレイ用に画像を最適化する
    """
    try:
        target_width, target_height = inky_display.width, inky_display.height
        logger.info(f"画像処理開始: {os.path.basename(image_path)}")

        with Image.open(image_path) as original_img:
            rgb_img = original_img.convert('RGB')
            enhanced_img = enhance_image(rgb_img)

            img_ratio = enhanced_img.width / enhanced_img.height
            target_ratio = target_width / target_height

            if img_ratio > target_ratio:
                new_height = target_height
                new_width = int(target_height * img_ratio)
            else:
                new_width = target_width
                new_height = int(target_width / img_ratio)

            resized_img = enhanced_img.resize((new_width, new_height), resample=Image.Resampling.LANCZOS)

            left = (new_width - target_width) // 2
            top = (new_height - target_height) // 2
            right, bottom = left + target_width, top + target_height
            cropped_img = resized_img.crop((left, top, right, bottom))

            capture_date = extract_capture_date(image_path)
            final_img = add_date_overlay(cropped_img, capture_date, inky_display)
            return final_img

    except Exception as e:
        logger.error(f"画像処理エラー [{os.path.basename(image_path)}]: {str(e)[:100]}")
        return None

# ==================== メイン処理ループ ====================
def main():
    """プログラムのメイン実行関数"""
    logger.info("=== Inkyスライドショーを起動します ===")

    try:
        inky_display = auto()
        inky_display.set_border(inky_display.WHITE)
        logger.info(f"検出されたディスプレイ: {inky_display} 解像度: {inky_display.width}x{inky_display.height}")
    except Exception as e:
        logger.error(f"ディスプレイ初期化エラー: {e}")
        return

    photo_dir = CONFIG["PHOTO_DIR"]
    if not os.path.isdir(photo_dir):
        logger.error(f"画像ディレクトリが見つかりません: {photo_dir}")
        return

    image_files = [
        os.path.join(photo_dir, f)
        for f in os.listdir(photo_dir)
        if f.lower().endswith(('.jpg', '.jpeg', '.png'))
    ]

    if not image_files:
        logger.error(f"画像ファイルが見つかりませんでした: {photo_dir}")
        return

    logger.info(f"読み込んだ画像の数: {len(image_files)}枚")

    while True:
        try:
            random.shuffle(image_files)
            for image_path in image_files:
                logger.info(f"表示処理開始: {os.path.basename(image_path)}")
                processed_image = prepare_image(image_path, inky_display)

                if processed_image:
                    try:
                        inky_display.set_image(processed_image, saturation=CONFIG["SATURATION"])
                        inky_display.show()
                        logger.info(f"表示に成功しました: {os.path.basename(image_path)}")
                    except Exception as e:
                        logger.error(f"表示エラー: {str(e)[:100]}")
                
                time.sleep(CONFIG["INTERVAL_SECONDS"])

        except KeyboardInterrupt:
            logger.info("ユーザーの操作により中断されました")
            break
        except Exception as e:
            logger.error(f"致命的なエラーが発生しました: {str(e)[:100]}")
            time.sleep(10)

if __name__ == "__main__":
    main()
    logger.info("=== プログラムを正常終了します ===")
