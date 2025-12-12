#!/usr/bin/python3

"""
================================================================================
          Inky Impression 5.7" - 高機能スライドショー スクリプト
================================================================================

概要 (Overview)
--------------------------------------------------------------------------------
このスクリプトは、Raspberry Pi に接続された Pimoroni 製電子ペーパー
「Inky Impression 5.7\" (7 colour ePaper/eInk HAT)」を、
インテリジェントなデジタルフォトフレームとして動作させるためのものです。

- 指定フォルダから画像を読み込み
- パネル解像度 (600x448) にリサイズ + 中央クロップ
- EXIF から撮影日・経過年数を取得し、四隅のどこかにオーバーレイ
- 表示キューを JSON に保存し、再起動後も続きから再開
================================================================================
"""

# ===== 標準ライブラリ =====
import os
import time
import random
import logging
import json
from datetime import datetime

# ===== サードパーティ =====
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import piexif
from inky.auto import auto
from dotenv import load_dotenv

# .env を読み込み
load_dotenv()

# ==================== 定数・設定 ====================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.expanduser("~/.cache/slideshow_state_57.json")

# Inky Impression 5.7" のパネル解像度
PANEL_WIDTH = 600
PANEL_HEIGHT = 448

CONFIG = {
    # --- .env から読む設定 ---
    "PHOTO_DIR": os.path.join(SCRIPT_DIR, os.getenv("PHOTO_DIR", "images")),
    "FONT_PATH": os.getenv(
        "FONT_PATH",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    # デフォルト間隔: 約 26 分 47 秒
    "INTERVAL_SECONDS": int(os.getenv("INTERVAL_SECONDS", 1607)),

    # --- 固定設定 ---
    "FONT_SIZE": 14,
    "DATE_FONT_SIZE": 16,
    "DATE_POSITIONS": ["bottom-right", "top-right", "top-left", "bottom-left"],
    "MARGIN": 15,
    "BACKGROUND_PADDING": 10,
    "TEXT_PADDING": 8,
    "MAX_RETRY_ATTEMPTS": 3,
    "SATURATION": 0.85,
    "CONTRAST": 1.15,
}


# ==================== ログ初期化 ====================

def setup_logging():
    log_dir = os.path.expanduser("~/.logs/slideshow_logs")
    os.makedirs(log_dir, exist_ok=True)
    try:
        os.chmod(log_dir, 0o700)
    except Exception:
        pass

    log_file = os.path.join(log_dir, "slideshow.log")
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


# ==================== 状態管理 ====================

def save_state(queue, total_count):
    """
    現在の表示キューと総画像数を JSON に保存
    """
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
    """
    JSON から表示キューと総画像数を復元
    （旧フォーマットにも対応）
    """
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)

            if isinstance(state, dict):
                count = state.get("total_count", 0)
                queue = state.get("queue", [])
                logger.info(f"状態復元: 残り {len(queue)} / {count} 枚")
                return count, queue

            elif isinstance(state, list):
                # 旧フォーマット（単純なリスト）
                logger.info("旧フォーマットの状態ファイルを検出しました（リセット予定）。")
                return 0, state

        except Exception as e:
            logger.error(f"状態ファイル読込エラー: {e}")

    return 0, []


# ==================== 画像処理系 ====================

def extract_capture_date(image_path):
    """
    JPEG から EXIF の撮影日時を取得（PNG は None）
    """
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
    """
    撮影日と「X years ago」形式の経過時間テキストを返す
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
    コントラスト調整など、軽い画像強調
    """
    return ImageEnhance.Contrast(img).enhance(CONFIG["CONTRAST"])


def _load_font(size):
    """
    フォントが見つからないときにデフォルトにフォールバック
    """
    try:
        return ImageFont.truetype(CONFIG["FONT_PATH"], size)
    except Exception:
        logger.warning(f"フォント {CONFIG['FONT_PATH']} が見つからないため、デフォルトフォントを使用します。")
        return ImageFont.load_default()


def add_date_overlay(img, capture_date):
    """
    撮影日と経過時間を画像の四隅のどこかにオーバーレイ
    """
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

    # 位置計算
    if "right" in position:
        x = img.width - max_width - margin - padding
    else:
        x = margin + padding

    if "bottom" in position:
        y = img.height - total_height - margin - padding
    else:
        y = margin + padding

    # 背景の白矩形
    bg_left = x - padding
    bg_top = y - padding
    bg_right = x + max_width + padding
    bg_bottom = y + total_height + padding

    draw.rectangle((bg_left, bg_top, bg_right, bg_bottom), fill="white")

    # テキスト描画
    draw.text((x, y), formatted_date, fill="black", font=date_font)
    draw.text(
        (x, y + date_h + CONFIG["TEXT_PADDING"]),
        elapsed_time,
        fill="black",
        font=elapsed_font,
    )

    return img


def prepare_image(image_path):
    """
    1枚の画像を
    - RGB化
    - コントラスト調整
    - PANEL_WIDTH x PANEL_HEIGHT になるようリサイズ
    - 中央クロップ
    - 日付オーバーレイ
    した PIL.Image を返す
    """
    try:
        logger.info(f"画像処理開始: {os.path.basename(image_path)}")

        with Image.open(image_path) as original_img:
            rgb_img = original_img.convert("RGB")
            enhanced_img = enhance_image(rgb_img)

            target_width = PANEL_WIDTH
            target_height = PANEL_HEIGHT

            img_ratio = enhanced_img.width / enhanced_img.height
            target_ratio = target_width / target_height

            # アスペクト比を保ったまま、少し大きめに合わせて中央クロップ
            if img_ratio > target_ratio:
                # 横長 → 高さを合わせる
                new_height = target_height
                new_width = int(target_height * img_ratio)
            else:
                # 縦長 → 幅を合わせる
                new_width = target_width
                new_height = int(target_width / img_ratio)

            resized_img = enhanced_img.resize(
                (new_width, new_height),
                resample=Image.Resampling.LANCZOS,
            )

            left = (new_width - target_width) // 2
            top = (new_height - target_height) // 2
            cropped_img = resized_img.crop(
                (left, top, left + target_width, top + target_height)
            )

            capture_date = extract_capture_date(image_path)
            with_date = add_date_overlay(cropped_img, capture_date)

            return with_date

    except Exception as e:
        logger.error(f"画像処理エラー [{os.path.basename(image_path)}]: {str(e)[:200]}")
        return None


# ==================== メイン処理 ====================

def main():
    logger.info("=== Inky Impression 5.7\" スライドショーを起動します ===")

    # ディスプレイ初期化
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

    # 現在の画像一覧
    current_files = [
        os.path.join(photo_dir, f)
        for f in os.listdir(photo_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    current_file_count = len(current_files)

    # 状態復元
    saved_count, display_queue = load_state()

    # 画像枚数が変わっていたらキューをリセット
    if current_file_count != saved_count:
        logger.info(
            f"画像数の変動を検知: 前回 {saved_count} 枚 → 現在 {current_file_count} 枚。"
            "キューをリセットします。"
        )
        display_queue = []

    total_in_cycle = current_file_count

    while True:
        try:
            # キューが空なら新しく全画像リストを作成
            if not display_queue:
                logger.info("表示キューが空です。全画像から新しいキューを生成します。")
                all_files = [
                    os.path.join(photo_dir, f)
                    for f in os.listdir(photo_dir)
                    if f.lower().endswith((".jpg", ".jpeg", ".png"))
                ]

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

            processed_image = prepare_image(image_path)

            if processed_image is None:
                logger.error(
                    f"画像処理に失敗したためスキップします: {os.path.basename(image_path)}"
                )
            else:
                # 表示リトライ
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
                        # 状態保存
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
